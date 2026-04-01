"""
因子分析模块
支持 IC 分析、衰减测试、中性化等高级功能
"""
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import RobustScaler, QuantileTransformer, StandardScaler
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FactorAnalyzer:
    """
    因子分析器

    功能:
    - 因子归一化 (Robust/Quantile)
    - 因子中性化
    - IC 分析 (IC/IR)
    - 因子衰减测试
    - 因子相关性分析
    """

    def __init__(self, method: str = 'robust'):
        """
        Args:
            method: 归一化方法 ('robust', 'quantile', 'zscore')
        """
        self.method = method
        self.scaler = self._get_scaler(method)

    def _get_scaler(self, method: str):
        """获取归一化器"""
        if method == 'robust':
            return RobustScaler()
        elif method == 'quantile':
            return QuantileTransformer(output_distribution='normal', n_quantiles=100)
        elif method == 'zscore':
            return StandardScaler()
        else:
            logger.warning(f"Unknown method: {method}, using robust")
            return RobustScaler()

    def normalize(self, factor_values: pd.Series) -> pd.Series:
        """
        因子归一化

        Args:
            factor_values: 因子值序列

        Returns:
            归一化后的因子值
        """
        if factor_values.empty:
            return factor_values

        # 去极值 (3-sigma)
        factor_clean = self._winsorize(factor_values)

        # 归一化
        try:
            if factor_clean.ndim == 1:
                normalized = self.scaler.fit_transform(factor_clean.values.reshape(-1, 1)).flatten()
            else:
                normalized = self.scaler.fit_transform(factor_clean.values)

            return pd.Series(normalized, index=factor_values.index, name=factor_values.name)
        except Exception as e:
            logger.warning(f"Normalization failed: {e}, returning original")
            return factor_values

    def _winsorize(self, series: pd.Series, n_sigma: float = 3.0) -> pd.Series:
        """去极值 (Winsorization)"""
        mean = series.mean()
        std = series.std()

        lower_bound = mean - n_sigma * std
        upper_bound = mean + n_sigma * std

        return series.clip(lower_bound, upper_bound)

    def neutralize(
        self,
        factor_values: pd.Series,
        benchmark_returns: pd.Series,
        market_cap: Optional[pd.Series] = None
    ) -> pd.Series:
        """
        因子中性化 (去除市场和市值影响)

        Args:
            factor_values: 因子值
            benchmark_returns: 基准收益率 (市场因子)
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

        # 添加常数项
        X = np.column_stack([np.ones(len(X)), X])

        try:
            # OLS 回归
            coeffs = np.linalg.lstsq(X, factor, rcond=None)[0]

            # 计算残差
            predicted = X @ coeffs
            residuals = factor - predicted

            return pd.Series(residuals, index=common_idx, name=f'{factor_values.name}_neutralized')

        except Exception as e:
            logger.error(f"Neutralization failed: {e}")
            return factor_values

    def calc_ic(
        self,
        factor_values: pd.Series,
        forward_returns: pd.Series,
        method: str = 'rank'
    ) -> Tuple[float, float]:
        """
        计算 IC (Information Coefficient)

        Args:
            factor_values: 因子值
            forward_returns: 未来收益率
            method: 'pearson' 或 'rank'

        Returns:
            (IC, IC_IR)
        """
        # 对齐
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

            # IC_IR (IC 均值/标准差)
            ic_ir = ic / max(abs(ic), 0.01)  # 简化计算

            return float(ic), float(ic_ir)

        except Exception as e:
            logger.warning(f"IC calculation failed: {e}")
            return 0.0, 0.0

    def calc_ic_time_series(
        self,
        factor_df: pd.DataFrame,
        forward_returns: pd.Series,
        method: str = 'rank'
    ) -> pd.DataFrame:
        """
        计算 IC 时间序列

        Args:
            factor_df: 因子值 DataFrame (columns 为不同因子)
            forward_returns: 未来收益率

        Returns:
            IC 时间序列 DataFrame
        """
        results = {'date': [], 'ic': [], 'factor': []}

        for factor_name in factor_df.columns:
            factor = factor_df[factor_name]
            common_idx = factor.index.intersection(forward_returns.index)

            if len(common_idx) < 30:
                continue

            # 滚动 IC
            for i in range(30, len(common_idx)):
                window_idx = common_idx[i-30:i]
                window_ret = forward_returns.loc[window_idx]
                window_factor = factor.loc[window_idx]

                if method == 'rank':
                    ic = stats.spearmanr(window_factor, window_ret)[0]
                else:
                    ic = stats.pearsonr(window_factor, window_ret)[0]

                if not np.isnan(ic):
                    results['date'].append(common_idx[i])
                    results['ic'].append(ic)
                    results['factor'].append(factor_name)

        return pd.DataFrame(results)

    def factor_decay(
        self,
        factor_values: pd.Series,
        returns: pd.Series,
        periods: List[int] = [1, 5, 10, 20]
    ) -> Dict[int, float]:
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
            # 向前平移 returns
            forward_ret = returns.shift(-period)
            common_idx = factor_values.index.intersection(forward_ret.dropna().index)

            if len(common_idx) < 30:
                results[period] = 0.0
                continue

            ic, _ = self.calc_ic(
                factor_values.loc[common_idx],
                forward_ret.loc[common_idx]
            )
            results[period] = ic

        return results

    def correlation_matrix(self, factor_df: pd.DataFrame) -> pd.DataFrame:
        """
        计算因子相关性矩阵

        Args:
            factor_df: 因子值 DataFrame

        Returns:
            相关性矩阵
        """
        # 先归一化
        normalized = factor_df.copy()
        for col in factor_df.columns:
            normalized[col] = self.normalize(factor_df[col])

        return normalized.corr()

    def get_factor_stats(self, factor_values: pd.Series) -> Dict:
        """获取因子统计特征"""
        return {
            'mean': float(factor_values.mean()),
            'std': float(factor_values.std()),
            'skew': float(stats.skew(factor_values)),
            'kurtosis': float(stats.kurtosis(factor_values)),
            'min': float(factor_values.min()),
            'max': float(factor_values.max()),
            'median': float(factor_values.median()),
            'null_ratio': float(factor_values.isnull().mean())
        }
