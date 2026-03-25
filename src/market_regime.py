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
        判断当前市场状态
        
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
        
        # 判断逻辑
        if price_vs_ma200 > 0.10 and ma200_slope > 0.02 and returns_6m > 0.15:
            # 牛市：价格在 MA200 上方 10%+，MA200 向上，6 个月收益 15%+
            logger.info("市场状态：牛市 🐂")
            return 'bull'
        elif price_vs_ma200 < -0.10 and ma200_slope < -0.02 and returns_6m < -0.15:
            # 熊市：价格在 MA200 下方 10%+，MA200 向下，6 个月收益 -15% 以下
            logger.info("市场状态：熊市 🐻")
            return 'bear'
        elif volatility_30d > 0.35:
            # 高波动也视为震荡市
            logger.info("市场状态：震荡市（高波动）〰️")
            return 'sideways'
        else:
            logger.info("市场状态：震荡市 〰️")
            return 'sideways'
    
    def get_dynamic_weights(self, regime: str, base_weights: Dict[str, float]) -> Dict[str, float]:
        """
        根据市场状态返回动态因子权重
        
        参数:
            regime: 市场状态 ('bull', 'bear', 'sideways')
            base_weights: 基础权重配置
        
        返回:
            调整后的权重字典
        """
        # 牛市配置：进攻型，重视动量和趋势
        bull_weights = {
            'momentum': 0.30,       # +10%
            'trend': 0.25,          # +5%
            'value': 0.15,          # -10%
            'volatility': 0.10,     # -5%
            'relative_strength': 0.15,  # -5%
            'flow': 0.05            # -10%
        }
        
        # 熊市配置：防御型，重视估值和低波
        bear_weights = {
            'momentum': 0.10,       # -10%
            'trend': 0.10,          # -10%
            'value': 0.35,          # +10%
            'volatility': 0.25,     # +10%
            'relative_strength': 0.10,  # -10%
            'flow': 0.10            # -5%
        }
        
        # 震荡市配置：平衡型，重视资金流和相对强弱
        sideways_weights = {
            'momentum': 0.15,       # -5%
            'trend': 0.15,          # -5%
            'value': 0.25,          # 0%
            'volatility': 0.15,     # 0%
            'relative_strength': 0.15,  # -5%
            'flow': 0.15            # 0%
        }
        
        regime_map = {
            'bull': bull_weights,
            'bear': bear_weights,
            'sideways': sideways_weights
        }
        
        regime_weights = regime_map.get(regime, sideways_weights)
        
        # 只保留配置中存在的因子
        final_weights = {}
        for key in base_weights.keys():
            if key in regime_weights:
                final_weights[key] = regime_weights[key]
            else:
                final_weights[key] = base_weights[key]
        
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
        self.current_weights = self.regime_detector.get_dynamic_weights(
            self.current_regime, 
            self.weights
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
