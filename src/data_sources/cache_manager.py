"""
数据缓存管理器 - 支持 SQLite 和 Parquet 双缓存
"""
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


class CacheManager:
    """
    数据缓存管理器

    支持：
    - Parquet 文件缓存 (适合时间序列数据)
    - SQLite 缓存 (适合结构化数据)
    - 缓存过期策略
    - 缓存刷新机制
    """

    def __init__(self,
                 parquet_dir: str = "data/cache/parquet",
                 sqlite_path: str = "data/cache/metadata.db",
                 default_ttl_hours: int = 24):
        self.parquet_dir = Path(parquet_dir)
        self.parquet_dir.mkdir(parents=True, exist_ok=True)

        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        self.default_ttl_hours = default_ttl_hours
        self._metadata_cache: Dict[str, dict] = {}

        self._init_metadata()

    def _init_metadata(self):
        """初始化元数据表"""
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    row_count INTEGER,
                    size_bytes INTEGER,
                    checksum TEXT
                )
            ''')
            conn.commit()

    def _generate_key(self, source: str, data_type: str, params: Dict) -> str:
        """生成缓存键"""
        param_str = json.dumps(params, sort_keys=True)
        raw_key = f"{source}:{data_type}:{param_str}"
        return hashlib.md5(raw_key.encode()).hexdigest()[:16]

    def get_parquet_path(self, key: str) -> Path:
        """获取 Parquet 文件路径"""
        return self.parquet_dir / f"{key}.parquet"

    def _get_metadata(self, key: str) -> Optional[dict]:
        """获取缓存元数据"""
        if key in self._metadata_cache:
            return self._metadata_cache[key]

        with sqlite3.connect(self.sqlite_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM cache_metadata WHERE key = ?',
                (key,)
            )
            row = cursor.fetchone()

            if row:
                metadata = dict(row)
                self._metadata_cache[key] = metadata
                return metadata

        return None

    def _update_metadata(self, key: str, df: pd.DataFrame, ttl_hours: Optional[int] = None):
        """更新缓存元数据"""
        now = datetime.now()
        expires_at = now + timedelta(hours=ttl_hours or self.default_ttl_hours)

        # 计算 checksum
        checksum = hashlib.md5(pd.util.hash_pandas_object(df).values).hexdigest()

        # 获取文件大小
        parquet_file = self.get_parquet_path(key)
        size_bytes = parquet_file.stat().st_size if parquet_file.exists() else 0

        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO cache_metadata
                (key, created_at, updated_at, expires_at, row_count, size_bytes, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                key,
                now.isoformat(),
                now.isoformat(),
                expires_at.isoformat(),
                len(df),
                size_bytes,
                checksum
            ))
            conn.commit()

        self._metadata_cache[key] = {
            'key': key,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'expires_at': expires_at.isoformat(),
            'row_count': len(df),
            'size_bytes': size_bytes,
            'checksum': checksum
        }

    def is_valid(self, key: str, ttl_hours: Optional[int] = None) -> bool:
        """检查缓存是否有效"""
        metadata = self._get_metadata(key)
        if not metadata:
            return False

        expires_at = datetime.fromisoformat(metadata['expires_at'])
        if datetime.now() > expires_at:
            logger.info(f"Cache expired: {key}")
            return False

        parquet_file = self.get_parquet_path(key)
        if not parquet_file.exists():
            logger.warning(f"Cache file missing: {key}")
            return False

        return True

    def read(self, key: str) -> Optional[pd.DataFrame]:
        """读取缓存"""
        if not self.is_valid(key):
            return None

        parquet_file = self.get_parquet_path(key)
        try:
            df = pd.read_parquet(parquet_file)
            logger.info(f"Cache hit: {key} ({len(df)} rows)")
            return df
        except Exception as e:
            logger.warning(f"Cache read failed: {key}, error: {e}")
            return None

    def write(self, key: str, df: pd.DataFrame, ttl_hours: Optional[int] = None):
        """写入缓存"""
        if df.empty:
            logger.warning(f"Attempted to cache empty DataFrame: {key}")
            return

        parquet_file = self.get_parquet_path(key)
        try:
            df.to_parquet(parquet_file, index=True)
            self._update_metadata(key, df, ttl_hours)
            logger.info(f"Cache saved: {key} ({len(df)} rows)")
        except Exception as e:
            logger.error(f"Cache write failed: {key}, error: {e}")

    def invalidate(self, key: str):
        """使缓存失效"""
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute('DELETE FROM cache_metadata WHERE key = ?', (key,))
            conn.commit()

        parquet_file = self.get_parquet_path(key)
        if parquet_file.exists():
            parquet_file.unlink()

        self._metadata_cache.pop(key, None)
        logger.info(f"Cache invalidated: {key}")

    def invalidate_pattern(self, pattern: str):
        """批量使缓存失效 (支持通配符)"""
        import fnmatch

        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.execute('SELECT key FROM cache_metadata')
            keys = [row[0] for row in cursor.fetchall()]

            for key in keys:
                if fnmatch.fnmatch(key, pattern):
                    self.invalidate(key)

        logger.info(f"Cache invalidated for pattern: {pattern}")

    def get_stats(self) -> Dict:
        """获取缓存统计"""
        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total_keys,
                    SUM(row_count) as total_rows,
                    SUM(size_bytes) as total_size,
                    AVG(row_count) as avg_rows,
                    MIN(expires_at) as earliest_expiry,
                    MAX(expires_at) as latest_expiry
                FROM cache_metadata
            ''')
            row = cursor.fetchone()

            return {
                'total_keys': row[0] or 0,
                'total_rows': row[1] or 0,
                'total_size_mb': (row[2] or 0) / 1024 / 1024,
                'avg_rows': row[4] or 0,
                'earliest_expiry': row[5],
                'latest_expiry': row[6]
            }

    def cleanup_expired(self) -> int:
        """清理过期缓存"""
        now = datetime.now().isoformat()

        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.execute(
                'SELECT key FROM cache_metadata WHERE expires_at < ?',
                (now,)
            )
            expired_keys = [row[0] for row in cursor.fetchall()]

        for key in expired_keys:
            self.invalidate(key)

        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        return len(expired_keys)
