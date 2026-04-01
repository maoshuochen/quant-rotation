"""
因子计算引擎 - 增强版
支持稳健归一化、中性化、IC 分析
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, List, Tuple
from sklearn.preprocessing import RobustScaler, QuantileTransformer
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class FactorEngine:
    """因子计算器"""
    
    def __init__(self, lookback_days: int = 2520):
        self.lookback = lookback_days  # 默认 10 年
    
    def calc_pe_percentile(self, current_pe: float, pe_history: pd.Series) -> float:
        """
        计算 PE 历史分位
        
        Returns:
            0-1 之间，越低表示估值越低
        """
        if pe_history.empty or current_pe is None:
            return 0.5
        
        # 过滤异常值
        valid_pe = pe_history[(pe_history > 0) & (pe_history < 100)]
        
        if len(valid_pe) < 100:
            return 0.5
        
        percentile = (valid_pe < current_pe).mean()
        return percentile
    
    def calc_pb_percentile(self, current_pb: float, pb_history: pd.Series) -> float:
        """计算 PB 历史分位"""
        if pb_history.empty or current_pb is None:
            return 0.5
        
        valid_pb = pb_history[(pb_history > 0) & (pb_history < 20)]
        
        if len(valid_pb) < 100:
            return 0.5
        
        return (valid_pb < current_pb).mean()
    
    def calc_momentum(self, prices: pd.Series, window: int = 126) -> float:
        """
        计算动量 (收益率)
        
        Args:
            prices: 价格序列
            window: 周期 (默认 126 天=6 个月)
            
        Returns:
            动量值 (-1 ~ 1)
        """
        if len(prices) < window:
            return 0.0
        
        momentum = prices.pct_change(window).iloc[-1]
        return momentum
    
    def calc_volatility(self, returns: pd.Series, window: int = 20) -> float:
        """
        计算波动率 (年化)
        
        Returns:
            年化波动率
        """
        if len(returns) < window:
            return 0.0
        
        daily_vol = returns.rolling(window).std().iloc[-1]
        annual_vol = daily_vol * np.sqrt(252)
        return annual_vol
    
    def calc_max_drawdown(self, prices: pd.Series, window: int = 252) -> float:
        """
        计算最大回撤 (近 1 年)
        
        Returns:
            最大回撤 (负数)
        """
        if len(prices) < window:
            return 0.0
        
        # 滚动最大回撤
        rolling_max = prices.rolling(window, min_periods=1).max()
        drawdown = (prices - rolling_max) / rolling_max
        
        return drawdown.min()
    
    def calc_sharpe_ratio(self, returns: pd.Series, window: int = 252, risk_free: float = 0.02) -> float:
        """
        计算夏普比率
        
        Args:
            returns: 日收益率序列
            window: 滚动窗口
            risk_free: 无风险利率 (年化)
            
        Returns:
            夏普比率
        """
        if len(returns) < window:
            return 0.0
        
        # 年化收益
        annual_return = returns.mean() * 252
        
        # 年化波动
        annual_vol = returns.std() * np.sqrt(252)
        
        if annual_vol == 0:
            return 0.0
        
        sharpe = (annual_return - risk_free) / annual_vol
        return sharpe
    
    def calc_relative_strength(self, index_prices: pd.Series, benchmark_prices: pd.Series) -> float:
        """
        计算相对强弱 (相对于沪深 300)
        
        Returns:
            相对强度比率
        """
        if len(index_prices) < 252 or len(benchmark_prices) < 252:
            return 1.0
        
        # 对齐索引
        common_idx = index_prices.index.intersection(benchmark_prices.index)
        if len(common_idx) < 252:
            return 1.0
        
        idx_prices = index_prices.loc[common_idx]
        bench_prices = benchmark_prices.loc[common_idx]
        
        # 计算相对价格比率
        ratio = idx_prices / bench_prices
        
        # 近 6 个月变化
        if len(ratio) < 126:
            return 1.0
        
        rs = ratio.iloc[-1] / ratio.iloc[-126]
        return rs
    
    def calc_turnover_percentile(self, volumes: pd.Series, window: int = 63) -> float:
        """
        计算换手率分位 (用成交量代理)
        
        Returns:
            0-1，越高表示交易越热
        """
        if len(volumes) < window:
            return 0.5
        
        current_vol = volumes.iloc[-1]
        historical_vol = volumes.iloc[-window:]
        
        percentile = (historical_vol < current_vol).mean()
        return percentile
    
    def calc_all_factors(self, 
                         price_df: pd.DataFrame, 
                         pe_df: pd.DataFrame,
                         benchmark_prices: Optional[pd.Series] = None) -> Dict[str, float]:
        """
        计算所有因子
        
        Returns:
            因子字典
        """
        factors = {}
        
        # 价格相关
        close = price_df['close']
        returns = close.pct_change().dropna()
        
        # 估值因子
        if not pe_df.empty:
            current_pe = pe_df['pe'].iloc[-1]
            current_pb = pe_df['pb'].iloc[-1]
            
            factors['pe_percentile'] = self.calc_pe_percentile(current_pe, pe_df['pe'])
            factors['pb_percentile'] = self.calc_pb_percentile(current_pb, pe_df['pb'])
            factors['dividend_yield'] = pe_df['dividend_yield'].iloc[-1] if 'dividend_yield' in pe_df else 0.0
        else:
            factors['pe_percentile'] = 0.5
            factors['pb_percentile'] = 0.5
            factors['dividend_yield'] = 0.0
        
        # 动量因子
        factors['momentum_6m'] = self.calc_momentum(close, 126)
        factors['momentum_12m'] = self.calc_momentum(close, 252)
        
        # 波动因子
        factors['volatility'] = self.calc_volatility(returns, 20)
        factors['max_drawdown'] = self.calc_max_drawdown(close, 252)
        factors['sharpe'] = self.calc_sharpe_ratio(returns, 252)
        
        # 相对强弱
        if benchmark_prices is not None:
            factors['relative_strength'] = self.calc_relative_strength(close, benchmark_prices)
        else:
            factors['relative_strength'] = 1.0
        
        # 情绪因子
        factors['turnover_percentile'] = self.calc_turnover_percentile(price_df['volume'], 63)
        
        logger.debug(f"Calculated factors: {factors}")

        return factors

    def normalize_factor(self,
                         factor_values: pd.Series,
                         method: str = 'robust') -> pd.Series:
        """
        因子归一化 (增强版)

        Args:
            factor_values: 因子值序列
            method: 'robust', 'quantile', 'zscore'

        Returns:
            归一化后的因子值
        """
        if factor_values.empty:
            return factor_values

        # 去极值 (3-sigma Winsorization)
        mean = factor_values.mean()
        std = factor_values.std()
        lower = mean - 3 * std
        upper = mean + 3 * std
        factor_clean = factor_values.clip(lower, upper)

        # 归一化
        try:
            if method == 'robust':
                scaler = RobustScaler()
            elif method == 'quantile':
                scaler = QuantileTransformer(output_distribution='normal', n_quantiles=100)
            else:  # zscore
                scaler = RobustScaler()  # fallback

            if factor_clean.ndim == 1:
                normalized = scaler.fit_transform(
                    factor_clean.values.reshape(-1, 1)
                ).flatten()
            else:
                normalized = scaler.fit_transform(factor_clean.values)

            return pd.Series(normalized, index=factor_values.index,
                           name=factor_values.name)
        except Exception as e:
            logger.warning(f"Normalization failed: {e}, returning original")
            return factor_values

    def neutralize_factor(self,
                          factor_values: pd.Series,
                          benchmark_returns: pd.Series,
                          market_cap: Optional[pd.Series] = None) -> pd.Series:
        """
        因子中性化 (去除市场和市值影响)

        Args:
            factor_values: 因子值
            benchmark_returns: 基准收益率
            market_cap: 市值 (可选)

        Returns:
            中性化后的因子 (回归残差)
        """
        # 对齐索引
        common_idx = factor_values.index
        if benchmark_returns is not None:
            common_idx = common_idx.intersection(benchmark_returns.index)
        if market_cap is not None:
            common_idx = common_idx.intersection(market_cap.index)

        if len(common_idx) < 30:
            logger.warning("Sample size too small for neutralization")
            return factor_values

        factor = factor_values.loc[common_idx].values
        market = benchmark_returns.loc[common_idx].values

        # 构建回归矩阵
        X = [market]
        if market_cap is not None:
            X.append(market_cap.loc[common_idx].values)
        X = np.column_stack(X)
        X = np.column_stack([np.ones(len(X)), X])

        try:
            # OLS 回归
            coeffs = np.linalg.lstsq(X, factor, rcond=None)[0]
            # 残差
            residuals = factor - X @ coeffs
            return pd.Series(residuals, index=common_idx,
                           name=f'{factor_values.name}_neutralized')
        except Exception as e:
            logger.error(f"Neutralization failed: {e}")
            return factor_values

    def calc_ic(self,
                factor_values: pd.Series,
                forward_returns: pd.Series,
                method: str = 'rank') -> Tuple[float, float]:
        """
        计算 IC (Information Coefficient)

        Args:
            factor_values: 因子值
            forward_returns: 未来收益率
            method: 'pearson' 或 'rank'

        Returns:
            (IC, IC_IR)
        """
        common_idx = factor_values.index.intersection(forward_returns.index)
        if len(common_idx) < 30:
            return 0.0, 0.0

        factor = factor_values.loc[common_idx]
        ret = forward_returns.loc[common_idx]

        try:
            if method == 'rank':
                ic = stats.spearmanr(factor, ret)[0]
            else:
                ic = stats.pearsonr(factor, ret)[0]

            if np.isnan(ic):
                return 0.0, 0.0

            ic_ir = abs(ic) / max(ic.std() if hasattr(ic, 'std') else 0.01, 0.01)
            return float(ic), float(ic_ir)
        except Exception as e:
            logger.warning(f"IC calculation failed: {e}")
            return 0.0, 0.0

    def factor_decay_analysis(self,
                              factor_values: pd.Series,
                              returns: pd.Series,
                              periods: List[int] = [1, 5, 10, 20]) -> Dict[int, float]:
        """
        因子衰减测试

        Args:
            factor_values: 因子值
            returns: 收益率序列
            periods: 测试的持有期

        Returns:
            {period: IC} 字典
        """
        results = {}

        for period in periods:
            forward_ret = returns.shift(-period)
            common_idx = factor_values.index.intersection(forward_ret.dropna().index)

            if len(common_idx) < 30:
                results[period] = 0.0
                continue

            ic, _ = self.calc_ic(factor_values.loc[common_idx],
                                 forward_ret.loc[common_idx])
            results[period] = ic

        return results
