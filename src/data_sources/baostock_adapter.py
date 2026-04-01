"""
Baostock 数据源适配器
"""
from .base import BaseDataFetcher
from typing import Dict, Optional, List
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaostockAdapter(BaseDataFetcher):
    """
    Baostock 适配器 - 主要负责指数和 ETF 历史行情

    优势：
    - 免费、稳定
    - 支持指数历史 K 线
    - 支持 ETF 历史行情

    劣势：
    - 不支持指数 PE/PB 数据
    - 财务数据有限
    """

    def __init__(self, cache_dir: str = "data/raw"):
        super().__init__(cache_dir)
        self.bs = None

    def connect(self) -> bool:
        """连接 Baostock"""
        try:
            import baostock as bs
            self.bs = bs
            lg = bs.login()
            if lg.error_code == '0':
                logger.info("Baostock 登录成功")
                self._connected = True
                return True
            else:
                logger.error(f"Baostock 登录失败：{lg.error_msg}")
                return False
        except ImportError:
            logger.error("Baostock 未安装")
            return False
        except Exception as e:
            logger.error(f"Baostock 连接失败：{e}")
            return False

    def disconnect(self):
        """断开 Baostock 连接"""
        if self.bs:
            self.bs.logout()
            self._connected = False
            logger.info("Baostock 已断开")

    def fetch_index_history(self, index_code: str, start_date: str = "20180101") -> pd.DataFrame:
        """获取指数历史行情"""
        if not self._connected or self.bs is None:
            return pd.DataFrame()

        try:
            # 转换日期格式
            start = self._format_date(start_date)
            end = datetime.now().strftime('%Y-%m-%d')

            rs = self.bs.query_index_history_k_data_plus(
                index_code,
                "date,code,open,high,low,close,volume,amount",
                start_date=start,
                end_date=end,
                frequency="d"
            )

            if rs.error_code != '0':
                logger.error(f"Baostock 获取指数行情失败 {index_code}: {rs.error_msg}")
                return pd.DataFrame()

            return self._parse_kline_result(rs, index_code)

        except Exception as e:
            logger.error(f"Baostock 获取指数行情异常 {index_code}: {e}")
            return pd.DataFrame()

    def fetch_etf_history(self, etf_code: str, start_date: str = "20180101") -> pd.DataFrame:
        """获取 ETF 历史行情"""
        if not self._connected or self.bs is None:
            return pd.DataFrame()

        try:
            start = self._format_date(start_date)
            end = datetime.now().strftime('%Y-%m-%d')

            # ETF 代码格式转换
            etf_code_clean = self._normalize_code(etf_code)

            rs = self.bs.query_history_k_data_plus(
                etf_code_clean,
                "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,pctChg",
                start_date=start,
                end_date=end,
                frequency="d",
                adjustflag="3"
            )

            if rs.error_code != '0':
                logger.error(f"Baostock 获取 ETF 行情失败 {etf_code}: {rs.error_msg}")
                return pd.DataFrame()

            return self._parse_kline_result(rs, etf_code)

        except Exception as e:
            logger.error(f"Baostock 获取 ETF 行情异常 {etf_code}: {e}")
            return pd.DataFrame()

    def fetch_index_pe_history(self, index_code: str) -> pd.DataFrame:
        """
        获取指数 PE 历史

        Note: Baostock 不支持指数 PE 数据，返回空 DataFrame
        """
        logger.warning(f"Baostock 不支持指数 PE 数据：{index_code}")
        return pd.DataFrame()

    def fetch_northbound_flow(self, start_date: str = "20250101") -> pd.DataFrame:
        """
        获取北向资金流向

        Note: Baostock 不支持北向资金数据，返回空 DataFrame
        建议使用 AKShare 适配器
        """
        logger.warning("Baostock 不支持北向资金数据，请使用 AKShare 适配器")
        return pd.DataFrame()

    def fetch_etf_shares(self, etf_code: str, start_date: str = "20250101") -> pd.DataFrame:
        """
        获取 ETF 份额数据

        Note: Baostock 不支持 ETF 份额数据，返回空 DataFrame
        建议使用 AKShare 适配器
        """
        logger.warning("Baostock 不支持 ETF 份额数据，请使用 AKShare 适配器")
        return pd.DataFrame()

    def get_current_price(self, index_code: str) -> Optional[float]:
        """获取当前价格（最新收盘价）"""
        df = self.fetch_index_history(index_code)
        if df.empty:
            return None
        return df['close'].iloc[-1]

    def check_health(self) -> Dict[str, bool]:
        """检查 Baostock 健康状态"""
        return {
            'connected': self._connected,
            'name': 'Baostock',
            'supports_pe': False,
            'supports_northbound': False,
            'supports_etf_shares': False
        }

    def _format_date(self, date_str: str) -> str:
        """转换日期格式为 Baostock 需要的格式"""
        if len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        return date_str

    def _normalize_code(self, code: str) -> str:
        """标准化代码格式"""
        # 移除分隔符
        clean_code = code.replace('.', '')
        if len(clean_code) == 6 and clean_code.isdigit():
            if clean_code.startswith(('51', '56', '58')):
                return f'sh{clean_code}'
            elif clean_code.startswith(('15', '16')):
                return f'sz{clean_code}'
        return code

    def _parse_kline_result(self, rs, code: str) -> pd.DataFrame:
        """解析 K 线数据结果"""
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            return pd.DataFrame()

        df = pd.DataFrame(data_list, columns=rs.fields)

        # 转换数值列
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'preclose', 'turn', 'pctChg']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()

        logger.info(f"Baostock 获取行情成功 {code}: {len(df)} rows")
        return df
