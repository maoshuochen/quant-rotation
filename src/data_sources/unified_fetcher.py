"""
统一数据获取器
自动选择和切换数据源，带缓存支持
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
import os

from .base import BaseDataFetcher, DataSourceConfig
from .baostock_adapter import BaostockAdapter
from .tushare_adapter import TushareAdapter
from .akshare_adapter import AKShareAdapter
from .cache_manager import CacheManager

logger = logging.getLogger(__name__)


class UnifiedDataFetcher:
    """
    统一数据获取器

    特性:
    - 多数据源自动切换
    - 缓存支持
    - 数据质量检查
    - 健康状态监控
    """

    def __init__(
        self,
        cache_dir: str = "data/cache",
        enable_cache: bool = True,
        cache_ttl_hours: int = 24
    ):
        self.cache = CacheManager(
            parquet_dir=f"{cache_dir}/parquet",
            sqlite_path=f"{cache_dir}/metadata.db",
            default_ttl_hours=cache_ttl_hours
        ) if enable_cache else None

        # 初始化数据源
        self.sources: List[BaseDataFetcher] = []
        self._init_sources()

        logger.info(f"UnifiedDataFetcher initialized with {len(self.sources)} sources")

    def _init_sources(self):
        """初始化数据源（按优先级）"""
        # 1. Tushare (如果 token 可用)
        tushare_token = os.environ.get('TUSHARE_TOKEN')
        if tushare_token:
            ts = TushareAdapter(token=tushare_token)
            if ts.is_available:
                self.sources.append(ts)
                logger.info("Tushare source registered")

        # 2. Baostock (主力数据源)
        baostock = BaostockAdapter()
        if baostock.is_available:
            self.sources.append(baostock)
            logger.info("Baostock source registered")

        # 3. AKShare (补充数据源)
        akshare = AKShareAdapter()
        self.sources.append(akshare)
        logger.info("AKShare source registered")

    def _get_available_source(
        self,
        exclude: Optional[List[str]] = None
    ) -> Optional[BaseDataFetcher]:
        """获取第一个可用的数据源"""
        exclude = exclude or []
        for source in self.sources:
            if source.source_name not in exclude and source.is_available:
                return source
        return None

    def fetch_price_history(
        self,
        code: str,
        start_date: str,
        end_date: Optional[str] = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        获取历史行情数据

        Args:
            code: 证券代码
            start_date: 开始日期
            end_date: 结束日期
            use_cache: 是否使用缓存

        Returns:
            DataFrame with OHLCV data
        """
        # 尝试从缓存读取
        if use_cache and self.cache:
            cache_key = f"price_{code}_{start_date}_{end_date or 'today'}"
            cached = self.cache.read(cache_key)
            if cached is not None:
                return cached

        # 从数据源获取
        result = self._fetch_with_fallback(
            'fetch_price_history',
            code=code,
            start_date=start_date,
            end_date=end_date
        )

        # 保存到缓存
        if use_cache and self.cache and not result.empty:
            cache_key = f"price_{code}_{start_date}_{end_date or 'today'}"
            self.cache.write(cache_key, result)

        return result

    def fetch_index_pe_history(
        self,
        index_code: str,
        start_date: str,
        end_date: Optional[str] = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """获取指数 PE/PB 历史数据"""
        if use_cache and self.cache:
            cache_key = f"pe_{index_code}_{start_date}_{end_date or 'today'}"
            cached = self.cache.read(cache_key)
            if cached is not None:
                return cached

        result = self._fetch_with_fallback(
            'fetch_index_pe_history',
            index_code=index_code,
            start_date=start_date,
            end_date=end_date
        )

        if use_cache and self.cache and not result.empty:
            cache_key = f"pe_{index_code}_{start_date}_{end_date or 'today'}"
            self.cache.write(cache_key, result)

        return result

    def fetch_northbound_flow(
        self,
        start_date: str,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """获取北向资金流向数据"""
        if use_cache and self.cache:
            cache_key = f"northbound_{start_date}"
            cached = self.cache.read(cache_key)
            if cached is not None:
                return cached

        result = self._fetch_with_fallback(
            'fetch_northbound_flow',
            start_date=start_date
        )

        if use_cache and self.cache and not result.empty:
            cache_key = f"northbound_{start_date}"
            self.cache.write(cache_key, result)

        return result

    def fetch_etf_shares(
        self,
        etf_code: str,
        start_date: str,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """获取 ETF 份额数据"""
        if use_cache and self.cache:
            cache_key = f"etf_shares_{etf_code}_{start_date}"
            cached = self.cache.read(cache_key)
            if cached is not None:
                return cached

        result = self._fetch_with_fallback(
            'fetch_etf_shares',
            etf_code=etf_code,
            start_date=start_date
        )

        if use_cache and self.cache and not result.empty:
            cache_key = f"etf_shares_{etf_code}_{start_date}"
            self.cache.write(cache_key, result)

        return result

    def _fetch_with_fallback(
        self,
        method_name: str,
        exclude_sources: Optional[List[str]] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        带回退机制的数据获取

        尝试所有数据源，直到成功或全部失败
        """
        exclude = exclude_sources or []
        tried_sources = []

        while True:
            source = self._get_available_source(exclude=exclude + tried_sources)
            if source is None:
                break

            tried_sources.append(source.source_name)

            try:
                method = getattr(source, method_name, None)
                if method:
                    result = method(**kwargs)
                    if result is not None and not result.empty:
                        logger.info(f"Successfully fetched from {source.source_name}")
                        return result
            except Exception as e:
                logger.warning(f"{source.source_name} failed: {e}")

        logger.error(f"All sources failed for {method_name}")
        return pd.DataFrame()

    def refresh_cache(self, code: str, data_types: Optional[List[str]] = None):
        """刷新指定证券的缓存"""
        if not self.cache:
            return

        data_types = data_types or ['price', 'pe']
        for data_type in data_types:
            self.cache.invalidate_pattern(f"{data_type}_{code}_*")

        logger.info(f"Cache refreshed for {code}")

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        if self.cache:
            return self.cache.get_stats()
        return {'enabled': False}

    def cleanup_expired_cache(self) -> int:
        """清理过期缓存"""
        if self.cache:
            return self.cache.cleanup_expired()
        return 0

    def get_health_status(self) -> Dict[str, bool]:
        """获取所有数据源健康状态"""
        return {
            source.source_name: source.is_available
            for source in self.sources
        }

    def close(self):
        """关闭所有数据源连接"""
        for source in self.sources:
            if hasattr(source, 'logout'):
                source.logout()
        logger.info("All data sources closed")
