"""
数据源测试
"""
import pytest
import pandas as pd
import sys
sys.path.insert(0, 'src')

from data_sources import BaostockAdapter, AKShareAdapter, CacheManager


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


class TestBaostockAdapter:
    """Baostock 适配器测试"""

    def test_normalize_date(self):
        """测试日期标准化"""
        adapter = BaostockAdapter()

        assert adapter._normalize_date("20240101") == "2024-01-01"
        assert adapter._normalize_date("2024-01-01") == "2024-01-01"

    def test_is_index_code(self):
        """测试指数代码识别"""
        adapter = BaostockAdapter()

        assert adapter._is_index_code("000300.SH") is True
        assert adapter._is_index_code("510300") is False


class TestAKShareAdapter:
    """AKShare 适配器测试"""

    def test_normalize_etf_code(self):
        """测试 ETF 代码标准化"""
        adapter = AKShareAdapter()

        assert adapter._normalize_etf_code("510300") == "sh510300"
        assert adapter._normalize_etf_code("159999") == "sz159999"
