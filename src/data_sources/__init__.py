"""
多数据源适配层
支持 Baostock, Tushare, AKShare 等数据源
"""
from .base import BaseDataFetcher, DataSourceConfig, DataSourceRegistry
from .baostock_adapter import BaostockAdapter
from .tushare_adapter import TushareAdapter
from .akshare_adapter import AKShareAdapter
from .cache_manager import CacheManager
from .unified_fetcher import UnifiedDataFetcher

__all__ = [
    'BaseDataFetcher',
    'DataSourceConfig',
    'DataSourceRegistry',
    'BaostockAdapter',
    'TushareAdapter',
    'AKShareAdapter',
    'CacheManager',
    'UnifiedDataFetcher'
]
