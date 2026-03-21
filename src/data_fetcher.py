"""
数据获取模块 - 支持 Tushare 和 AKShare
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import logging
import time
from typing import Optional
import yaml
import os

logger = logging.getLogger(__name__)


class TushareClient:
    """Tushare 客户端"""
    
    def __init__(self, token: str):
        self.token = token
        self.pro = None
        self._init_pro()
    
    def _init_pro(self):
        """初始化 Tushare Pro"""
        try:
            import tushare as ts
            ts.set_token(self.token)
            self.pro = ts.pro_api()
            logger.info("Tushare 初始化成功")
        except ImportError:
            logger.warning("Tushare 未安装，运行：pip install tushare")
        except Exception as e:
            logger.error(f"Tushare 初始化失败：{e}")
    
    def fetch_index_daily(self, ts_code: str, start_date: str = "20180101") -> pd.DataFrame:
        """获取指数日线行情"""
        if self.pro is None:
            return pd.DataFrame()
        
        try:
            df = self.pro.index_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=datetime.now().strftime('%Y%m%d')
            )
            
            df = df.rename(columns={
                'trade_date': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'vol': 'volume'
            })
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
            
            return df
            
        except Exception as e:
            logger.error(f"Tushare 获取行情失败 {ts_code}: {e}")
            return pd.DataFrame()


def load_secrets() -> dict:
    """加载敏感配置"""
    secrets_path = Path(__file__).parent.parent / 'config' / 'secrets.yaml'
    
    if secrets_path.exists():
        with open(secrets_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    return {}


class IndexDataFetcher:
    """指数数据获取器 - 支持 Tushare 和 AKShare"""
    
    def __init__(self, cache_dir: str = "data/raw", use_tushare: bool = True):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化 Tushare
        self.tushare_client = None
        if use_tushare:
            secrets = load_secrets()
            tushare_token = secrets.get('tushare', {}).get('token', '')
            if tushare_token:
                self.tushare_client = TushareClient(tushare_token)
                logger.info("使用 Tushare 作为主要数据源")
            else:
                logger.warning("Tushare Token 未配置，使用 AKShare")
    
    def fetch_index_history(self, index_code: str, start_date: str = "20180101") -> pd.DataFrame:
        """获取指数历史行情"""
        cache_file = self.cache_dir / f"{index_code}_history.parquet"
        
        # 检查缓存
        if cache_file.exists():
            df = pd.read_parquet(cache_file)
            logger.info(f"Loaded cached data for {index_code}: {len(df)} rows")
            return df
        
        df = None
        
        # 优先使用 Tushare
        if self.tushare_client and self.tushare_client.pro:
            logger.info(f"Fetching from Tushare: {index_code}")
            df = self.tushare_client.fetch_index_daily(index_code, start_date)
            
            if not df.empty:
                logger.info(f"Tushare success: {len(df)} rows")
                df.to_parquet(cache_file)
                return df
        
        # Tushare 失败则降级到 AKShare
        logger.info(f"Tushare failed/unavailable, fallback to AKShare: {index_code}")
        
        try:
            import akshare as ak
            
            for attempt in range(3):
                try:
                    df = ak.index_zh_a_hist(
                        symbol=index_code,
                        period="daily",
                        start_date=start_date
                    )
                    break
                except Exception as e:
                    if attempt < 2:
                        logger.warning(f"AKShare retry ({attempt+1}/3): {e}")
                        time.sleep(2)
                    else:
                        raise
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume',
                '成交额': 'amount'
            })
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
            
            df.to_parquet(cache_file)
            logger.info(f"AKShare cached: {len(df)} rows")
            
            return df
            
        except Exception as e:
            logger.error(f"AKShare failed: {e}")
            return pd.DataFrame()
    
    def fetch_index_pe_history(self, index_code: str) -> pd.DataFrame:
        """获取指数 PE 历史"""
        cache_file = self.cache_dir / f"{index_code}_pe.parquet"
        
        if cache_file.exists():
            df = pd.read_parquet(cache_file)
            logger.info(f"Loaded cached PE data for {index_code}: {len(df)} rows")
            return df
        
        # 提取指数代码数字部分
        index_num = index_code.split('.')[0] if '.' in index_code else index_code
        
        try:
            import akshare as ak
            
            df = None
            for attempt in range(3):
                try:
                    df = ak.stock_zh_index_value_csindex(symbol=index_num)
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(2)
                    else:
                        raise
            
            if df is None or df.empty:
                logger.warning(f"No PE data for {index_code}")
                return pd.DataFrame()
            
            df = df.rename(columns={
                '日期': 'date',
                '市盈率 1': 'pe',
                '市盈率 2': 'pe_ttm',
                '股息率 1': 'dividend_yield',
                '股息率 2': 'dividend_yield_ttm',
            })
            
            if 'date' not in df.columns or 'pe' not in df.columns:
                return pd.DataFrame()
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index(ascending=False)
            
            df.to_parquet(cache_file)
            logger.info(f"PE cached: {len(df)} rows")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch PE for {index_code}: {e}")
            return pd.DataFrame()
    
    def get_current_pe(self, index_code: str) -> Optional[float]:
        """获取当前 PE"""
        df = self.fetch_index_pe_history(index_code)
        if df.empty:
            return None
        return df['pe'].iloc[0]
    
    def get_current_pb(self, index_code: str) -> Optional[float]:
        """获取当前 PB"""
        df = self.fetch_index_pe_history(index_code)
        if df.empty:
            return None
        # PB 需要从其他接口获取，这里简化处理
        return None
    
    def refresh_cache(self, index_codes: list):
        """刷新所有指数缓存"""
        for code in index_codes:
            logger.info(f"Refreshing cache for {code}")
            self.fetch_index_history(code)
            self.fetch_index_pe_history(code)
