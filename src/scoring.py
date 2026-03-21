"""
评分系统 - 将因子转化为综合得分
"""
from typing import Dict, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FactorWeight:
    """因子权重配置"""
    name: str
    weight: float
    direction: int  # 1=越高越好，-1=越低越好


class ScoringEngine:
    """评分引擎"""
    
    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or {
            'value': 0.25,
            'momentum': 0.20,
            'volatility': 0.15,
            'flow': 0.15,
            'fundamental': 0.15,
            'sentiment': 0.10,
        }
    
    def normalize(self, value: float, min_val: float, max_val: float, 
                  direction: int = 1) -> float:
        """
        归一化到 0-1
        
        Args:
            value: 原始值
            min_val: 最小值
            max_val: 最大值
            direction: 1=越高越好，-1=越低越好
            
        Returns:
            归一化后的值 (0-1)
        """
        if max_val == min_val:
            return 0.5
        
        normalized = (value - min_val) / (max_val - min_val)
        normalized = max(0, min(1, normalized))  # 截断到 0-1
        
        if direction == -1:
            normalized = 1 - normalized
        
        return normalized
    
    def calc_value_score(self, factors: Dict[str, float]) -> float:
        """
        估值得分
        
        PE/PB 分位越低，得分越高
        """
        pe_percentile = factors.get('pe_percentile', 0.5)
        pb_percentile = factors.get('pb_percentile', 0.5)
        
        # 分位越低得分越高
        pe_score = 1 - pe_percentile
        pb_score = 1 - pb_percentile
        
        # 股息率 (越高越好)
        div_yield = factors.get('dividend_yield', 0)
        div_score = min(1, div_yield / 5)  # 假设 5% 是满分
        
        value_score = pe_score * 0.5 + pb_score * 0.3 + div_score * 0.2
        return value_score
    
    def calc_momentum_score(self, factors: Dict[str, float]) -> float:
        """
        动量得分
        
        收益率越高，得分越高
        """
        mom_6m = factors.get('momentum_6m', 0)
        mom_12m = factors.get('momentum_12m', 0)
        rs = factors.get('relative_strength', 1)
        
        # 归一化动量 (假设 -50% ~ +50% 范围)
        mom_6m_score = self.normalize(mom_6m, -0.5, 0.5, 1)
        mom_12m_score = self.normalize(mom_12m, -0.5, 0.5, 1)
        
        # 相对强弱 (假设 0.8 ~ 1.2 范围)
        rs_score = self.normalize(rs, 0.8, 1.2, 1)
        
        momentum_score = mom_6m_score * 0.5 + mom_12m_score * 0.3 + rs_score * 0.2
        return momentum_score
    
    def calc_volatility_score(self, factors: Dict[str, float]) -> float:
        """
        波动得分
        
        波动越低、回撤越小，得分越高
        """
        vol = factors.get('volatility', 0.3)
        mdd = factors.get('max_drawdown', -0.3)
        sharpe = factors.get('sharpe', 0)
        
        # 波动率归一化 (假设 10% ~ 50% 范围)
        vol_score = self.normalize(vol, 0.1, 0.5, -1)
        
        # 最大回撤归一化 (假设 -50% ~ 0 范围)
        mdd_score = self.normalize(mdd, -0.5, 0, 1)
        
        # 夏普比率归一化 (假设 -1 ~ 2 范围)
        sharpe_score = self.normalize(sharpe, -1, 2, 1)
        
        volatility_score = vol_score * 0.4 + mdd_score * 0.4 + sharpe_score * 0.2
        return volatility_score
    
    def calc_sentiment_score(self, factors: Dict[str, float]) -> float:
        """
        情绪得分
        
        换手率适中最好 (避免过热)
        """
        turnover = factors.get('turnover_percentile', 0.5)
        
        # 换手率分位适中最好 (0.3-0.7 之间最佳)
        if 0.3 <= turnover <= 0.7:
            sentiment_score = 1.0
        elif turnover < 0.3:
            sentiment_score = turnover / 0.3
        else:
            sentiment_score = (1 - turnover) / 0.3
        
        return sentiment_score
    
    def calc_score(self, factors: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
        """
        计算综合得分
        
        Returns:
            (总分，各维度得分字典)
        """
        scores = {}
        
        scores['value'] = self.calc_value_score(factors)
        scores['momentum'] = self.calc_momentum_score(factors)
        scores['volatility'] = self.calc_volatility_score(factors)
        scores['sentiment'] = self.calc_sentiment_score(factors)
        
        # 资金和基本面暂时用动量代理 (后续可扩展)
        scores['flow'] = scores['momentum'] * 0.8
        scores['fundamental'] = scores['value'] * 0.8 + scores['volatility'] * 0.2
        
        # 加权综合
        total_score = sum(
            scores[dim] * self.weights[dim]
            for dim in self.weights.keys()
        )
        
        logger.debug(f"Total score: {total_score:.3f}, Breakdown: {scores}")
        
        return total_score, scores
    
    def rank_indices(self, index_scores: Dict[str, float]) -> List[Tuple[str, float]]:
        """
        对指数排序
        
        Returns:
            [(指数代码，得分), ...] 从高到低
        """
        ranked = sorted(index_scores.items(), key=lambda x: x[1], reverse=True)
        return ranked
