"""
数据缓存层
支持 SQLite + Parquet 混合缓存
"""
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


class DataCache:
    """
    数据缓存管理器

    缓存策略:
    1. 热数据 (7 天内): Parquet 文件缓存
    2. 冷数据 (7 天前): SQLite 数据库缓存
    3. 元数据：SQLite 存储
    """

    def __init__(
        self,
        cache_dir: str = "data/cache",
        db_path: Optional[str] = None,
        ttl_days: int = 7
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path or str(self.cache_dir / "data_cache.db")
        self.ttl_days = ttl_days

        self._init_database()
        logger.info(f"DataCache initialized: {self.cache_dir}")

    def _init_database(self):
        """初始化 SQLite 数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 缓存元数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_meta (
                    key TEXT PRIMARY KEY,
                    data_type TEXT,
                    code TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    row_count INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    expires_at TEXT,
                    source TEXT
                )
            """)

            # 数据表 (通用结构)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT,
                    date TEXT,
                    column_name TEXT,
                    value REAL,
                    FOREIGN KEY (cache_key) REFERENCES cache_meta(key)
                )
            """)

            # 索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_key
                ON cache_data(cache_key)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_date
                ON cache_data(date)
            """)

            conn.commit()

    def _generate_key(
        self,
        data_type: str,
        code: str,
        start_date: str,
        end_date: str
    ) -> str:
        """生成缓存键"""
        key_str = f"{data_type}:{code}:{start_date}:{end_date}"
        return hashlib.md5(key_str.encode()).hexdigest()[:16]

    def _get_parquet_path(self, key: str, data_type: str) -> Path:
        """获取 Parquet 缓存文件路径"""
        return self.cache_dir / f"{data_type}_{key}.parquet"

    def get(
        self,
        data_type: str,
        code: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        从缓存获取数据

        Args:
            data_type: 数据类型 (price/pe/northbound/etf_shares)
            code: 证券代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame 或 None (缓存未命中)
        """
        key = self._generate_key(data_type, code, start_date, end_date)

        # 1. 检查元数据
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT expires_at, row_count
                FROM cache_meta
                WHERE key = ?
            """, (key,))
            row = cursor.fetchone()

            if row is None:
                logger.debug(f"Cache miss: {data_type}:{code}")
                return None

            expires_at, row_count = row

            # 检查是否过期
            if datetime.fromisoformat(expires_at) < datetime.now():
                logger.info(f"Cache expired: {data_type}:{code}")
                self.delete(key)
                return None

        # 2. 读取 Parquet 数据
        parquet_path = self._get_parquet_path(key, data_type)

        if parquet_path.exists():
            try:
                df = pd.read_parquet(parquet_path)
                logger.info(f"Cache hit: {data_type}:{code} ({row_count} rows)")
                return df
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")
                return None

        return None

    def set(
        self,
        data_type: str,
        code: str,
        start_date: str,
        end_date: str,
        df: pd.DataFrame,
        source: str = "unknown"
    ):
        """
        保存数据到缓存

        Args:
            data_type: 数据类型
            code: 证券代码
            start_date: 开始日期
            end_date: 结束日期
            df: 数据 DataFrame
            source: 数据源名称
        """
        if df.empty:
            logger.warning("不缓存空数据")
            return

        key = self._generate_key(data_type, code, start_date, end_date)
        expires_at = (datetime.now() + timedelta(days=self.ttl_days)).isoformat()

        # 1. 保存 Parquet 文件
        parquet_path = self._get_parquet_path(key, data_type)

        try:
            df.to_parquet(parquet_path, index=True)
        except Exception as e:
            logger.error(f"Parquet write failed: {e}")
            return

        # 2. 更新元数据
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 确保日期列为索引
            if isinstance(df.index, pd.DatetimeIndex):
                actual_start = df.index.min().strftime('%Y-%m-%d')
                actual_end = df.index.max().strftime('%Y-%m-%d')
            else:
                actual_start = start_date
                actual_end = end_date

            cursor.execute("""
                INSERT OR REPLACE INTO cache_meta
                (key, data_type, code, start_date, end_date, row_count,
                 created_at, updated_at, expires_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                key, data_type, code, actual_start, actual_end,
                len(df), datetime.now().isoformat(),
                datetime.now().isoformat(), expires_at, source
            ))

            conn.commit()

        logger.info(f"Cached: {data_type}:{code} ({len(df)} rows)")

    def delete(self, key: str):
        """删除缓存"""
        # 删除 Parquet 文件
        parquet_files = list(self.cache_dir.glob(f"*_{key}.parquet"))
        for f in parquet_files:
            try:
                f.unlink()
            except Exception as e:
                logger.warning(f"Delete parquet failed: {e}")

        # 删除元数据
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cache_meta WHERE key = ?", (key,))
            cursor.execute("DELETE FROM cache_data WHERE cache_key = ?", (key,))
            conn.commit()

    def invalidate(
        self,
        data_type: Optional[str] = None,
        code: Optional[str] = None
    ):
        """
        批量失效缓存

        Args:
            data_type: 数据类型，None 表示所有
            code: 证券代码，None 表示所有
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            conditions = []
            params = []

            if data_type:
                conditions.append("data_type = ?")
                params.append(data_type)
            if code:
                conditions.append("code = ?")
                params.append(code)

            if conditions:
                cursor.execute(
                    f"SELECT key FROM cache_meta WHERE {' AND '.join(conditions)}",
                    params
                )
                keys = [row[0] for row in cursor.fetchall()]

                for key in keys:
                    self.delete(key)

                logger.info(f"Invalidated {len(keys)} cache entries")

    def cleanup_expired(self) -> int:
        """清理过期缓存，返回删除数量"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT key FROM cache_meta
                WHERE expires_at < ?
            """, (datetime.now().isoformat(),))

            expired_keys = [row[0] for row in cursor.fetchall()]

            for key in expired_keys:
                self.delete(key)

            return len(expired_keys)

    def get_stats(self) -> Dict:
        """获取缓存统计"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 总记录数
            cursor.execute("SELECT COUNT(*) FROM cache_meta")
            total_entries = cursor.fetchone()[0]

            # 总行数
            cursor.execute("SELECT SUM(row_count) FROM cache_meta")
            total_rows = cursor.fetchone()[0] or 0

            # 按数据类型分组
            cursor.execute("""
                SELECT data_type, COUNT(*), SUM(row_count)
                FROM cache_meta
                GROUP BY data_type
            """)
            by_type = {
                row[0]: {"entries": row[1], "rows": row[2] or 0}
                for row in cursor.fetchall()
            }

            # Parquet 文件大小
            parquet_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.parquet"))

            return {
                "total_entries": total_entries,
                "total_rows": total_rows,
                "by_type": by_type,
                "parquet_size_bytes": parquet_size,
                "parquet_size_mb": round(parquet_size / 1024 / 1024, 2)
            }

    def refresh_stale_data(
        self,
        data_type: str,
        code: str,
        fetch_func,
        default_start: str
    ) -> pd.DataFrame:
        """
        获取数据，如果缓存过期则刷新

        Args:
            data_type: 数据类型
            code: 证券代码
            fetch_func: 数据获取函数 (返回 DataFrame)
            default_start: 默认开始日期

        Returns:
            DataFrame
        """
        # 尝试从缓存加载
        today = datetime.now().strftime('%Y-%m-%d')
        cached = self.get(data_type, code, default_start, today)

        if cached is not None:
            # 检查是否需要刷新 (缓存可能缺少最新数据)
            max_cached_date = cached.index.max().strftime('%Y-%m-%d')
            if max_cached_date < today:
                logger.info(f"Refreshing stale data: {code}")

                # 获取新数据
                fresh_data = fetch_func()

                if not fresh_data.empty:
                    # 合并数据
                    combined = pd.concat([cached, fresh_data])
                    combined = combined[~combined.index.duplicated(keep='last')]

                    # 重新缓存
                    self.set(data_type, code, default_start, today, combined)
                    return combined

            return cached

        # 缓存未命中，获取新数据
        logger.info(f"Cache miss, fetching fresh data: {code}")
        fresh_data = fetch_func()

        if not fresh_data.empty:
            self.set(data_type, code, default_start, today, fresh_data)

        return fresh_data
