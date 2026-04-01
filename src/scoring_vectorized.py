"""
向量化评分引擎
使用批量向量化计算加速因子和评分
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class VectorizedScoringEngine:
    """
    向量化评分引擎

    相比传统循环方式:
    - 使用 pandas 向量化操作
    - 批量计算所有指数因子
    - 减少重复计算
    """

    def __init__(self, config: dict):
        self.config = config
        self.factor_weights = config.get('factor_weights', {})

    def batch_compute_factors(
        self,
        etf_data_dict: Dict[str, pd.DataFrame],
        benchmark: pd.DataFrame
    ) -> pd.DataFrame:
        """
        批量计算所有指数因子

        Args:
            etf_data_dict: {code: DataFrame} 字典
            benchmark: 基准数据

        Returns:
            因子 DataFrame (index=code, columns=factors)
        """
        factors = {}

        # 合并所有数据便于向量化计算
        close_prices = pd.DataFrame({
            code: df['close'] for code, df in etf_data_dict.items()
        })
        volumes = pd.DataFrame({
            code: df['volume'] for code, df in etf_data_dict.items()
        })

        # 计算收益率
        returns = close_prices.pct_change()

        # 1. 动量因子 (6 月收益率)
        momentum = close_prices.pct_change(126).iloc[-1]
        factors['momentum'] = momentum

        # 2. 波动率因子 (年化波动率)
        volatility = returns.rolling(20).std().iloc[-1] * np.sqrt(252)
        # 波动率越低分越高
        factors['volatility_score'] = 1 - (volatility - volatility.min()) / (volatility.max() - volatility.min() + 1e-10)

        # 3. 趋势因子 (MA20 位置)
        ma20 = close_prices.rolling(20).mean()
        trend = (close_prices.iloc[-1] - ma20.iloc[-1]) / ma20.iloc[-1]
        factors['trend'] = trend

        # 4. 成交量趋势
        vol_ma20 = volumes.rolling(20).mean()
        vol_trend = (volumes.iloc[-1] - vol_ma20.iloc[-1]) / vol_ma20.iloc[-1]
        factors['volume_trend'] = vol_trend

        # 5. 相对强弱 (相对于基准)
        if not benchmark.empty and 'close' in benchmark.columns:
            for code in close_prices.columns:
                common_idx = close_prices[code].index.intersection(benchmark.index)
                if len(common_idx) >= 126:
                    ratio = close_prices[code].loc[common_idx] / benchmark['close'].loc[common_idx]
                    rs = ratio.iloc[-1] / ratio.iloc[-126] - 1
                    factors[f'rs_{code}'] = rs

        return pd.DataFrame([factors])

    def compute_composite_score(
        self,
        factor_df: pd.DataFrame,
        weights: Optional[Dict[str, float]] = None
    ) -> pd.DataFrame:
        """
        计算综合评分

        Args:
            factor_df: 因子 DataFrame
            weights: 因子权重

        Returns:
            综合评分
        """
        weights = weights or self.factor_weights

        # 归一化因子 (0-1)
        normalized = factor_df.copy()
        for col in factor_df.columns:
            if col.startswith('rs_'):
                continue  # 跳过相对强弱

            col_min = factor_df[col].min()
            col_max = factor_df[col].max()

            if col_max - col_min > 0:
                # 波动率和估值因子反向得分
                if col in ['volatility', 'pe_percentile']:
                    normalized[col] = 1 - (factor_df[col] - col_min) / (col_max - col_min)
                else:
                    normalized[col] = (factor_df[col] - col_min) / (col_max - col_min)
            else:
                normalized[col] = 0.5

        # 加权计算
        score = 0
        total_weight = 0

        for factor, weight in weights.items():
            if factor in normalized.columns:
                score += normalized[factor] * weight
                total_weight += weight

        if total_weight > 0:
            score = score / total_weight

        return score * 100  # 转为 0-100 分

    def rank_indices(self, scores: pd.Series) -> pd.DataFrame:
        """
        排名指数

        Args:
            scores: 评分 Series

        Returns:
            排名 DataFrame
        """
        ranking = scores.sort_values(ascending=False).to_frame(name='score')
        ranking['rank'] = ranking['score'].rank(ascending=False, method='first').astype(int)
        return ranking.reset_index().rename(columns={'index': 'code'})
