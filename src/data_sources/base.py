"""
数据源抽象基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, List
import pandas as pd
from pathlib import Path
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DataSourceConfig:
    """数据源配置"""
    name: str
    priority: int = 1
    enabled: bool = True
    rate_limit: Optional[float] = None
    timeout: int = 30


class BaseDataFetcher(ABC):
    """数据获取器抽象基类"""

    def __init__(self, config: Optional[DataSourceConfig] = None):
        self.config = config or DataSourceConfig(name=self.__class__.__name__)
        self._initialized = False

    @abstractmethod
    def fetch_price_history(
        self,
        code: str,
        start_date: str,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """获取历史行情数据"""
        pass

    @abstractmethod
    def fetch_index_pe_history(
        self,
        index_code: str,
        start_date: str,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """获取指数 PE/PB 历史数据"""
        pass

    @abstractmethod
    def fetch_northbound_flow(self, start_date: str) -> pd.DataFrame:
        """获取北向资金流向数据"""
        pass

    @abstractmethod
    def fetch_etf_shares(self, etf_code: str, start_date: str) -> pd.DataFrame:
        """获取 ETF 份额数据"""
        pass

    @abstractmethod
    def fetch_fundamental_data(self, code: str, report_date: Optional[str] = None) -> Dict:
        """获取基本面数据"""
        pass

    @property
    def source_name(self) -> str:
        """返回数据源名称"""
        return self.config.name

    @property
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        return self.config.enabled and self._initialized


class DataSourceRegistry:
    """数据源注册中心"""

    def __init__(self):
        self._sources: Dict[str, BaseDataFetcher] = {}
        self._priority: List[str] = []

    def register(self, name: str, fetcher: BaseDataFetcher, priority: int = 0):
        """注册数据源"""
        self._sources[name] = fetcher
        self._priority.append(name)
        self._priority.sort(key=lambda x: priority if self._sources[x] == fetcher else 999)

    def get_source(self, name: str) -> Optional[BaseDataFetcher]:
        """获取指定数据源"""
        return self._sources.get(name)

    def get_available_source(self) -> Optional[BaseDataFetcher]:
        """获取第一个可用的数据源"""
        for name in self._priority:
            source = self._sources.get(name)
            if source and source.is_available:
                return source
        return None
