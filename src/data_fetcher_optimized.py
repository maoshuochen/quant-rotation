"""
优化版数据获取器
- 并行获取
- 增量更新
- 自动重试
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, retry
from typing import Dict, List, Optional
import logging
import time

from src.datafetcher_baostock import IndexDataFetcher

logger = logging.getLogger(__name__)


class OptimizedDataFetcher:
    """
    优化版数据获取器

    特性:
    - 多线程并行获取
    - 增量更新 (仅获取新增数据)
    - 自动重试机制
    - 请求限流
    """

    def __init__(
        self,
        cache_dir: str = "data/raw",
        max_workers: int = 5,
        retry_times: int = 3,
        rate_limit: float = 0.5  # 秒
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_workers = max_workers
        self.retry_times = retry_times
        self.rate_limit = rate_limit
        self._fetcher = IndexDataFetcher()

    def fetch_all_etfs(
        self,
        indices: List[dict],
        start_date: str,
        force_refresh: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        并行获取所有 ETF 数据

        Args:
            indices: 指数配置列表
            start_date: 开始日期
            force_refresh: 强制刷新

        Returns:
            {code: DataFrame} 字典
        """
        results = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._fetch_with_retry,
                    idx['code'],
                    idx.get('etf'),
                    start_date,
                    force_refresh
                ): idx for idx in indices if idx.get('etf')
            }

            for future in futures:
                try:
                    code, df = future.result()
                    if df is not None and not df.empty:
                        results[code] = df
                except Exception as e:
                    logger.warning(f"获取 ETF 失败：{e}")

        logger.info(f"成功获取 {len(results)} 个 ETF 数据")
        return results

    def _fetch_with_retry(
        self,
        code: str,
        etf: str,
        start_date: str,
        force_refresh: bool
    ) -> tuple:
        """带重试的获取"""
        for attempt in range(self.retry_times):
            try:
                df = self._fetcher.fetch_etf_history(
                    etf, start_date, force_refresh=force_refresh
                )

                if not df.empty:
                    # 限流
                    time.sleep(self.rate_limit)
                    return (code, df)

            except Exception as e:
                logger.warning(f"获取 {code} 失败 (尝试 {attempt + 1}/{self.retry_times}): {e}")
                time.sleep(1 * (attempt + 1))  # 递增等待

        return (code, pd.DataFrame())

    def fetch_incremental(
        self,
        indices: List[dict],
        last_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        增量获取 ETF 数据

        Args:
            indices: 指数配置列表
            last_date: 最后已获取日期

        Returns:
            新增数据字典
        """
        if last_date:
            # 从最后日期后一天开始
            start_date = (pd.to_datetime(last_date) + timedelta(days=1)).strftime('%Y%m%d')
        else:
            # 默认获取最近 30 天
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')

        logger.info(f"增量获取数据：{start_date} 至今")
        return self.fetch_all_etfs(indices, start_date)

    def get_cached_data(self, code: str) -> Optional[pd.DataFrame]:
        """读取缓存数据"""
        cache_file = self._get_cache_file(code)
        if cache_file.exists():
            try:
                return pd.read_parquet(cache_file)
            except Exception as e:
                logger.warning(f"读取缓存失败：{e}")
        return None

    def _get_cache_file(self, code: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{code.replace('.', '_')}_etf_history.parquet"

    def close(self):
        """关闭连接"""
        self._fetcher.close()
