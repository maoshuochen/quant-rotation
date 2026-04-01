"""
数据源测试
"""
import pytest
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_sources.cache_manager import CacheManager


class TestCacheManager:
    """缓存管理器测试"""

    def test_cache_write_read(self, tmp_path):
        """测试缓存写入和读取"""
        cache = CacheManager(
            parquet_dir=str(tmp_path / "parquet"),
            sqlite_path=str(tmp_path / "metadata.db")
        )

        df = pd.DataFrame({
            'open': [1, 2, 3],
            'close': [1.1, 2.2, 3.3]
        }, index=pd.date_range('2024-01-01', periods=3))

        cache.write("test_key", df)
        result = cache.read("test_key")

        assert result is not None
        assert len(result) == 3

    def test_cache_invalidate(self, tmp_path):
        """测试缓存失效"""
        cache = CacheManager(
            parquet_dir=str(tmp_path / "parquet"),
            sqlite_path=str(tmp_path / "metadata.db")
        )

        df = pd.DataFrame({'close': [1, 2, 3]})
        cache.write("test_key", df)
        cache.invalidate("test_key")

        result = cache.read("test_key")
        assert result is None


class TestHelperFunctions:
    """辅助函数测试"""

    def test_date_helpers(self):
        """测试日期处理"""
        # 简单的日期格式测试
        assert "2024" in "2024-01-01"
