"""
市场状态判断与因子动态权重
"""
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# 导入基础评分引擎
from src.scoring_baostock import ScoringEngine


class MarketRegimeDetector:
    """市场状态检测器"""
    
    def __init__(self, benchmark_code: str = '000300.SH'):
        self.benchmark_code = benchmark_code  # 沪深 300 作为基准
    
    def detect_regime(self, benchmark_prices: pd.Series) -> str:
        """
        判断当前市场状态（打分制）

        参数:
            benchmark_prices: 基准指数价格序列

        返回:
            'bull' (牛市), 'bear' (熊市), 'sideways' (震荡市)
        """
        if len(benchmark_prices) < 252:
            logger.warning("数据不足，使用默认震荡市")
            return 'sideways'

        # 1. 价格相对 MA200 位置
        ma200 = benchmark_prices.rolling(200).mean()
        current_price = benchmark_prices.iloc[-1]
        price_vs_ma200 = (current_price - ma200.iloc[-1]) / ma200.iloc[-1]

        # 2. MA200 斜率 (趋势方向)
        ma200_20d_ago = ma200.iloc[-20] if len(ma200) >= 20 else ma200.iloc[-1]
        ma200_slope = (ma200.iloc[-1] - ma200_20d_ago) / ma200_20d_ago

        # 3. 6 个月收益率
        returns_6m = (current_price - benchmark_prices.iloc[-126]) / benchmark_prices.iloc[-126] if len(benchmark_prices) >= 126 else 0

        # 4. 波动率 (VIX 代理)
        returns = benchmark_prices.pct_change()
        volatility_30d = returns.iloc[-30:].std() * np.sqrt(252) if len(returns) >= 30 else 0.2

        logger.info(f"市场指标：价格 vs MA200={price_vs_ma200:.2%}, MA200 斜率={ma200_slope:.2%}, 6M 收益={returns_6m:.2%}, 波动率={volatility_30d:.2%}")

        # ===== 打分制 =====
        # 每个指标 -1 到 +1 分，根据程度连续打分

        # 1. 价格位置分：-10% 得 -1 分，+10% 得 +1 分，线性插值
        price_score = max(-1, min(1, price_vs_ma200 / 0.10))

        # 2. 均线斜率分：-2% 得 -1 分，+2% 得 +1 分，线性插值
        slope_score = max(-1, min(1, ma200_slope / 0.02))

        # 3. 动量分：-15% 得 -1 分，+15% 得 +1 分，线性插值
        momentum_score = max(-1, min(1, returns_6m / 0.15))

        # 4. 波动率惩罚：>35% 时扣分
        volatility_penalty = 0.5 if volatility_30d > 0.35 else 0

        # 综合得分 (-3 到 +3)
        total_score = price_score + slope_score + momentum_score - volatility_penalty

        logger.info(f"打分：价格={price_score:.2f}, 斜率={slope_score:.2f}, 动量={momentum_score:.2f}, 波动惩罚={volatility_penalty:.2f}, 总分={total_score:.2f}")

        # 根据总分判断
        if total_score >= 1.5:
            regime = 'bull'
            regime_name = '牛市 🐂'
        elif total_score <= -1.5:
            regime = 'bear'
            regime_name = '熊市 🐻'
        else:
            regime = 'sideways'
            if volatility_30d > 0.35:
                regime_name = '震荡市（高波动）〰️'
            else:
                regime_name = '震荡市 〰️'

        logger.info(f"市场状态：{regime_name}")
        return regime
    
    def get_dynamic_weights(self, regime: str, base_weights: Dict[str, float]) -> Dict[str, float]:
        """
        根据市场状态返回动态因子权重

        参数:
            regime: 市场状态 ('bull', 'bear', 'sideways')
            base_weights: 基础权重配置

        返回:
            调整后的权重字典（仅包含活跃因子，已归一化）
        """
        # 只处理活跃因子 (momentum, trend, flow)
        active_factors = ['momentum', 'trend', 'flow']

        # 牛市：进攻型，重视动量和趋势
        # 熊市：防御型，重视资金流
        # 震荡市：平衡型，重视资金流

        adjustments = {
            'bull': {
                'momentum': 1.5,    # +50%
                'trend': 1.3,       # +30%
                'flow': 1.2         # +20%
            },
            'bear': {
                'momentum': 0.5,    # -50%
                'trend': 0.5,       # -50%
                'flow': 1.3         # +30%
            },
            'sideways': {
                'momentum': 0.8,    # -20%
                'trend': 0.8,       # -20%
                'flow': 1.5         # +50%
            }
        }.get(regime, {'momentum': 1.0, 'trend': 1.0, 'flow': 1.0})

        # 只对活跃因子应用调整
        final_weights = {}
        for factor in active_factors:
            base_weight = base_weights.get(factor, 0)
            if base_weight > 0:
                adjustment = adjustments.get(factor, 1.0)
                final_weights[factor] = base_weight * adjustment

        # 归一化（确保总和为 1）
        total = sum(final_weights.values())
        if total > 0:
            final_weights = {k: v / total for k, v in final_weights.items()}

        logger.info(f"动态权重 ({regime}): {final_weights}")
        return final_weights


class DynamicWeightScoringEngine(ScoringEngine):
    """动态权重评分引擎（继承基础评分引擎）"""
    
    def __init__(self, config: Dict[str, any]):
        # 调用父类初始化
        super().__init__(config)
        
        self.regime_detector = MarketRegimeDetector()
        self.current_regime = 'sideways'
        self.current_weights = self.weights.copy()
        self.benchmark_prices = None
    
    def update_market_regime(self, benchmark_prices: pd.Series):
        """更新市场状态和权重"""
        self.benchmark_prices = benchmark_prices
        self.current_regime = self.regime_detector.detect_regime(benchmark_prices)
        # 使用完整的 factor_weights 配置作为基础权重
        self.current_weights = self.regime_detector.get_dynamic_weights(
            self.current_regime,
            self.weights  # 直接使用父类的 weights（从 config 加载）
        )
    
    def get_current_weights(self) -> Dict[str, float]:
        """获取当前权重"""
        return self.current_weights
    
    def get_regime_description(self) -> str:
        """获取市场状态描述"""
        descriptions = {
            'bull': '牛市 🐂 - 进攻型配置，重视动量和趋势',
            'bear': '熊市 🐻 - 防御型配置，重视估值和低波',
            'sideways': '震荡市 〰️ - 平衡型配置，重视资金流'
        }
        return descriptions.get(self.current_regime, '未知')
