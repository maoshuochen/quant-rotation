"""
Tushare Pro 数据源适配器
需要积分才能访问完整数据
"""
import pandas as pd
from datetime import datetime
from typing import Optional, Dict
import logging
import os

from .base import BaseDataFetcher, DataSourceConfig

logger = logging.getLogger(__name__)


class TushareAdapter(BaseDataFetcher):
    """
    Tushare Pro 数据适配器

    支持:
    - 指数历史行情
    - 指数 PE/PB 估值
    - 基本面数据

    需要：TUSHARE_TOKEN 环境变量
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get('TUSHARE_TOKEN')
        self.ts = None

        super().__init__(DataSourceConfig(
            name="tushare",
            priority=1,
            enabled=bool(self.token)
        ))

        if self.token:
            self._init_tushare()

    def _init_tushare(self):
        """初始化 Tushare 连接"""
        try:
            import tushare as ts
            ts.set_token(self.token)
            self.ts = ts.pro_api()
            self._initialized = True
            logger.info("Tushare Pro 初始化成功")
        except ImportError:
            logger.error("Tushare 未安装：pip install tushare")
        except Exception as e:
            logger.error(f"Tushare 初始化失败：{e}")
            self._initialized = False

    def fetch_price_history(
        self,
        code: str,
        start_date: str,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """获取指数历史行情"""
        if self.ts is None:
            return pd.DataFrame()

        try:
            start = self._normalize_date(start_date)
            end = self._normalize_date(end_date or datetime.now().strftime('%Y%m%d'))
            ts_code = self._convert_code_format(code)

            df = self.ts.index_daily(
                ts_code=ts_code,
                start_date=start,
                end_date=end
            )

            if df.empty:
                logger.warning(f"Tushare index data empty: {code}")
                return pd.DataFrame()

            return self._clean_index_data(df)

        except Exception as e:
            logger.error(f"Tushare fetch failed {code}: {e}")
            return pd.DataFrame()

    def fetch_index_pe_history(
        self,
        index_code: str,
        start_date: str,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """获取指数 PE/PB 历史数据"""
        if self.ts is None:
            return pd.DataFrame()

        try:
            start = self._normalize_date(start_date)
            end = self._normalize_date(end_date or datetime.now().strftime('%Y%m%d'))
            ts_code = self._convert_code_format(index_code)

            df = self.ts.index_dailybasic(
                ts_code=ts_code,
                start_date=start,
                end_date=end,
                fields='ts_code,trade_date,pe,peg,pb,ps,dv_ratio'
            )

            if df is None or df.empty:
                logger.warning(f"Tushare PE data empty: {index_code}")
                return pd.DataFrame()

            df = df.rename(columns={
                'trade_date': 'date',
                'pe': 'pe',
                'pb': 'pb',
                'dv_ratio': 'dividend_yield'
            })

            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()

            logger.info(f"Tushare PE data: {index_code} ({len(df)} rows)")
            return df[['pe', 'pb', 'dividend_yield']]

        except Exception as e:
            logger.warning(f"Tushare PE fetch failed {index_code}: {e}")
            return pd.DataFrame()

    def fetch_northbound_flow(self, start_date: str) -> pd.DataFrame:
        """Tushare 不支持北向资金数据"""
        logger.warning("Tushare 不支持北向资金数据")
        return pd.DataFrame()

    def fetch_etf_shares(self, etf_code: str, start_date: str) -> pd.DataFrame:
        """Tushare 不支持 ETF 份额数据"""
        logger.warning("Tushare 不支持 ETF 份额数据")
        return pd.DataFrame()

    def fetch_fundamental_data(
        self,
        code: str,
        report_date: Optional[str] = None
    ) -> Dict:
        """获取基本面数据"""
        if self.ts is None:
            return {}

        try:
            ts_code = self._convert_code_format(code)
            year = report_date[:4] if report_date else str(datetime.now().year)

            df = self.ts.fina_indicator(
                ts_code=ts_code,
                start_date=f"{year}0101",
                end_date=f"{year}1231"
            )

            if df.empty:
                return {}

            latest = df.iloc[0].to_dict()

            return {
                'roe': float(latest.get('roe', 0)),
                'roa': float(latest.get('roa', 0)),
                'gross_margin': float(latest.get('gross_profit_margin', 0)),
                'net_margin': float(latest.get('net_profit_margin', 0)),
                'debt_ratio': float(latest.get('debt_to_assets', 0)),
                'current_ratio': float(latest.get('current_ratio', 0)),
                'revenue_growth': float(latest.get('op_yoy', 0)),
                'profit_growth': float(latest.get('np_yoy', 0))
            }

        except Exception as e:
            logger.warning(f"Tushare fundamental fetch failed {code}: {e}")
            return {}

    def _convert_code_format(self, code: str) -> str:
        """转换代码格式为 Tushare 格式"""
        if '.' in code:
            return code.upper()
        return f"{code}.SH"

    def _normalize_date(self, date_str: str) -> str:
        """标准化日期格式为 YYYYMMDD"""
        if len(date_str) == 8:
            return date_str
        if '-' in date_str:
            return date_str.replace('-', '')
        return date_str

    def _clean_index_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗指数数据"""
        df = df.rename(columns={
            'trade_date': 'date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'vol': 'volume',
            'amount': 'amount'
        })

        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()

        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        if 'pre_close' in df.columns:
            df['preclose'] = pd.to_numeric(df['pre_close'], errors='coerce')
        else:
            df['preclose'] = df['close'].shift(1)

        return df
