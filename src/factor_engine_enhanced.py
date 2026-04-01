"""
增强的因子工程模块
带去极值、归一化、中性化功能
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from sklearn.preprocessing import RobustScaler, StandardScaler, QuantileTransformer
import logging

logger = logging.getLogger(__name__)


class EnhancedFactorEngine:
    """
    增强因子引擎

    功能:
    - 去极值 (MAD/Percentile/Z-score)
    - 归一化 (Robust/Z-score/Quantile)
    - 中性化 (市场/市值中性)
    - 因子标准化流程
    """

    def __init__(self,
                 winsorize_method: str = 'mad',
                 normalize_method: str = 'robust',
                 n_std: float = 3.0):
        """
        Args:
            winsorize_method: 'mad', 'percentile', 'zscore'
            normalize_method: 'robust', 'zscore', 'quantile'
            n_std: 去极值标准差倍数
        """
        self.winsorize_method = winsorize_method
        self.normalize_method = normalize_method
        self.n_std = n_std
        self._scalers: Dict[str, object] = {}

    def winsorize(self, factor: pd.Series) -> pd.Series:
        """去极值"""
        if self.winsorize_method == 'mad':
            return self._winsorize_mad(factor)
        elif self.winsorize_method == 'percentile':
            return self._winsorize_percentile(factor)
        elif self.winsorize_method == 'zscore':
            return self._winsorize_zscore(factor)
        return factor

    def _winsorize_mad(self, factor: pd.Series) -> pd.Series:
        """MAD 去极值"""
        median = factor.median()
        mad = (factor - median).abs().median()

        if mad == 0:
            return factor

        limit = median + self.n_std * 1.4826 * mad
        return factor.clip(lower=median - limit, upper=limit)

    def _winsorize_percentile(self, factor: pd.Series) -> pd.Series:
        """百分位去极值"""
        return factor.clip(lower=factor.quantile(0.01), upper=factor.quantile(0.99))

    def _winsorize_zscore(self, factor: pd.Series) -> pd.Series:
        """3-sigma 去极值"""
        mean, std = factor.mean(), factor.std()
        if std == 0:
            return factor
        limit = self.n_std * std
        return factor.clip(lower=mean - limit, upper=mean + limit)

    def normalize(self, factor: pd.Series, key: str = 'default') -> pd.Series:
        """归一化"""
        if self.normalize_method == 'robust':
            return self._normalize_robust(factor, key)
        elif self.normalize_method == 'zscore':
            return self._normalize_zscore(factor)
        elif self.normalize_method == 'quantile':
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

    def neutralize(self,
                   factor: pd.Series,
                   exposures: Dict[str, pd.Series]) -> pd.Series:
        """
        因子中性化 - 去除其他因子/风格暴露

        Args:
            factor: 原始因子
            exposures: 风险暴露字典 {'market': series, 'size': series, ...}

        Returns:
            中性化后的因子
        """
        # 对齐索引
        common_idx = factor.index
        for name, exp in exposures.items():
            common_idx = common_idx.intersection(exp.index)

        f = factor.loc[common_idx].dropna()
        if len(f) < 30:
            logger.warning("样本不足，无法中性化")
            return factor

        # 构建暴露矩阵
        X_data = []
        for name, exp in exposures.items():
            e = exp.loc[common_idx].dropna()
            if len(e) == len(f):
                X_data.append(e.values)

        if not X_data:
            return factor

        X = np.column_stack(X_data)
        y = f.values

        # 去除 NaN
        mask = np.all(np.isfinite(X), axis=1) & np.isfinite(y)
        X, y = X[mask], y[mask]

        if len(y) < 30:
            return factor

        # OLS 回归获取残差
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

    def process(self, factor: pd.Series, key: str = 'default') -> pd.Series:
        """完整处理流程：去极值 -> 归一化"""
        processed = self.winsorize(factor)
        processed = self.normalize(processed, key)
        return processed


def create_factor_engine(
        winsorize_method: str = 'mad',
        normalize_method: str = 'robust') -> EnhancedFactorEngine:
    """创建因子引擎"""
    return EnhancedFactorEngine(winsorize_method, normalize_method)
