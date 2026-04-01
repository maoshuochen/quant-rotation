"""
因子计算引擎
支持因子计算、归一化、中性化、IC 分析
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, List, Tuple
from sklearn.preprocessing import RobustScaler, QuantileTransformer
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class FactorEngine:
    """
    因子计算器

    功能:
    - 估值因子 (PE/PB 分位)
    - 动量因子 (6 月/12 月收益率)
    - 波动因子 (波动率、最大回撤、夏普比率)
    - 相对强弱
    - 换手率分位
    """

    def __init__(self, lookback_days: int = 2520):
        self.lookback = lookback_days
        self._scalers: Dict[str, object] = {}

    def calc_pe_percentile(self, current_pe: float, pe_history: pd.Series) -> float:
        """
        计算 PE 历史分位

        Returns:
            0-1 之间，越低表示估值越低
        """
        if pe_history.empty or current_pe is None:
            return 0.5

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

        annual_return = returns.mean() * 252
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

        common_idx = index_prices.index.intersection(benchmark_prices.index)
        if len(common_idx) < 252:
            return 1.0

        idx_prices = index_prices.loc[common_idx]
        bench_prices = benchmark_prices.loc[common_idx]

        ratio = idx_prices / bench_prices

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

        close = price_df['close']
        returns = close.pct_change().dropna()

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

        factors['momentum_6m'] = self.calc_momentum(close, 126)
        factors['momentum_12m'] = self.calc_momentum(close, 252)
        factors['volatility'] = self.calc_volatility(returns, 20)
        factors['max_drawdown'] = self.calc_max_drawdown(close, 252)
        factors['sharpe'] = self.calc_sharpe_ratio(returns, 252)

        if benchmark_prices is not None:
            factors['relative_strength'] = self.calc_relative_strength(close, benchmark_prices)
        else:
            factors['relative_strength'] = 1.0

        factors['turnover_percentile'] = self.calc_turnover_percentile(price_df['volume'], 63)

        logger.debug(f"Calculated factors: {factors}")
        return factors

    # ==================== 因子处理功能 (增强版) ====================

    def winsorize(self, factor: pd.Series, method: str = 'mad', n_std: float = 3.0) -> pd.Series:
        """
        去极值

        Args:
            factor: 因子序列
            method: 'mad', 'percentile', 'zscore'
            n_std: 去极值标准差倍数

        Returns:
            去极值后的因子
        """
        if method == 'mad':
            return self._winsorize_mad(factor, n_std)
        elif method == 'percentile':
            return self._winsorize_percentile(factor)
        elif method == 'zscore':
            return self._winsorize_zscore(factor, n_std)
        return factor

    def _winsorize_mad(self, factor: pd.Series, n_std: float) -> pd.Series:
        """MAD 去极值"""
        median = factor.median()
        mad = (factor - median).abs().median()

        if mad == 0:
            return factor

        limit = median + n_std * 1.4826 * mad
        return factor.clip(lower=median - limit, upper=limit)

    def _winsorize_percentile(self, factor: pd.Series) -> pd.Series:
        """百分位去极值"""
        return factor.clip(lower=factor.quantile(0.01), upper=factor.quantile(0.99))

    def _winsorize_zscore(self, factor: pd.Series, n_std: float) -> pd.Series:
        """3-sigma 去极值"""
        mean, std = factor.mean(), factor.std()
        if std == 0:
            return factor
        limit = n_std * std
        return factor.clip(lower=mean - limit, upper=mean + limit)

    def normalize(self, factor: pd.Series, method: str = 'robust', key: str = 'default') -> pd.Series:
        """
        归一化

        Args:
            factor: 因子序列
            method: 'robust', 'zscore', 'quantile'
            key: 缩放器缓存键

        Returns:
            归一化后的因子
        """
        if method == 'robust':
            return self._normalize_robust(factor, key)
        elif method == 'zscore':
            return self._normalize_zscore(factor)
        elif method == 'quantile':
            return self._normalize_quantile(factor, key)
        return factor

    def _normalize_robust(self, factor: pd.Series, key: str) -> pd.Series:
        """RobustScaler 归一化"""
        values = factor.values.reshape(-1, 1)
        if key not in self._scalers:
            self._scalers[key] = RobustScaler()
            normalized = self._scalers[key].fit_transform(values)
        else:
            normalized = self._scalers[key].transform(values)
        return pd.Series(normalized.flatten(), index=factor.index)

    def _normalize_zscore(self, factor: pd.Series) -> pd.Series:
        """Z-score 归一化"""
        mean, std = factor.mean(), factor.std()
        if std == 0:
            return factor
        return (factor - mean) / std

    def _normalize_quantile(self, factor: pd.Series, key: str) -> pd.Series:
        """QuantileTransformer 归一化"""
        values = factor.values.reshape(-1, 1)
        if key not in self._scalers:
            self._scalers[key] = QuantileTransformer(output_distribution='normal')
            normalized = self._scalers[key].fit_transform(values)
        else:
            normalized = self._scalers[key].transform(values)
        return pd.Series(normalized.flatten(), index=factor.index)

    def neutralize(self, factor: pd.Series, exposures: Dict[str, pd.Series]) -> pd.Series:
        """
        因子中性化 - 去除其他因子/风格暴露

        Args:
            factor: 原始因子
            exposures: 风险暴露字典 {'market': series, 'size': series, ...}

        Returns:
            中性化后的因子
        """
        common_idx = factor.index
        for name, exp in exposures.items():
            common_idx = common_idx.intersection(exp.index)

        f = factor.loc[common_idx].dropna()
        if len(f) < 30:
            logger.warning("样本不足，无法中性化")
            return factor

        X_data = []
        for name, exp in exposures.items():
            e = exp.loc[common_idx].dropna()
            if len(e) == len(f):
                X_data.append(e.values)

        if not X_data:
            return factor

        X = np.column_stack(X_data)
        y = f.values

        mask = np.all(np.isfinite(X), axis=1) & np.isfinite(y)
        X, y = X[mask], y[mask]

        if len(y) < 30:
            return factor

        X_with_const = np.column_stack([np.ones(len(X)), X])
        try:
            beta = np.linalg.lstsq(X_with_const, y, rcond=None)[0]
            residuals = y - X_with_const @ beta

            neutralized = factor.copy()
            neutralized.loc[common_idx[mask]] = residuals
            logger.info(f"因子中性化完成，残差标准差：{residuals.std():.4f}")
            return neutralized

        except Exception as e:
            logger.error(f"因子中性化失败：{e}")
            return factor

    def process(self, factor: pd.Series, key: str = 'default',
                winsorize_method: str = 'mad', normalize_method: str = 'robust') -> pd.Series:
        """
        完整处理流程：去极值 -> 归一化

        Args:
            factor: 原始因子
            key: 缩放器缓存键
            winsorize_method: 去极值方法
            normalize_method: 归一化方法

        Returns:
            处理后的因子
        """
        processed = self.winsorize(factor, method=winsorize_method)
        processed = self.normalize(processed, method=normalize_method, key=key)
        return processed

    # ==================== IC 分析 ====================

    def calc_ic(self, factor_values: pd.Series, forward_returns: pd.Series,
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

    def factor_decay_analysis(self, factor_values: pd.Series, returns: pd.Series,
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

            ic, _ = self.calc_ic(factor_values.loc[common_idx], forward_ret.loc[common_idx])
            results[period] = ic

        return results


def create_factor_engine(
        winsorize_method: str = 'mad',
        normalize_method: str = 'robust') -> FactorEngine:
    """创建因子引擎"""
    return FactorEngine()
