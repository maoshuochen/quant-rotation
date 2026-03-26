"""
混合数据获取器 - Baostock + AKShare
支持沪市和深市 ETF 数据
"""
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class HybridDataFetcher:
    """
    混合数据获取器
    
    数据源策略:
    - 沪市 ETF (51xxxx/58xxxx): Baostock
    - 深市 ETF (15xxxx/16xxxx): AKShare Sina 接口
    - 北向资金：AKShare 东方财富
    - ETF 份额：AKShare
    """
    
    def __init__(self, cache_dir: str = "data/raw"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.bs = None
        self._init_baostock()
    
    def _init_baostock(self):
        """初始化 Baostock"""
        try:
            import baostock as bs
            self.bs = bs
            lg = bs.login()
            if lg.error_code == '0':
                logger.info("Baostock 登录成功")
            else:
                logger.error(f"Baostock 登录失败：{lg.error_msg}")
        except ImportError:
            logger.warning("Baostock 未安装，将完全使用 AKShare")
            self.bs = None
        except Exception as e:
            logger.error(f"Baostock 初始化失败：{e}")
            self.bs = None
    
    def _get_cache_file(self, code: str, data_type: str = "history") -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{code.replace('.', '_')}_{data_type}.parquet"
    
    def _detect_market(self, code: str) -> str:
        """
        判断 ETF 市场
        
        Returns:
            'sh' | 'sz' | 'unknown'
        """
        code_clean = code.replace('.', '').replace('sh', '').replace('sz', '')
        
        if len(code_clean) != 6 or not code_clean.isdigit():
            return 'unknown'
        
        # 沪市：51xxxx (ETF), 56xxxx, 58xxxx (科创板)
        if code_clean.startswith(('51', '56', '58')):
            return 'sh'
        # 深市：15xxxx, 16xxxx
        elif code_clean.startswith(('15', '16')):
            return 'sz'
        else:
            return 'unknown'
    
    def fetch_etf_history(self, etf_code: str, start_date: str = "20180101", force_refresh: bool = False) -> pd.DataFrame:
        """
        获取 ETF 历史行情 (自动选择数据源)
        
        Args:
            etf_code: ETF 代码 (如 510300 或 159915)
            start_date: 开始日期 (YYYYMMDD)
            force_refresh: 是否强制刷新缓存
            
        Returns:
            DataFrame with columns: open, high, low, close, volume, amount, preclose
        """
        cache_file = self._get_cache_file(etf_code, "etf_history")
        
        if cache_file.exists() and not force_refresh:
            try:
                df = pd.read_parquet(cache_file)
                logger.info(f"Loaded cached ETF data for {etf_code}: {len(df)} rows")
                return df
            except Exception as e:
                logger.warning(f"Cache read failed, will refresh: {e}")
        
        market = self._detect_market(etf_code)
        logger.info(f"Fetching ETF {etf_code} from {market.upper() if market != 'unknown' else 'AKShare'}")
        
        df = pd.DataFrame()
        
        if market == 'sh' and self.bs is not None:
            # 沪市 ETF 使用 Baostock
            df = self._fetch_etf_baostock(etf_code, start_date)
        else:
            # 深市 ETF 或 Baostock 不可用时使用 AKShare
            df = self._fetch_etf_akshare(etf_code, start_date)
        
        if not df.empty:
            df.to_parquet(cache_file)
            logger.info(f"ETF cached: {len(df)} rows ({df.index.min().date()} ~ {df.index.max().date()})")
        
        return df
    
    def _fetch_etf_baostock(self, etf_code: str, start_date: str) -> pd.DataFrame:
        """使用 Baostock 获取沪市 ETF 数据"""
        if self.bs is None:
            return pd.DataFrame()
        
        try:
            # 转换代码格式 (510300 -> sh.510300)
            code_clean = etf_code.replace('.', '')
            if not code_clean.startswith('sh.'):
                code_clean = f'sh.{code_clean}'
            
            start = start_date
            if len(start_date) == 8:
                start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            
            end = datetime.now().strftime('%Y-%m-%d')
            
            rs = self.bs.query_history_k_data_plus(
                code_clean,
                "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg",
                start_date=start,
                end_date=end,
                frequency="d",
                adjustflag="3"  # 不复权
            )
            
            if rs.error_code != '0':
                logger.error(f"Baostock 获取 ETF 行情失败 {etf_code}: {rs.error_msg}")
                return pd.DataFrame()
            
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                logger.warning(f"Baostock 返回空数据 {etf_code}")
                return pd.DataFrame()
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 转换类型
            numeric_cols = ['open', 'high', 'low', 'close', 'preclose', 'volume', 'amount', 'turn', 'pctChg']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
            
            logger.info(f"Baostock 获取 ETF 成功 {etf_code}: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Baostock 获取 ETF 异常 {etf_code}: {e}")
            return pd.DataFrame()
    
    def _fetch_etf_akshare(self, etf_code: str, start_date: str) -> pd.DataFrame:
        """使用 AKShare Sina 接口获取 ETF 数据 (支持深市)"""
        try:
            import akshare as ak
            
            # 转换代码格式 (510300 -> sh510300, 159915 -> sz159915)
            code_clean = etf_code.replace('.', '')
            if len(code_clean) == 6 and code_clean.isdigit():
                if code_clean.startswith(('51', '56', '58')):
                    code_clean = f'sh{code_clean}'
                elif code_clean.startswith(('15', '16')):
                    code_clean = f'sz{code_clean}'
            
            logger.info(f"AKShare Sina fetching: {code_clean}")
            
            df = ak.fund_etf_hist_sina(symbol=code_clean)
            
            if df.empty:
                logger.warning(f"AKShare 返回空数据 {code_clean}")
                return pd.DataFrame()
            
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
            
            # 转换类型
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
            
            # 添加 preclose
            df['preclose'] = df['close'].shift(1)
            
            logger.info(f"AKShare 获取 ETF 成功 {etf_code}: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"AKShare 获取 ETF 失败 {etf_code}: {e}")
            return pd.DataFrame()
    
    def fetch_northbound_flow(self, start_date: str = "20250101") -> pd.DataFrame:
        """获取北向资金流向数据"""
        try:
            import akshare as ak
            
            df = ak.stock_hsgt_fund_flow_summary_em()
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            df = df[df['资金方向'] == '北向'].copy()
            
            if df.empty:
                return pd.DataFrame()
            
            df = df.rename(columns={
                '交易日': 'date',
                '成交净买额': 'net_flow'
            })
            
            df['date'] = pd.to_datetime(df['date'])
            df['net_flow'] = pd.to_numeric(df['net_flow'], errors='coerce') / 1e8  # 转为亿元
            
            df = df.set_index('date').sort_index()
            df['buy_amount'] = df['net_flow'].apply(lambda x: x if x > 0 else 0)
            df['sell_amount'] = df['net_flow'].apply(lambda x: -x if x < 0 else 0)
            
            logger.info(f"北向资金数据：{len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"获取北向资金失败：{e}")
            return pd.DataFrame()
    
    def fetch_etf_shares(self, etf_code: str, start_date: str = "20250101") -> pd.DataFrame:
        """获取 ETF 份额变化数据"""
        try:
            import akshare as ak
            
            market = self._detect_market(etf_code)
            
            if market == 'sh':
                df = ak.fund_etf_scale_sse()
            elif market == 'sz':
                df = ak.fund_etf_scale_szse()
            else:
                logger.warning(f"未知 ETF 市场：{etf_code}")
                return pd.DataFrame()
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            df = df[df['基金代码'] == etf_code].copy()
            
            if df.empty:
                return pd.DataFrame()
            
            df = df.rename(columns={
                '统计日期': 'date',
                '基金份额': 'shares'
            })
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
            df['shares'] = pd.to_numeric(df['shares'], errors='coerce')
            
            df['shares_change_1d'] = df['shares'].pct_change().fillna(0)
            df['shares_change_5d'] = df['shares'].pct_change(5).fillna(0)
            df['shares_change_20d'] = df['shares'].pct_change(20).fillna(0)
            
            logger.info(f"ETF 份额数据 {etf_code}: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"获取 ETF 份额失败 {etf_code}: {e}")
            return pd.DataFrame()
    
    def calc_northbound_metrics(self, northbound_df: pd.DataFrame, window: int = 20) -> Dict[str, float]:
        """计算北向资金指标"""
        if northbound_df.empty or 'net_flow' not in northbound_df.columns:
            return {
                'net_flow_20d_sum': 0,
                'net_flow_5d_avg': 0,
                'buy_ratio': 0.5,
                'trend': 0
            }
        
        net_flow = northbound_df['net_flow']
        
        net_flow_20d_sum = net_flow.iloc[-20:].sum() if len(net_flow) >= 20 else net_flow.sum()
        net_flow_5d_avg = net_flow.iloc[-5:].mean() if len(net_flow) >= 5 else net_flow.mean()
        
        buy_days = (net_flow.iloc[-20:] > 0).sum() if len(net_flow) >= 20 else (net_flow > 0).sum()
        buy_ratio = buy_days / min(20, len(net_flow))
        
        if len(net_flow) >= 20:
            recent_10d = net_flow.iloc[-10:].sum()
            prev_10d = net_flow.iloc[-20:-10].sum()
            trend = (recent_10d - prev_10d) / abs(prev_10d) if prev_10d != 0 else 0
        else:
            trend = 0
        
        return {
            'net_flow_20d_sum': float(net_flow_20d_sum),
            'net_flow_5d_avg': float(net_flow_5d_avg),
            'buy_ratio': float(buy_ratio),
            'trend': float(trend)
        }
    
    def calc_etf_shares_metrics(self, shares_df: pd.DataFrame, window: int = 20) -> Dict[str, float]:
        """计算 ETF 份额指标"""
        if shares_df.empty or 'shares' not in shares_df.columns:
            return {
                'shares_change_20d': 0,
                'shares_change_5d': 0,
                'inflow_days_ratio': 0.5,
                'trend': 0
            }
        
        shares = shares_df['shares']
        
        shares_change_20d = shares.iloc[-1] / shares.iloc[-20] - 1 if len(shares) >= 20 else 0
        shares_change_5d = shares.iloc[-1] / shares.iloc[-5] - 1 if len(shares) >= 5 else 0
        
        if 'shares_change_1d' in shares_df.columns:
            inflow_days = (shares_df['shares_change_1d'].iloc[-20:] > 0).sum() if len(shares) >= 20 else (shares_df['shares_change_1d'] > 0).sum()
        else:
            daily_change = shares.pct_change()
            inflow_days = (daily_change.iloc[-20:] > 0).sum() if len(daily_change) >= 20 else (daily_change > 0).sum()
        inflow_days_ratio = inflow_days / min(20, len(shares))
        
        if len(shares) >= 40:
            recent_change = shares.iloc[-1] / shares.iloc[-20] - 1
            prev_change = shares.iloc[-20] / shares.iloc[-40] - 1
            trend = recent_change - prev_change
        else:
            trend = shares_change_20d
        
        return {
            'shares_change_20d': float(shares_change_20d),
            'shares_change_5d': float(shares_change_5d),
            'inflow_days_ratio': float(inflow_days_ratio),
            'trend': float(trend)
        }
    
    def logout(self):
        """登出 Baostock"""
        if self.bs:
            self.bs.logout()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    fetcher = HybridDataFetcher()
    
    # 测试沪市 ETF
    print("\n=== 测试沪市 ETF (510300) ===")
    df_sh = fetcher.fetch_etf_history("510300", "20250101")
    print(f"510300: {len(df_sh)} rows")
    if not df_sh.empty:
        print(df_sh.tail(3))
    
    # 测试深市 ETF
    print("\n=== 测试深市 ETF (159915) ===")
    df_sz = fetcher.fetch_etf_history("159915", "20250101")
    print(f"159915: {len(df_sz)} rows")
    if not df_sz.empty:
        print(df_sz.tail(3))
    
    # 测试北向资金
    print("\n=== 测试北向资金 ===")
    df_nb = fetcher.fetch_northbound_flow("20250101")
    print(f"北向资金：{len(df_nb)} rows")
    if not df_nb.empty:
        metrics = fetcher.calc_northbound_metrics(df_nb)
        print(f"指标：{metrics}")
    
    fetcher.logout()
