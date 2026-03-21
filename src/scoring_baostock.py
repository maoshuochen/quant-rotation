"""
评分系统 - 适配 Baostock (ETF 数据)
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ScoringEngine:
    """评分引擎 - 基于 ETF 数据"""
    
    def __init__(self, config: dict):
        self.config = config
        self.weights = config.get('factor_weights', {})
    
    def calc_momentum_score(self, returns: pd.Series) -> float:
        """
        动量评分 (6 个月收益率)
        归一化到 0-1
        """
        if len(returns) < 126:
            return 0.5
        
        momentum_6m = returns.iloc[-126:].sum()
        
        # 简单归一化 (-0.5 ~ 0.5 -> 0 ~ 1)
        score = 0.5 + momentum_6m
        return max(0, min(1, score))
    
    def calc_volatility_score(self, returns: pd.Series) -> float:
        """
        波动率评分 (低波动高分)
        """
        if len(returns) < 20:
            return 0.5
        
        volatility = returns.std() * np.sqrt(252)  # 年化
        
        # 波动率越低分越高 (假设合理波动率 0.1-0.4)
        # 0.1 -> 1.0, 0.4 -> 0.0
        score = 1.0 - (volatility - 0.1) / 0.3
        return max(0, min(1, score))
    
    def calc_trend_score(self, prices: pd.Series) -> float:
        """
        趋势评分 (价格在 MA 上方)
        """
        if len(prices) < 60:
            return 0.5
        
        ma20 = prices.rolling(20).mean().iloc[-1]
        ma60 = prices.rolling(60).mean().iloc[-1]
        current = prices.iloc[-1]
        
        # 价格在 MA20 和 MA60 上方得高分
        score = 0.5
        if current > ma20:
            score += 0.25
        if current > ma60:
            score += 0.25
        
        return min(1, score)
    
    def calc_relative_strength(self, prices: pd.Series, benchmark_prices: pd.Series) -> float:
        """
        相对强弱 (相对于基准)
        """
        if len(prices) < 60 or len(benchmark_prices) < 60:
            return 1.0
        
        # 对齐
        common_idx = prices.index.intersection(benchmark_prices.index)
        if len(common_idx) < 60:
            return 1.0
        
        prices_aligned = prices.loc[common_idx]
        bench_aligned = benchmark_prices.loc[common_idx]
        
        # 计算相对强度
        ratio = prices_aligned / bench_aligned
        rs_60d = ratio.iloc[-1] / ratio.iloc[-60]
        
        # 归一化
        score = 0.5 + (rs_60d - 1) * 2
        return max(0, min(1, score))
    
    def calc_value_score(self, prices: pd.Series) -> float:
        """
        估值评分 (简化版：用价格分位代替 PE 分位)
        假设近 3 年价格区间
        """
        if len(prices) < 252:
            lookback = len(prices)
        else:
            lookback = 252
        
        recent_prices = prices.iloc[-lookback:]
        current = prices.iloc[-1]
        
        # 计算价格在历史中的分位
        percentile = (recent_prices < current).mean()
        
        # 分位越低 (价格越低) 得分越高
        score = 1.0 - percentile
        return score
    
    def calc_flow_score(self, 
                        prices: pd.Series, 
                        volumes: pd.Series,
                        amounts: Optional[pd.Series] = None,
                        northbound_metrics: Optional[Dict[str, float]] = None,
                        etf_shares_metrics: Optional[Dict[str, float]] = None) -> float:
        """
        资金流评分 (增强版)
        
        核心逻辑：
        1. 成交量趋势：放量上涨 = 资金流入 (高分)
        2. 量价配合：价格上涨 + 成交量放大 = 健康 (高分)
        3. 成交金额趋势：金额增长 = 资金关注度提升
        4. 北向资金：外资流向 (新增)
        5. ETF 份额：基金份额变化 (新增)
        
        Args:
            prices: 价格序列
            volumes: 成交量序列
            amounts: 成交金额序列 (可选)
            northbound_metrics: 北向资金指标 (可选)
            etf_shares_metrics: ETF 份额指标 (可选)
            
        Returns:
            0-1 之间的分数
        """
        if len(prices) < 40 or len(volumes) < 40:
            return 0.5
        
        scores = []
        score_values = []
        weights = []
        
        # ===== 基础资金流指标 (权重 60%) =====
        
        # 1. 成交量趋势 (20 日 vs 前 20 日) - 权重 15%
        recent_vol = volumes.iloc[-20:].mean()
        prev_vol = volumes.iloc[-40:-20].mean()
        vol_change = (recent_vol - prev_vol) / prev_vol if prev_vol > 0 else 0
        vol_score = 0.5 + vol_change
        vol_score = max(0, min(1, vol_score))
        scores.append(('volume_trend', vol_score))
        score_values.append(vol_score)
        weights.append(0.15)
        
        # 2. 量价配合 - 权重 15%
        price_returns = prices.pct_change().dropna()
        vol_returns = volumes.pct_change().dropna()
        common_idx = price_returns.index.intersection(vol_returns.index)
        if len(common_idx) >= 20:
            corr = price_returns.loc[common_idx].corr(vol_returns.loc[common_idx])
            corr_score = 0.5 + corr * 0.5
            corr_score = max(0, min(1, corr_score))
        else:
            corr_score = 0.5
        scores.append(('price_volume_corr', corr_score))
        score_values.append(corr_score)
        weights.append(0.15)
        
        # 3. 成交金额趋势 - 权重 15%
        if amounts is not None and len(amounts) >= 40:
            recent_amt = amounts.iloc[-20:].mean()
            prev_amt = amounts.iloc[-40:-20].mean()
            amt_change = (recent_amt - prev_amt) / prev_amt if prev_amt > 0 else 0
            amt_score = 0.5 + amt_change
            amt_score = max(0, min(1, amt_score))
        else:
            amt_score = vol_score
        scores.append(('amount_trend', amt_score))
        score_values.append(amt_score)
        weights.append(0.15)
        
        # 4. 资金流入强度 - 权重 15%
        vol_median = volumes.iloc[-60:].median()
        high_vol_days = (volumes.iloc[-20:] > vol_median).sum()
        flow_intensity = high_vol_days / 20
        scores.append(('flow_intensity', flow_intensity))
        score_values.append(flow_intensity)
        weights.append(0.15)
        
        # ===== 北向资金指标 (权重 20%) =====
        if northbound_metrics is not None:
            # 北向资金评分
            nb_scores = []
            
            # 净买入趋势 (归一化：-50 亿 ~ +50 亿 -> 0~1)
            net_flow_20d = northbound_metrics.get('net_flow_20d_sum', 0)
            nb_net_score = 0.5 + net_flow_20d / 100  # 100 亿归一化因子
            nb_net_score = max(0, min(1, nb_net_score))
            nb_scores.append(nb_net_score)
            
            # 买入天数占比
            buy_ratio = northbound_metrics.get('buy_ratio', 0.5)
            nb_scores.append(buy_ratio)
            
            # 资金趋势
            nb_trend = northbound_metrics.get('trend', 0)
            nb_trend_score = 0.5 + nb_trend
            nb_trend_score = max(0, min(1, nb_trend_score))
            nb_scores.append(nb_trend_score)
            
            nb_score = sum(nb_scores) / len(nb_scores)
            scores.append(('northbound', nb_score))
            score_values.append(nb_score)
            weights.append(0.20)
            
            logger.debug(f"Northbound metrics: {northbound_metrics}, score: {nb_score:.3f}")
        else:
            # 无北向数据时，用基础指标平均代替
            base_avg = sum(score_values[:4]) / 4
            score_values.append(base_avg)
            weights.append(0.20)
            scores.append(('northbound_proxy', base_avg))
        
        # ===== ETF 份额指标 (权重 20%) =====
        if etf_shares_metrics is not None:
            etf_scores = []
            
            # 20 日份额变化 (归一化：-20% ~ +20% -> 0~1)
            shares_20d = etf_shares_metrics.get('shares_change_20d', 0)
            etf_20d_score = 0.5 + shares_20d / 0.4
            etf_20d_score = max(0, min(1, etf_20d_score))
            etf_scores.append(etf_20d_score)
            
            # 5 日份额变化 (短期)
            shares_5d = etf_shares_metrics.get('shares_change_5d', 0)
            etf_5d_score = 0.5 + shares_5d / 0.2
            etf_5d_score = max(0, min(1, etf_5d_score))
            etf_scores.append(etf_5d_score)
            
            # 流入天数占比
            inflow_ratio = etf_shares_metrics.get('inflow_days_ratio', 0.5)
            etf_scores.append(inflow_ratio)
            
            etf_score = sum(etf_scores) / len(etf_scores)
            scores.append(('etf_shares', etf_score))
            score_values.append(etf_score)
            weights.append(0.20)
            
            logger.debug(f"ETF shares metrics: {etf_shares_metrics}, score: {etf_score:.3f}")
        else:
            # 无 ETF 份额数据时，用基础指标平均代替
            base_avg = sum(score_values[:4]) / 4
            score_values.append(base_avg)
            weights.append(0.20)
            scores.append(('etf_shares_proxy', base_avg))
        
        # 加权平均
        flow_score = sum(s * w for s, w in zip(score_values, weights)) / sum(weights)
        
        logger.debug(f"Flow scores: {scores}, weights: {weights}, final: {flow_score:.3f}")
        
        return flow_score
    
    def score_index(self, 
                    etf_data: pd.DataFrame, 
                    benchmark_data: Optional[pd.DataFrame] = None,
                    northbound_metrics: Optional[Dict[str, float]] = None,
                    etf_shares_metrics: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """
        计算综合评分 (增强版)
        
        Args:
            etf_data: ETF 数据 (包含 close, volume, amount)
            benchmark_data: 基准数据 (可选，用于相对强弱)
            northbound_metrics: 北向资金指标 (可选)
            etf_shares_metrics: ETF 份额指标 (可选)
            
        Returns:
            包含各因子得分和总分
        """
        if etf_data.empty:
            return {'total_score': 0.0}
        
        close = etf_data['close']
        volume = etf_data.get('volume', pd.Series())
        amount = etf_data.get('amount', pd.Series())
        returns = close.pct_change().dropna()
        
        scores = {}
        
        # 动量 (20%)
        scores['momentum'] = self.calc_momentum_score(returns)
        
        # 波动 (15%)
        scores['volatility'] = self.calc_volatility_score(returns)
        
        # 趋势 (20%)
        scores['trend'] = self.calc_trend_score(close)
        
        # 估值 (25%) - 简化版
        scores['value'] = self.calc_value_score(close)
        
        # 资金流 (15%) - 增强版 (含北向资金 + ETF 份额)
        scores['flow'] = self.calc_flow_score(
            close, 
            volume, 
            amount if not amount.empty else None,
            northbound_metrics,
            etf_shares_metrics
        )
        
        # 相对强弱 (20%)
        if benchmark_data is not None and not benchmark_data.empty:
            scores['relative_strength'] = self.calc_relative_strength(
                close, 
                benchmark_data['close']
            )
        else:
            scores['relative_strength'] = 0.5
        
        # 确保所有值都是有效的数字（处理 NaN）
        for key in scores:
            if pd.isna(scores[key]) or scores[key] is None:
                scores[key] = 0.5
        
        # 加权总分 (使用配置中的权重)
        total = (
            scores.get('momentum', 0.5) * self.weights.get('momentum', 0.20) +
            scores.get('volatility', 0.5) * self.weights.get('volatility', 0.15) +
            scores.get('trend', 0.5) * self.weights.get('trend', 0.20) +
            scores.get('value', 0.5) * self.weights.get('value', 0.25) +
            scores.get('flow', 0.5) * self.weights.get('flow', 0.15) +
            scores.get('relative_strength', 0.5) * self.weights.get('relative_strength', 0.20)
        )
        
        # 重新归一化 (因为权重总和可能超过 1)
        weight_sum = (
            self.weights.get('momentum', 0.20) +
            self.weights.get('volatility', 0.15) +
            self.weights.get('trend', 0.20) +
            self.weights.get('value', 0.25) +
            self.weights.get('flow', 0.15) +
            self.weights.get('relative_strength', 0.20)
        )
        
        if weight_sum > 0:
            total = total / weight_sum
        
        scores['total_score'] = total
        
        logger.debug(f"Scores: {scores}")
        
        return scores
    
    def rank_indices(self, scores_dict: Dict[str, Dict[str, float]]) -> pd.DataFrame:
        """
        对所有指数排名
        
        Args:
            scores_dict: {index_code: scores}
            
        Returns:
            排名 DataFrame
        """
        rows = []
        for code, scores in scores_dict.items():
            row = {'code': code}
            row.update(scores)
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        if df.empty:
            return df
        
        df = df.sort_values('total_score', ascending=False)
        df['rank'] = range(1, len(df) + 1)
        
        return df


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    config = {
        'factor_weights': {
            'value': 0.25,
            'momentum': 0.20,
            'volatility': 0.15,
            'flow': 0.15,
            'fundamental': 0.15,
            'sentiment': 0.10
        }
    }
    
    engine = ScoringEngine(config)
    
    # 模拟数据
    dates = pd.date_range('2025-01-01', periods=100, freq='D')
    prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    
    df = pd.DataFrame({'close': prices}, index=dates)
    
    scores = engine.score_index(df)
    print(f"Scores: {scores}")
