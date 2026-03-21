"""
因子计算引擎
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional
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
