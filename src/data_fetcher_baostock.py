"""
数据获取模块 - 使用 Baostock
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import logging
import time
from typing import Optional, Dict
import yaml
import os

from src.config_loader import load_app_config

logger = logging.getLogger(__name__)


def _coerce_datetime_index(df: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    if df.empty:
        return df
    if column in df.columns:
        df[column] = pd.to_datetime(df[column], errors="coerce")
        df = df.dropna(subset=[column]).set_index(column)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors="coerce")
    return df[~df.index.isna()].sort_index()


def load_config() -> dict:
    """加载统一配置"""
    return load_app_config(Path(__file__).parent.parent)


class BaostockFetcher:
    """Baostock 数据获取器"""
    
    def __init__(self):
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
            logger.error("Baostock 未安装，运行：pip install baostock")
        except Exception as e:
            logger.error(f"Baostock 初始化失败：{e}")
    
    def fetch_index_history(self, index_code: str, start_date: str = "20180101") -> pd.DataFrame:
        """获取指数历史行情"""
        if self.bs is None:
            return pd.DataFrame()
        
        try:
            # 转换日期格式
            start = start_date
            if len(start_date) == 8:
                start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            
            end = datetime.now().strftime('%Y-%m-%d')
            
            # 获取指数 K 线数据
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
            
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return pd.DataFrame()
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 数据清洗
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
            
            logger.info(f"Baostock 获取指数行情成功 {index_code}: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Baostock 获取指数行情异常 {index_code}: {e}")
            return pd.DataFrame()
    
    def fetch_stock_history(self, stock_code: str, start_date: str = "20180101") -> pd.DataFrame:
        """获取股票/ETF 历史行情"""
        if self.bs is None:
            return pd.DataFrame()
        
        try:
            start = start_date
            if len(start_date) == 8:
                start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            
            end = datetime.now().strftime('%Y-%m-%d')
            
            rs = self.bs.query_history_k_data_plus(
                stock_code,
                "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,pctChg",
                start_date=start,
                end_date=end,
                frequency="d",
                adjustflag="3"  # 不复权
            )
            
            if rs.error_code != '0':
                logger.error(f"Baostock 获取股票行情失败 {stock_code}: {rs.error_msg}")
                return pd.DataFrame()
            
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return pd.DataFrame()
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 转换类型
            numeric_cols = ['open', 'high', 'low', 'close', 'preclose', 'volume', 'amount', 'turn', 'pctChg']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
            
            logger.info(f"Baostock 获取股票行情成功 {stock_code}: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Baostock 获取股票行情异常 {stock_code}: {e}")
            return pd.DataFrame()
    
    def fetch_northbound_flow(self, start_date: str = "20250101") -> pd.DataFrame:
        """
        获取北向资金流向数据 (使用东方财富 API)
        
        Returns:
            DataFrame with columns: date, net_flow (亿元)
        """
        try:
            hist_df = self._fetch_northbound_flow_hist(start_date)
            if not hist_df.empty:
                logger.info(f"北向资金历史数据：{len(hist_df)} rows, 最新净流量={hist_df['net_flow'].iloc[-1]:.2f}亿元")
                return hist_df
        except Exception as e:
            logger.warning(f"北向资金历史接口失败，回退摘要接口：{e}")

        try:
            import akshare as ak
            
            # 获取北向资金历史数据 (按日)
            df = ak.stock_hsgt_fund_flow_summary_em()
            
            if df is None or df.empty:
                logger.warning("北向资金数据为空")
                return pd.DataFrame()
            
            # 筛选北向资金 (沪深股通)
            df = df[df['资金方向'] == '北向'].copy()
            
            if df.empty:
                logger.warning("北向资金数据为空 (筛选后)")
                return pd.DataFrame()
            
            # 重命名列
            df = df.rename(columns={
                '交易日': 'date',
                '成交净买额': 'net_flow'  # 单位：元
            })
            
            # 转换类型
            df['date'] = pd.to_datetime(df['date'])
            df['net_flow'] = pd.to_numeric(df['net_flow'], errors='coerce') / 1e8  # 转为亿元
            
            df = df.set_index('date').sort_index()
            
            # 计算买入/卖出 (用净流量近似)
            df['buy_amount'] = df['net_flow'].apply(lambda x: x if x > 0 else 0)
            df['sell_amount'] = df['net_flow'].apply(lambda x: -x if x < 0 else 0)
            
            logger.info(f"北向资金数据：{len(df)} rows, 最新净流量={df['net_flow'].iloc[-1]:.2f}亿元")
            return df
            
        except Exception as e:
            logger.error(f"获取北向资金失败：{e}")
            return pd.DataFrame()

    def _fetch_northbound_flow_hist(self, start_date: str = "20250101") -> pd.DataFrame:
        """使用东方财富历史接口获取北向资金日序列。"""
        import akshare as ak

        df = ak.stock_hsgt_hist_em(symbol="北向资金")
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "日期": "date",
                "当日成交净买额": "net_flow",
                "买入成交额": "buy_amount",
                "卖出成交额": "sell_amount",
                "历史累计净买额": "accum_net_flow",
                "当日资金流入": "fund_inflow",
                "当日余额": "quota_balance",
                "持股市值": "holding_market_cap",
            }
        )
        df = _coerce_datetime_index(df, "date")

        for col in [
            "net_flow",
            "buy_amount",
            "sell_amount",
            "accum_net_flow",
            "fund_inflow",
            "quota_balance",
            "holding_market_cap",
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 最新交易日偶尔只更新指数行情，资金列为空；这里过滤掉没有净买额的伪记录。
        df = df.dropna(subset=["net_flow"])
        if df.empty:
            return pd.DataFrame()

        start_ts = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
        if start_ts is not None and not pd.isna(start_ts):
            df = df[df.index >= start_ts]

        return df.sort_index()

    def fetch_northbound_snapshot(self) -> pd.DataFrame:
        """获取北向资金当日快照，作为健康检查补充。"""
        try:
            import akshare as ak

            df = ak.stock_hsgt_fund_flow_summary_em()
            if df is None or df.empty:
                return pd.DataFrame()

            df = df[df["资金方向"] == "北向"].copy()
            if df.empty:
                return pd.DataFrame()

            date_col = "交易日" if "交易日" in df.columns else None
            if date_col:
                df = df.rename(columns={date_col: "date"})
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
            else:
                df["date"] = pd.Timestamp(datetime.now().date())

            net_flow_col = "成交净买额" if "成交净买额" in df.columns else None
            if net_flow_col:
                df = df.rename(columns={net_flow_col: "net_flow"})
                df["net_flow"] = pd.to_numeric(df["net_flow"], errors="coerce") / 1e8
            else:
                df["net_flow"] = pd.NA

            df = _coerce_datetime_index(df, "date")
            return df.sort_index()
        except Exception as e:
            logger.warning(f"获取北向资金快照失败：{e}")
            return pd.DataFrame()
    
    def fetch_northbound_flow_by_market(self, start_date: str = "20250101") -> Dict[str, pd.DataFrame]:
        """
        获取分市场北向资金流向 (沪股通/深股通)
        
        Returns:
            {
                'sh': DataFrame for 沪股通，
                'sz': DataFrame for 深股通
            }
        """
        try:
            import akshare as ak
            
            result = {}
            
            # 沪股通
            df_sh = ak.stock_hsgt_north_net_flow_in_em(symbol="沪股通")
            if df_sh is not None and not df_sh.empty:
                df_sh = df_sh.rename(columns={
                    '日期': 'date',
                    '净买入金额': 'net_flow',
                    '买入成交额': 'buy_amount',
                    '卖出成交额': 'sell_amount'
                })
                df_sh['date'] = pd.to_datetime(df_sh['date'])
                df_sh = df_sh.set_index('date').sort_index()
                for col in ['net_flow', 'buy_amount', 'sell_amount']:
                    if col in df_sh.columns:
                        df_sh[col] = pd.to_numeric(df_sh[col], errors='coerce') / 1e8
                result['sh'] = df_sh
            
            # 深股通
            df_sz = ak.stock_hsgt_north_net_flow_in_em(symbol="深股通")
            if df_sz is not None and not df_sz.empty:
                df_sz = df_sz.rename(columns={
                    '日期': 'date',
                    '净买入金额': 'net_flow',
                    '买入成交额': 'buy_amount',
                    '卖出成交额': 'sell_amount'
                })
                df_sz['date'] = pd.to_datetime(df_sz['date'])
                df_sz = df_sz.set_index('date').sort_index()
                for col in ['net_flow', 'buy_amount', 'sell_amount']:
                    if col in df_sz.columns:
                        df_sz[col] = pd.to_numeric(df_sz[col], errors='coerce') / 1e8
                result['sz'] = df_sz
            
            logger.info(f"分市场北向资金：沪股通{len(result.get('sh', []))}行，深股通{len(result.get('sz', []))}行")
            return result
            
        except Exception as e:
            logger.error(f"获取分市场北向资金失败：{e}")
            return {}
    
    def calc_northbound_metrics(self, northbound_df: pd.DataFrame, window: int = 20) -> Dict[str, float]:
        """
        计算北向资金指标
        
        Returns:
            {
                'net_flow_20d_sum': 近 20 日净买入总和 (亿元),
                'net_flow_5d_avg': 近 5 日日均净买入，
                'buy_ratio': 买入天数占比，
                'trend': 资金趋势 (近期 vs 前期)
            }
        """
        if northbound_df.empty or 'net_flow' not in northbound_df.columns:
            return {
                'net_flow_20d_sum': 0,
                'net_flow_5d_avg': 0,
                'buy_ratio': 0.5,
                'trend': 0
            }
        
        net_flow = northbound_df['net_flow']
        
        # 近 20 日净买入总和
        net_flow_20d_sum = net_flow.iloc[-20:].sum() if len(net_flow) >= 20 else net_flow.sum()
        
        # 近 5 日日均净买入
        net_flow_5d_avg = net_flow.iloc[-5:].mean() if len(net_flow) >= 5 else net_flow.mean()
        
        # 买入天数占比 (净买入>0 的天数)
        buy_days = (net_flow.iloc[-20:] > 0).sum() if len(net_flow) >= 20 else (net_flow > 0).sum()
        buy_ratio = buy_days / min(20, len(net_flow))
        
        # 资金趋势 (近 10 日 vs 前 10 日)
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
    
    def fetch_etf_shares(self, etf_code: str, start_date: str = "20250101") -> pd.DataFrame:
        """
        获取 ETF 份额变化数据 (通过 AKShare 获取上交所/深交所 ETF 规模数据)
        
        Args:
            etf_code: ETF 代码 (如 510300)
            
        Returns:
            DataFrame with columns: date, shares, change_pct
        """
        try:
            import akshare as ak
            
            # 判断 ETF 市场 (51xxxx/58xxxx=上交所，15xxxx=深交所)
            if etf_code.startswith('51') or etf_code.startswith('58'):
                # 上交所 ETF (含科创板 588xxx)
                df = ak.fund_etf_scale_sse()
                market = 'SSE'
            elif etf_code.startswith('15'):
                # 深交所 ETF
                df = ak.fund_etf_scale_szse()
                market = 'SZSE'
            else:
                logger.warning(f"未知 ETF 市场：{etf_code}")
                return pd.DataFrame()
            
            if df is None or df.empty:
                logger.warning(f"ETF 份额数据为空：{etf_code}")
                return pd.DataFrame()
            
            # 筛选目标 ETF
            df = df[df['基金代码'] == etf_code].copy()
            
            if df.empty:
                logger.warning(f"未找到 ETF 份额数据：{etf_code}")
                return pd.DataFrame()

            # 上交所返回历史快照，深交所当前接口通常只返回单条最新快照且没有日期列。
            # 这里统一兼容不同列名，确保缺失日期时也能返回可计算的中性数据。
            date_col = next(
                (col for col in ('统计日期', '交易日期', '日期', '上市日期') if col in df.columns),
                None
            )
            shares_col = next(
                (col for col in ('基金份额', '份额') if col in df.columns),
                None
            )

            if shares_col is None:
                logger.warning(f"ETF 份额数据缺少份额列：{etf_code}, columns={list(df.columns)}")
                return pd.DataFrame()

            if date_col is not None:
                df = df.rename(columns={date_col: 'date'})
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
            else:
                df['date'] = pd.Timestamp(datetime.now().date())
                logger.info(f"ETF 份额数据 {etf_code} ({market}) 未提供日期列，使用当日快照")

            df = df.rename(columns={shares_col: 'shares'})
            df['shares'] = pd.to_numeric(df['shares'], errors='coerce')

            df = df.dropna(subset=['date', 'shares'])
            if df.empty:
                logger.warning(f"ETF 份额数据清洗后为空：{etf_code}")
                return pd.DataFrame()

            # 避免同一天多条记录干扰变化率计算，保留最后一条。
            df = df.sort_values('date').drop_duplicates(subset=['date'], keep='last')
            df = df.set_index('date').sort_index()
            
            # 计算份额变化百分比
            df['shares_change_1d'] = df['shares'].pct_change().fillna(0)
            df['shares_change_5d'] = df['shares'].pct_change(5).fillna(0)
            df['shares_change_20d'] = df['shares'].pct_change(20).fillna(0)
            
            logger.info(f"ETF 份额数据 {etf_code} ({market}): {len(df)} rows, 最新份额={df['shares'].iloc[-1]:,.0f}")
            return df
            
        except Exception as e:
            logger.error(f"获取 ETF 份额失败 {etf_code}: {e}")
            return pd.DataFrame()
    
    def calc_etf_shares_metrics(self, shares_df: pd.DataFrame, window: int = 20) -> Dict[str, float]:
        """
        计算 ETF 份额指标
        
        Returns:
            {
                'shares_change_20d': 20 日份额变化 (%),
                'shares_change_5d': 5 日份额变化 (%),
                'inflow_days_ratio': 份额增长天数占比，
                'trend': 份额趋势 (近期 vs 前期)
            }
        """
        if shares_df.empty or 'shares' not in shares_df.columns:
            return {
                'shares_change_20d': 0,
                'shares_change_5d': 0,
                'inflow_days_ratio': 0.5,
                'trend': 0
            }
        
        shares = shares_df['shares']

        # 深交所接口常常只提供单条快照；样本不足时返回中性值，避免误伤评分。
        if len(shares) < 2:
            return {
                'shares_change_20d': 0.0,
                'shares_change_5d': 0.0,
                'inflow_days_ratio': 0.5,
                'trend': 0.0
            }
        
        # 20 日份额变化
        shares_change_20d = shares.iloc[-1] / shares.iloc[-20] - 1 if len(shares) >= 20 else 0
        
        # 5 日份额变化
        shares_change_5d = shares.iloc[-1] / shares.iloc[-5] - 1 if len(shares) >= 5 else 0
        
        # 份额增长天数占比
        if 'shares_change_1d' in shares_df.columns:
            inflow_days = (shares_df['shares_change_1d'].iloc[-20:] > 0).sum() if len(shares) >= 20 else (shares_df['shares_change_1d'] > 0).sum()
        else:
            daily_change = shares.pct_change()
            inflow_days = (daily_change.iloc[-20:] > 0).sum() if len(daily_change) >= 20 else (daily_change > 0).sum()
        inflow_days_ratio = inflow_days / min(20, len(shares))
        
        # 份额趋势 (近 20 日变化 vs 前 20 日变化)
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
    
    def fetch_money_flow(self, etf_code: str, window: int = 20) -> Dict[str, float]:
        """
        计算资金流指标
        
        Returns:
            {
                'volume_trend': 成交量趋势 (>0 表示放量),
                'amount_trend': 成交金额趋势，
                'turnover_trend': 换手率趋势
            }
        """
        df = self.fetch_etf_history(etf_code, "20250101")
        
        if df.empty or len(df) < window * 2:
            return {'volume_trend': 0, 'amount_trend': 0, 'turnover_trend': 0}
        
        # 成交量趋势 (当前 vs 过去 20 日均值)
        recent_vol = df['volume'].iloc[-window:].mean()
        prev_vol = df['volume'].iloc[-window*2:-window].mean()
        volume_trend = (recent_vol - prev_vol) / prev_vol if prev_vol > 0 else 0
        
        # 成交金额趋势
        recent_amt = df['amount'].iloc[-window:].mean()
        prev_amt = df['amount'].iloc[-window*2:-window].mean()
        amount_trend = (recent_amt - prev_amt) / prev_amt if prev_amt > 0 else 0
        
        # 换手率趋势 (如果有)
        if 'turn' in df.columns:
            recent_turn = df['turn'].iloc[-window:].mean()
            prev_turn = df['turn'].iloc[-window*2:-window].mean()
            turnover_trend = (recent_turn - prev_turn) / prev_turn if prev_turn > 0 else 0
        else:
            turnover_trend = 0
        
        return {
            'volume_trend': volume_trend,
            'amount_trend': amount_trend,
            'turnover_trend': turnover_trend
        }
    
    def fetch_index_basic_info(self, index_code: str) -> dict:
        """获取指数基本信息"""
        if self.bs is None:
            return {}
        
        try:
            # Baostock 没有直接的指数基本信息接口，这里返回空字典
            # 可以通过其他方式获取
            return {
                'code': index_code,
                'name': 'Unknown'
            }
        except Exception as e:
            logger.error(f"获取指数基本信息失败 {index_code}: {e}")
            return {}
    
    def logout(self):
        """登出 Baostock"""
        if self.bs:
            self.bs.logout()


class IndexDataFetcher:
    """指数数据获取器 - 使用 Baostock"""
    
    def __init__(self, cache_dir: str = "data/raw"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.baostock_fetcher = BaostockFetcher()
        self.config = load_config()
    
    def fetch_northbound_flow(self, start_date: str = "20250101") -> pd.DataFrame:
        """优先读取缓存并刷新北向资金历史序列。"""
        cache_file = self._get_cache_file("northbound", "history_v2")
        cached_df = pd.DataFrame()

        if cache_file.exists():
            try:
                cached_df = pd.read_parquet(cache_file)
                cached_df = _coerce_datetime_index(cached_df)
                if "net_flow" in cached_df.columns and "类型" not in cached_df.columns:
                    logger.info(f"Loaded cached northbound data: {len(cached_df)} rows")
                else:
                    logger.warning("Northbound cache schema outdated, ignoring old cache")
                    cached_df = pd.DataFrame()
            except Exception as e:
                logger.warning(f"Northbound cache read failed, will refresh: {e}")
                cached_df = pd.DataFrame()

        try:
            fresh_df = self.baostock_fetcher.fetch_northbound_flow(start_date)
            if not fresh_df.empty:
                combined = pd.concat([cached_df, fresh_df]).sort_index()
                combined = combined[~combined.index.duplicated(keep="last")]
                combined.to_parquet(cache_file)
                logger.info(f"Northbound cache updated: {len(combined)} rows")
                return combined[combined.index >= pd.to_datetime(start_date, format="%Y%m%d")]
        except Exception as e:
            logger.warning(f"Northbound refresh failed, fallback to cache: {e}")

        if not cached_df.empty:
            start_ts = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
            if start_ts is not None and not pd.isna(start_ts):
                return cached_df[cached_df.index >= start_ts]
            return cached_df

        return pd.DataFrame()

    def fetch_northbound_snapshot(self) -> pd.DataFrame:
        """代理到 BaostockFetcher"""
        return self.baostock_fetcher.fetch_northbound_snapshot()
    
    def calc_northbound_metrics(self, northbound_df: pd.DataFrame, window: int = 20) -> Dict[str, float]:
        """代理到 BaostockFetcher"""
        return self.baostock_fetcher.calc_northbound_metrics(northbound_df, window)
    
    def fetch_etf_shares(self, etf_code: str, start_date: str = "20250101") -> pd.DataFrame:
        """代理到 BaostockFetcher"""
        return self.baostock_fetcher.fetch_etf_shares(etf_code, start_date)
    
    def calc_etf_shares_metrics(self, shares_df: pd.DataFrame, window: int = 20) -> Dict[str, float]:
        """代理到 BaostockFetcher"""
        return self.baostock_fetcher.calc_etf_shares_metrics(shares_df, window)
    
    def _get_cache_file(self, index_code: str, data_type: str = "history") -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{index_code.replace('.', '_')}_{data_type}.parquet"
    
    def fetch_index_history(self, index_code: str, start_date: str = "20180101", force_refresh: bool = False) -> pd.DataFrame:
        """
        获取指数历史行情
        注意：Baostock 不支持指数数据，这里通过 ETF 数据替代
        需要在 config.yaml 中配置 ETF 代码
        """
        # Baostock 不支持指数数据，返回空 DataFrame
        # 使用 ETF 数据作为替代
        logger.warning(f"Baostock 不支持指数数据，请使用 fetch_etf_history: {index_code}")
        return pd.DataFrame()
    
    def fetch_etf_history(self, etf_code: str, start_date: str = "20180101", force_refresh: bool = False) -> pd.DataFrame:
        """获取 ETF 历史行情（使用 AKShare Sina 接口）"""
        cache_file = self._get_cache_file(etf_code, "etf_history")
        
        if cache_file.exists() and not force_refresh:
            try:
                df = pd.read_parquet(cache_file)
                logger.info(f"Loaded cached ETF data for {etf_code}: {len(df)} rows")
                return df
            except Exception as e:
                logger.warning(f"Cache read failed, will refresh: {e}")
        
        # 转换代码格式 (如 510300 -> sh510300)
        # 51/56 开头是上海，15/16 开头是深圳
        etf_code_clean = etf_code.replace('.', '')
        if len(etf_code_clean) == 6 and etf_code_clean.isdigit():
            if etf_code_clean.startswith(('51', '56', '58')):
                etf_code_clean = f'sh{etf_code_clean}'
            elif etf_code_clean.startswith(('15', '16')):
                etf_code_clean = f'sz{etf_code_clean}'
        
        logger.info(f"Fetching ETF from AKShare Sina: {etf_code_clean}")
        
        try:
            import akshare as ak
            
            # 使用 Sina 接口获取 ETF 历史数据
            df = ak.fund_etf_hist_sina(symbol=etf_code_clean)
            
            if df.empty:
                logger.warning(f"AKShare returned empty data for {etf_code_clean}")
                return pd.DataFrame()
            
            # 重命名列以匹配预期格式
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
            
            # 添加 preclose（用前一天的 close 近似）
            df['preclose'] = df['close'].shift(1)
            
            logger.info(f"ETF data fetched: {len(df)} rows ({df.index.min().date()} ~ {df.index.max().date()})")
            
            if not df.empty:
                df.to_parquet(cache_file)
                logger.info(f"ETF cached: {len(df)} rows")
            
            return df
            
        except Exception as e:
            logger.error(f"AKShare ETF fetch failed for {etf_code_clean}: {e}")
            return pd.DataFrame()
    
    def fetch_index_pe_history(self, index_code: str) -> pd.DataFrame:
        """
        获取指数 PE 历史
        注意：Baostock 没有直接的指数 PE 接口，这里返回空 DataFrame
        后续可以通过其他方式获取（如 AKShare 或手动计算）
        """
        cache_file = self._get_cache_file(index_code, "pe")
        
        if cache_file.exists():
            try:
                df = pd.read_parquet(cache_file)
                logger.info(f"Loaded cached PE data for {index_code}: {len(df)} rows")
                return df
            except Exception as e:
                logger.warning(f"PE cache read failed: {e}")
        
        # Baostock 暂无指数 PE 数据接口
        logger.warning(f"Baostock 不支持指数 PE 数据，返回空数据：{index_code}")
        return pd.DataFrame()
    
    def get_current_price(self, index_code: str) -> Optional[float]:
        """获取当前价格"""
        df = self.fetch_index_history(index_code)
        if df.empty:
            return None
        return df['close'].iloc[-1]
    
    def get_current_pe(self, index_code: str) -> Optional[float]:
        """获取当前 PE"""
        df = self.fetch_index_pe_history(index_code)
        if df.empty:
            return None
        return df['pe'].iloc[0] if 'pe' in df.columns else None
    
    def get_current_pb(self, index_code: str) -> Optional[float]:
        """获取当前 PB"""
        # Baostock 暂无 PB 数据
        return None
    
    def refresh_all_cache(self, indices: list):
        """刷新所有指数缓存"""
        logger.info(f"Refreshing cache for {len(indices)} indices...")
        
        for idx in indices:
            code = idx.get('code', '')
            etf = idx.get('etf', '')
            
            logger.info(f"Refreshing {code}...")
            
            # 获取指数数据
            self.fetch_index_history(code, force_refresh=True)
            
            # 获取 ETF 数据（作为替代）
            if etf:
                self.fetch_etf_history(etf, force_refresh=True)
            
            # PE 数据（暂不支持）
            self.fetch_index_pe_history(code)
        
        logger.info("Cache refresh completed")
    
    def close(self):
        """关闭连接"""
        self.baostock_fetcher.logout()


# 便捷函数
def create_fetcher() -> IndexDataFetcher:
    """创建数据获取器实例"""
    return IndexDataFetcher()


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    fetcher = create_fetcher()
    
    # 测试获取沪深 300 数据
    df = fetcher.fetch_index_history("000300.SH", "20250101")
    print(f"\n沪深 300 数据：{len(df)} rows")
    if not df.empty:
        print(df.tail())
    
    # 测试获取 ETF 数据
    df_etf = fetcher.fetch_etf_history("510300", "20250101")
    print(f"\n华泰柏瑞沪深 300ETF 数据：{len(df_etf)} rows")
    if not df_etf.empty:
        print(df_etf.tail())
    
    fetcher.close()
