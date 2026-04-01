"""
AKShare 数据源适配器
"""
import pandas as pd
from datetime import datetime
from typing import Optional, Dict
import logging

from .base import BaseDataFetcher, DataSourceConfig

logger = logging.getLogger(__name__)


class AKShareAdapter(BaseDataFetcher):
    """
    AKShare 数据适配器

    支持:
    - ETF 历史行情 (Sina 接口)
    - 北向资金流向
    - ETF 份额数据
    """

    def __init__(self):
        super().__init__(DataSourceConfig(
            name="akshare",
            priority=2,
            enabled=True
        ))
        self._initialized = True

    def fetch_price_history(
        self,
        code: str,
        start_date: str,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """获取 ETF 历史行情 (使用 Sina 接口)"""
        try:
            import akshare as ak

            # 转换代码格式
            etf_code = self._normalize_etf_code(code)
            logger.info(f"Fetching ETF data from AKShare: {etf_code}")

            df = ak.fund_etf_hist_sina(symbol=etf_code)

            if df.empty:
                logger.warning(f"AKShare returned empty data for {etf_code}")
                return pd.DataFrame()

            return self._clean_kline_data(df)

        except Exception as e:
            logger.error(f"AKShare fetch failed {code}: {e}")
            return pd.DataFrame()

    def _normalize_etf_code(self, code: str) -> str:
        """标准化 ETF 代码格式"""
        code_clean = code.replace('.', '')

        if len(code_clean) == 6 and code_clean.isdigit():
            if code_clean.startswith(('51', '56', '58')):
                return f'sh{code_clean}'
            elif code_clean.startswith(('15', '16')):
                return f'sz{code_clean}'

        return code_clean

    def _clean_kline_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗 K 线数据"""
        # 重命名列
        df = df.rename(columns={
            'date': 'date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'amount': 'amount'
        })

        # 日期转换
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()

        # 数值转换
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 添加 preclose
        if 'preclose' not in df.columns:
            df['preclose'] = df['close'].shift(1)

        return df

    def fetch_index_pe_history(
        self,
        index_code: str,
        start_date: str,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取指数 PE 历史 (使用 AKShare 指数估值接口)
        """
        try:
            import akshare as ak

            df = ak.index_value_hist_funddb(symbol=index_code)

            if df is None or df.empty:
                logger.warning(f"AKShare index PE data empty: {index_code}")
                return pd.DataFrame()

            df = df.rename(columns={
                'trade_date': 'date',
                'pe': 'pe',
                'pb': 'pb',
                'dividend_yield': 'dividend_yield'
            })

            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()

            logger.info(f"AKShare index PE data: {index_code} ({len(df)} rows)")
            return df[['pe', 'pb', 'dividend_yield']]

        except Exception as e:
            logger.warning(f"AKShare index PE fetch failed {index_code}: {e}")
            return pd.DataFrame()

    def fetch_northbound_flow(
        self,
        start_date: str
    ) -> pd.DataFrame:
        """获取北向资金流向数据"""
        try:
            import akshare as ak

            df = ak.stock_hsgt_hist_em(symbol="北向资金")

            if df is None or df.empty:
                return pd.DataFrame()

            df = df.rename(columns={
                "日期": "date",
                "当日成交净买额": "net_flow",
                "买入成交额": "buy_amount",
                "卖出成交额": "sell_amount",
            })

            for col in ['net_flow', 'buy_amount', 'sell_amount']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce') / 1e8

            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()

            start_ts = pd.to_datetime(start_date, errors='coerce')
            if start_ts is not None:
                df = df[df.index >= start_ts]

            logger.info(f"Northbound flow data: {len(df)} rows")
            return df

        except Exception as e:
            logger.error(f"Northbound flow fetch failed: {e}")
            return pd.DataFrame()

    def fetch_etf_shares(
        self,
        etf_code: str,
        start_date: str
    ) -> pd.DataFrame:
        """获取 ETF 份额数据"""
        try:
            import akshare as ak

            if etf_code.startswith('51') or etf_code.startswith('58'):
                df = ak.fund_etf_scale_sse()
                market = 'SSE'
            elif etf_code.startswith('15'):
                df = ak.fund_etf_scale_szse()
                market = 'SZSE'
            else:
                logger.warning(f"Unknown ETF market: {etf_code}")
                return pd.DataFrame()

            if df is None or df.empty:
                return pd.DataFrame()

            df = df[df['基金代码'] == etf_code.replace('.', '')].copy()

            if df.empty:
                logger.warning(f"ETF shares not found: {etf_code}")
                return pd.DataFrame()

            date_col = next((c for c in ['统计日期', '交易日期', '日期'] if c in df.columns), None)
            shares_col = next((c for c in ['基金份额', '份额'] if c in df.columns), None)

            if shares_col is None:
                return pd.DataFrame()

            result = pd.DataFrame()
            result['date'] = pd.to_datetime(df[date_col]) if date_col else pd.Timestamp.now()
            result['shares'] = pd.to_numeric(df[shares_col], errors='coerce')
            result = result.dropna(subset=['date', 'shares'])

            if result.empty:
                return pd.DataFrame()

            result = result.set_index('date').sort_index()
            result['shares_change_1d'] = result['shares'].pct_change().fillna(0)
            result['shares_change_5d'] = result['shares'].pct_change(5).fillna(0)
            result['shares_change_20d'] = result['shares'].pct_change(20).fillna(0)

            logger.info(f"ETF shares data {etf_code} ({market}): {len(result)} rows")
            return result

        except Exception as e:
            logger.error(f"ETF shares fetch failed {etf_code}: {e}")
            return pd.DataFrame()

    def fetch_fundamental_data(
        self,
        code: str,
        report_date: Optional[str] = None
    ) -> Dict:
        """获取基本面数据"""
        try:
            import akshare as ak
            df = ak.stock_financial_analysis_indicator(symbol=code)

            if df is None or df.empty:
                return {}

            latest = df.iloc[0].to_dict()

            return {
                'roe': float(latest.get('净资产收益率 (%)', 0)),
                'roa': float(latest.get('总资产报酬率 (%)', 0)),
                'gross_margin': float(latest.get('销售毛利率 (%)', 0)),
                'net_margin': float(latest.get('销售净利率 (%)', 0)),
                'debt_ratio': float(latest.get('资产负债率 (%)', 0)),
                'current_ratio': float(latest.get('流动比率', 0)),
                'revenue_growth': float(latest.get('营业收入增长率 (%)', 0)),
                'profit_growth': float(latest.get('净利润增长率 (%)', 0))
            }

        except Exception as e:
            logger.warning(f"Fundamental data fetch failed {code}: {e}")
            return {}
