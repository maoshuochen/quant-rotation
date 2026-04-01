"""
数据源抽象基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, List
import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class BaseDataFetcher(ABC):
    """数据获取器抽象基类"""

    def __init__(self, cache_dir: str = "data/raw"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._connected = False

    @abstractmethod
    def fetch_index_history(self, index_code: str, start_date: str = "20180101") -> pd.DataFrame:
        """获取指数历史行情"""
        pass

    @abstractmethod
    def fetch_etf_history(self, etf_code: str, start_date: str = "20180101") -> pd.DataFrame:
        """获取 ETF 历史行情"""
        pass

    @abstractmethod
    def fetch_index_pe_history(self, index_code: str) -> pd.DataFrame:
        """获取指数 PE 历史"""
        pass

    @abstractmethod
    def fetch_northbound_flow(self, start_date: str = "20250101") -> pd.DataFrame:
        """获取北向资金流向"""
        pass

    @abstractmethod
    def fetch_etf_shares(self, etf_code: str, start_date: str = "20250101") -> pd.DataFrame:
        """获取 ETF 份额数据"""
        pass

    @abstractmethod
    def get_current_price(self, index_code: str) -> Optional[float]:
        """获取当前价格"""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """连接数据源"""
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    def check_health(self) -> Dict[str, bool]:
        """检查数据源健康状态"""
        return {
            'connected': self._connected,
            'name': self.__class__.__name__
        }


class DataSourceRegistry:
    """数据源注册中心 - 支持自动切换"""

    def __init__(self):
        self._sources: Dict[str, BaseDataFetcher] = {}
        self._priority: List[str] = []  # 优先级列表，靠前的优先使用
        self._current_source: Optional[str] = None

    def register(self, name: str, fetcher: BaseDataFetcher, priority: int = 0):
        """注册数据源"""
        self._sources[name] = fetcher
        self._priority.append(name)
        self._priority.sort(key=lambda x: priority if self._sources[x] == fetcher else 999)
        logger.info(f"Registered data source: {name}")

    def get_source(self, name: str) -> Optional[BaseDataFetcher]:
        """获取指定数据源"""
        return self._sources.get(name)

    def get_available_source(self) -> Optional[BaseDataFetcher]:
        """获取第一个可用的数据源"""
        for name in self._priority:
            source = self._sources.get(name)
            if source and source._connected:
                return source
        return None

    def set_primary(self, name: str):
        """设置主要数据源"""
        if name in self._sources:
            self._priority.remove(name)
            self._priority.insert(0, name)
            logger.info(f"Set primary data source: {name}")

    def check_all_health(self) -> Dict[str, Dict]:
        """检查所有数据源健康状态"""
        return {
            name: source.check_health()
            for name, source in self._sources.items()
        }
