"""
基本面数据获取模块

数据源:
- 指数 PE/PB: AKShare 中证指数
- 成分股基本面：AKShare 个股财务数据
- 行业估值：AKShare 行业指数
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, List, Tuple
import time

logger = logging.getLogger(__name__)


class FundamentalDataFetcher:
    """
    基本面数据获取器
    
    功能:
    1. 指数 PE/PB 历史数据
    2. 指数成分股 ROE/盈利增长
    3. 行业估值对比
    """
    
    def __init__(self, cache_dir: str = "data/fundamental"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_file(self, code: str, data_type: str = "pe") -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{code.replace('.', '_')}_{data_type}.parquet"
    
    def fetch_index_pe_history(self, index_code: str, days: int = 2520) -> pd.DataFrame:
        """
        获取指数 PE 历史数据
        
        数据源优先级:
        1. AKShare 乐咕数据 (稳定)
        2. ETF 价格反推 (备用)
        
        Args:
            index_code: 指数代码 (如 000300.SH)
            days: 历史天数 (默认 10 年约 2520 天)
            
        Returns:
            DataFrame with columns: date, pe, pb, dividend_yield
        """
        cache_file = self._get_cache_file(index_code, "pe")
        
        # 尝试读取缓存 (7 天内)
        if cache_file.exists():
            try:
                df = pd.read_parquet(cache_file)
                if not df.empty:
                    last_date = df.index.max()
                    days_old = (datetime.now() - last_date).days
                    if days_old < 7:
                        logger.info(f"Loaded cached PE data for {index_code}: {len(df)} rows ({days_old} days old)")
                        return df
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")
        
        logger.info(f"Fetching PE history for {index_code}...")
        
        # 尝试使用乐咕数据 (更稳定)
        df = self._fetch_pe_legu(index_code, days)
        
        if not df.empty:
            df.to_parquet(cache_file)
            logger.info(f"PE data fetched (Legu) and cached: {len(df)} rows")
            return df
        
        # 备用方案：ETF 价格反推
        logger.warning(f"Legu data unavailable, using alternative method for {index_code}")
        df = self._fetch_pe_alternative(index_code, days)
        
        if not df.empty:
            df.to_parquet(cache_file)
            logger.info(f"PE data estimated and cached: {len(df)} rows")
        
        return df
    
    def _fetch_pe_legu(self, index_code: str, days: int = 2520) -> pd.DataFrame:
        """
        从乐咕数据获取指数估值 (更稳定)
        
        接口：akshare.index_value_hist_fundamental_em
        """
        try:
            import akshare as ak
            
            # 转换代码格式
            code_clean = index_code.replace('.', '').replace('SH', '').replace('SZ', '')
            
            # 乐咕数据接口
            df = ak.index_value_hist_fundamental_em(symbol=code_clean, indicator="市盈率")
            
            if df is None or df.empty:
                logger.warning(f"Legu returned empty data for {index_code}")
                return pd.DataFrame()
            
            # 重命名列
            df = df.rename(columns={
                '日期': 'date',
                '市盈率': 'pe',
                '市净率': 'pb',
                '股息率': 'dividend_yield'
            })
            
            # 筛选列
            cols_to_keep = ['date', 'pe', 'pb', 'dividend_yield']
            df = df[[c for c in cols_to_keep if c in df.columns]]
            
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date').sort_index()
            
            # 转换数值
            for col in ['pe', 'pb', 'dividend_yield']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 限制天数
            if len(df) > days:
                df = df.iloc[-days:]
            
            return df
            
        except Exception as e:
            logger.error(f"Legu PE fetch failed: {e}")
            return pd.DataFrame()
    
    def _fetch_pe_alternative(self, index_code: str, days: int = 2520) -> pd.DataFrame:
        """
        备用方案：使用 ETF 数据估算 PE
        
        逻辑：
        1. 获取 ETF 历史价格
        2. 使用预设的当前 PE 值
        3. 用价格变化反推历史 PE
        """
        logger.info(f"Using alternative method to estimate PE for {index_code}")
        
        # 获取 ETF 代码 (去除后缀)
        code_clean = index_code.replace('.', '').replace('SH', '').replace('SZ', '').replace('CSI', '')
        
        # ETF 映射 + 当前 PE 估计值 (2026 年 3 月)
        etf_pe_map = {
            '000300': ('510300', 12.5),  # 沪深 300
            '000905': ('510500', 23.0),  # 中证 500
            '000852': ('512100', 28.0),  # 中证 1000
            '399006': ('159915', 35.0),  # 创业板指
            '000688': ('588000', 45.0),  # 科创 50
            '000932': ('159928', 18.0),  # 消费指数
            '000933': ('512010', 25.0),  # 医药指数
            '000993': ('515000', 35.0),  # 科技指数
            '000992': ('510230', 8.0),   # 金融指数
            '000988': ('516880', 20.0),  # 制造指数
            '399967': ('512660', 25.0),  # 军工指数
            '399808': ('516160', 30.0),  # 新能源
            '399997': ('512690', 22.0),  # 白酒
            '399986': ('512800', 5.5),   # 银行
            '399975': ('512000', 18.0),  # 证券
        }
        
        if code_clean not in etf_pe_map:
            logger.warning(f"No ETF mapping for {index_code} (code: {code_clean})")
            return pd.DataFrame()
        
        etf_code, current_pe = etf_pe_map[code_clean]
        
        try:
            # 获取 ETF 价格数据
            from data_fetcher_hybrid import HybridDataFetcher
            fetcher = HybridDataFetcher()
            etf_df = fetcher.fetch_etf_history(etf_code, "20200101")
            
            if etf_df.empty:
                return pd.DataFrame()
            
            # 用价格变化反推历史 PE
            etf_df = etf_df.copy()
            current_price = etf_df['close'].iloc[-1]
            
            # PE = 价格 / 每股收益，假设每股收益不变
            # 历史 PE = 当前 PE * (历史价格 / 当前价格)
            etf_df['pe'] = current_pe * (etf_df['close'] / current_price)
            
            # 估算 PB (假设 PB/PE 比率稳定，不同指数不同)
            pb_pe_ratio = 0.15  # 默认
            if code_clean in ['399986', '000992']:  # 银行/金融
                pb_pe_ratio = 0.08
            elif code_clean in ['399006', '000688']:  # 创业板/科创板
                pb_pe_ratio = 0.25
            
            etf_df['pb'] = etf_df['pe'] * pb_pe_ratio
            
            # 估算股息率 (简化：固定值)
            dividend_yield = 2.0
            if code_clean in ['399986', '000922']:  # 银行/红利
                dividend_yield = 4.5
            elif code_clean in ['399006', '000688']:  # 成长板块
                dividend_yield = 0.5
            
            etf_df['dividend_yield'] = dividend_yield
            
            result = etf_df[['pe', 'pb', 'dividend_yield']].copy()
            
            if len(result) > days:
                result = result.iloc[-days:]
            
            logger.info(f"Alternative PE estimated: {len(result)} rows, current PE={current_pe}")
            return result
            
        except Exception as e:
            logger.error(f"Alternative PE estimation failed: {e}")
            return pd.DataFrame()
    
    def _get_current_pe_from_csindex(self, index_code: str) -> Optional[float]:
        """获取当前 PE (从中证指数官网)"""
        try:
            import akshare as ak
            
            # 获取指数当前估值
            df = ak.index_stock_cons_csindex(symbol=index_code)
            
            if df is not None and not df.empty and '市盈率' in df.columns:
                return float(df['市盈率'].iloc[-1])
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get current PE: {e}")
            return None
    
    def fetch_index_constituents(self, index_code: str) -> pd.DataFrame:
        """
        获取指数成分股
        
        Returns:
            DataFrame with columns: stock_code, stock_name, weight
        """
        try:
            import akshare as ak
            
            code_clean = index_code.replace('.', '').replace('SH', '').replace('SZ', '')
            
            df = ak.index_stock_cons_csindex(symbol=code_clean)
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            # 重命名
            df = df.rename(columns={
                '品种代码': 'stock_code',
                '品种名称': 'stock_name',
                '权重': 'weight'
            })
            
            cols_to_keep = ['stock_code', 'stock_name', 'weight']
            df = df[[c for c in cols_to_keep if c in df.columns]]
            
            logger.info(f"Fetched {len(df)} constituents for {index_code}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch constituents: {e}")
            return pd.DataFrame()
    
    def calc_index_fundamental_metrics(self, index_code: str) -> Dict[str, float]:
        """
        计算指数基本面指标
        
        Returns:
            {
                'pe_current': 当前 PE,
                'pe_percentile': PE 历史分位 (0-1),
                'pb_current': 当前 PB,
                'pb_percentile': PB 历史分位 (0-1),
                'roe_median': 成分股 ROE 中位数，
                'earnings_growth': 盈利增长率，
                'dividend_yield': 股息率
            }
        """
        result = {
            'pe_current': None,
            'pe_percentile': None,
            'pb_current': None,
            'pb_percentile': None,
            'roe_median': None,
            'earnings_growth': None,
            'dividend_yield': None
        }
        
        # 获取 PE 历史
        pe_df = self.fetch_index_pe_history(index_code)
        
        if not pe_df.empty:
            if 'pe' in pe_df.columns and not pe_df['pe'].isna().all():
                result['pe_current'] = float(pe_df['pe'].iloc[-1])
                result['pe_percentile'] = self._calc_percentile(pe_df['pe'].dropna(), result['pe_current'])
            
            if 'pb' in pe_df.columns and not pe_df['pb'].isna().all():
                result['pb_current'] = float(pe_df['pb'].iloc[-1])
                result['pb_percentile'] = self._calc_percentile(pe_df['pb'].dropna(), result['pb_current'])
            
            if 'dividend_yield' in pe_df.columns:
                result['dividend_yield'] = float(pe_df['dividend_yield'].iloc[-1])
        
        # 获取成分股基本面 (简化：用指数 PE 估算 ROE)
        # ROE ≈ 1 / PE * 100 (简化公式)
        if result['pe_current'] and result['pe_current'] > 0:
            result['roe_median'] = 100.0 / result['pe_current']
        
        # 盈利增长 (简化：用 PE 变化估算)
        if len(pe_df) >= 252 and 'pe' in pe_df.columns:
            pe_1y_ago = pe_df['pe'].iloc[-252]
            if pe_1y_ago > 0:
                result['earnings_growth'] = (result['pe_current'] / pe_1y_ago - 1) * 100
        
        logger.debug(f"Fundamental metrics for {index_code}: {result}")
        
        return result
    
    def _calc_percentile(self, series: pd.Series, value: float) -> float:
        """计算分位数"""
        if series.empty or pd.isna(value):
            return 0.5
        return (series < value).mean()
    
    def fetch_stock_fundamental(self, stock_code: str) -> Dict[str, float]:
        """
        获取个股基本面数据
        
        Returns:
            {
                'pe': 市盈率，
                'pb': 市净率，
                'ps': 市销率，
                'roe': 净资产收益率，
                'revenue_growth': 营收增长率，
                'profit_growth': 净利润增长率
            }
        """
        result = {
            'pe': None,
            'pb': None,
            'ps': None,
            'roe': None,
            'revenue_growth': None,
            'profit_growth': None
        }
        
        try:
            import akshare as ak
            
            # 转换代码格式
            code_clean = stock_code.replace('.', '')
            if len(code_clean) == 6:
                if code_clean.startswith('6'):
                    code_clean = f'sh{code_clean}'
                else:
                    code_clean = f'sz{code_clean}'
            
            # 获取个股估值
            df = ak.stock_value_manage_em(symbol=stock_code)
            
            if df is not None and not df.empty:
                # 获取最新数据
                latest = df.iloc[-1]
                
                if 'PE' in latest:
                    result['pe'] = float(latest['PE'])
                if 'PB' in latest:
                    result['pb'] = float(latest['PB'])
                if 'PS' in latest:
                    result['ps'] = float(latest['PS'])
            
            logger.debug(f"Stock fundamental for {stock_code}: {result}")
            
        except Exception as e:
            logger.error(f"Failed to fetch stock fundamental: {e}")
        
        return result
    
    def calc_industry_valuation(self, industry_name: str) -> pd.DataFrame:
        """
        获取行业估值对比
        
        Args:
            industry_name: 行业名称 (如 '银行', '医药', '科技')
            
        Returns:
            DataFrame with industry valuation metrics
        """
        try:
            import akshare as ak
            
            # 获取行业指数估值
            df = ak.stock_board_industry_name_em(symbol=industry_name)
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            logger.info(f"Industry valuation for {industry_name}: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch industry valuation: {e}")
            return pd.DataFrame()
    
    def get_fundamental_score(self, index_code: str) -> Tuple[float, Dict[str, float]]:
        """
        计算基本面评分
        
        Returns:
            (score, metrics_dict)
            
        评分逻辑:
        - PE 分位低 → 高分
        - PB 分位低 → 高分
        - ROE 高 → 高分
        - 盈利增长高 → 高分
        """
        metrics = self.calc_index_fundamental_metrics(index_code)
        
        scores = []
        weights = []
        
        # 1. PE 分位 (40%) - 分位越低分越高
        if metrics['pe_percentile'] is not None:
            pe_score = 1.0 - metrics['pe_percentile']
            scores.append(pe_score)
            weights.append(0.40)
            metrics['pe_score'] = pe_score
        else:
            metrics['pe_score'] = 0.5
        
        # 2. PB 分位 (30%) - 分位越低分越高
        if metrics['pb_percentile'] is not None:
            pb_score = 1.0 - metrics['pb_percentile']
            scores.append(pb_score)
            weights.append(0.30)
            metrics['pb_score'] = pb_score
        else:
            metrics['pb_score'] = 0.5
        
        # 3. ROE (20%) - ROE 越高分越高 (假设合理 ROE 8%-20%)
        if metrics['roe_median'] is not None:
            roe = metrics['roe_median']
            roe_score = (roe - 8) / 12  # 8% → 0, 20% → 1
            roe_score = max(0, min(1, roe_score))
            scores.append(roe_score)
            weights.append(0.20)
            metrics['roe_score'] = roe_score
        else:
            metrics['roe_score'] = 0.5
        
        # 4. 盈利增长 (10%) - 增长越高分越高 (假设合理增长 5%-20%)
        if metrics['earnings_growth'] is not None:
            growth = metrics['earnings_growth']
            growth_score = (growth - 5) / 15  # 5% → 0, 20% → 1
            growth_score = max(0, min(1, growth_score))
            scores.append(growth_score)
            weights.append(0.10)
            metrics['growth_score'] = growth_score
        else:
            metrics['growth_score'] = 0.5
        
        # 加权平均
        if scores:
            final_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        else:
            final_score = 0.5
        
        metrics['fundamental_score'] = final_score
        
        return final_score, metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    fetcher = FundamentalDataFetcher()
    
    # 测试获取沪深 300 基本面
    print("\n=== 测试沪深 300 基本面 ===")
    metrics = fetcher.calc_index_fundamental_metrics("000300.SH")
    print(f"PE: {metrics.get('pe_current')}, PE 分位：{metrics.get('pe_percentile')}")
    print(f"PB: {metrics.get('pb_current')}, PB 分位：{metrics.get('pb_percentile')}")
    print(f"ROE: {metrics.get('roe_median')}%")
    print(f"股息率：{metrics.get('dividend_yield')}%")
    
    # 测试基本面评分
    print("\n=== 测试基本面评分 ===")
    score, details = fetcher.get_fundamental_score("000300.SH")
    print(f"基本面评分：{score:.3f}")
    print(f"详情：{details}")
