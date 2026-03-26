"""
增强评分系统 - 添加基本面和情绪因子
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class EnhancedScoringEngine:
    """
    增强评分引擎
    
    因子体系:
    - 动量 (20%): 6 个月收益率
    - 波动 (15%): 年化波动率 (低波高分)
    - 趋势 (20%): 价格相对 MA20/MA60 位置
    - 估值 (20%): 价格历史分位 (简化 PE)
    - 资金流 (15%): 成交量/北向资金/ETF 份额
    - 基本面 (10%): ROE/盈利增长 (新增)
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.weights = config.get('factor_weights', {})
    
    def calc_momentum_score(self, returns: pd.Series) -> tuple:
        """
        动量评分 (6 个月收益率)
        
        Returns:
            (score, metrics_dict)
        """
        metrics = {}
        
        if len(returns) < 126:
            # 数据不足时用短期动量
            lookback = min(len(returns), 60)
            momentum = returns.iloc[-lookback:].sum() if lookback > 0 else 0
            metrics['momentum_6m'] = 0
            metrics['momentum_1m'] = returns.iloc[-21:].sum() * 100 if len(returns) >= 21 else 0
        else:
            momentum_6m = returns.iloc[-126:].sum()
            momentum_1m = returns.iloc[-21:].sum()
            metrics['momentum_6m'] = momentum_6m * 100
            metrics['momentum_1m'] = momentum_1m * 100
            momentum = momentum_6m
        
        # 归一化 (-0.5 ~ 0.5 -> 0 ~ 1)
        score = 0.5 + momentum
        score = max(0, min(1, score))
        
        return score, metrics
    
    def calc_volatility_score(self, returns: pd.Series) -> tuple:
        """
        波动率评分 (低波动高分)
        
        Returns:
            (score, metrics_dict)
        """
        metrics = {}
        
        if len(returns) < 20:
            return 0.5, {'volatility_annual': 0}
        
        volatility = returns.std() * np.sqrt(252)
        metrics['volatility_annual'] = volatility * 100
        
        # 波动率越低分越高 (假设合理波动率 0.1-0.4)
        score = 1.0 - (volatility - 0.1) / 0.3
        score = max(0, min(1, score))
        
        return score, metrics
    
    def calc_trend_score(self, prices: pd.Series) -> tuple:
        """
        趋势评分 (价格在 MA 上方)
        
        Returns:
            (score, metrics_dict)
        """
        metrics = {}
        
        if len(prices) < 60:
            return 0.5, {'price_vs_ma20': 0, 'price_vs_ma60': 0, 'ma20_above_ma60': False}
        
        ma20 = prices.rolling(20).mean().iloc[-1]
        ma60 = prices.rolling(60).mean().iloc[-1]
        current = prices.iloc[-1]
        
        metrics['price_vs_ma20'] = ((current - ma20) / ma20) * 100
        metrics['price_vs_ma60'] = ((current - ma60) / ma60) * 100
        metrics['ma20_above_ma60'] = ma20 > ma60
        
        # 价格在 MA20 和 MA60 上方得高分
        score = 0.5
        if current > ma20:
            score += 0.25
        if current > ma60:
            score += 0.25
        
        return min(1, score), metrics
    
    def calc_value_score(self, prices: pd.Series) -> tuple:
        """
        估值评分 (价格分位代替 PE)
        
        Returns:
            (score, metrics_dict)
        """
        metrics = {}
        
        if len(prices) < 252:
            lookback = len(prices)
        else:
            lookback = 252
        
        recent_prices = prices.iloc[-lookback:]
        current = prices.iloc[-1]
        
        percentile = (recent_prices < current).mean()
        metrics['value_percentile'] = percentile * 100
        metrics['value_assessment'] = '低估' if percentile < 0.3 else ('高估' if percentile > 0.7 else '合理')
        
        # 分位越低 (价格越低) 得分越高
        score = 1.0 - percentile
        
        return score, metrics
    
    def calc_flow_score(self, 
                        prices: pd.Series, 
                        volumes: pd.Series,
                        amounts: Optional[pd.Series] = None,
                        northbound_metrics: Optional[Dict[str, float]] = None,
                        etf_shares_metrics: Optional[Dict[str, float]] = None) -> tuple:
        """
        资金流评分 (增强版)
        
        Returns:
            (score, metrics_dict)
        """
        metrics = {}
        
        if len(prices) < 40 or len(volumes) < 40:
            return 0.5, {}
        
        scores = []
        weights = []
        
        # 1. 成交量趋势 (20%)
        recent_vol = volumes.iloc[-20:].mean()
        prev_vol = volumes.iloc[-40:-20].mean()
        vol_change = (recent_vol - prev_vol) / prev_vol if prev_vol > 0 else 0
        vol_score = 0.5 + vol_change
        vol_score = max(0, min(1, vol_score))
        scores.append(vol_score)
        weights.append(0.20)
        metrics['volume_change_pct'] = vol_change * 100
        
        # 2. 量价配合 (20%)
        price_returns = prices.pct_change().dropna()
        vol_returns = volumes.pct_change().dropna()
        common_idx = price_returns.index.intersection(vol_returns.index)
        if len(common_idx) >= 20:
            corr = price_returns.loc[common_idx].corr(vol_returns.loc[common_idx])
            corr_score = 0.5 + corr * 0.5
            corr_score = max(0, min(1, corr_score))
        else:
            corr_score = 0.5
        scores.append(corr_score)
        weights.append(0.20)
        metrics['price_volume_corr'] = corr if len(common_idx) >= 20 else 0
        
        # 3. 成交金额趋势 (20%)
        if amounts is not None and len(amounts) >= 40:
            recent_amt = amounts.iloc[-20:].mean()
            prev_amt = amounts.iloc[-40:-20].mean()
            amt_change = (recent_amt - prev_amt) / prev_amt if prev_amt > 0 else 0
            amt_score = 0.5 + amt_change
            amt_score = max(0, min(1, amt_score))
        else:
            amt_change = vol_change
            amt_score = vol_score
        scores.append(amt_score)
        weights.append(0.20)
        metrics['amount_change_pct'] = amt_change * 100
        
        # 4. 资金流入强度 (20%)
        vol_median = volumes.iloc[-60:].median()
        high_vol_days = (volumes.iloc[-20:] > vol_median).sum()
        flow_intensity = high_vol_days / 20
        scores.append(flow_intensity)
        weights.append(0.20)
        metrics['high_vol_days_ratio'] = flow_intensity
        
        # 5. 北向资金 (20%, 如果有数据)
        if northbound_metrics is not None:
            nb_scores = []
            
            net_flow_20d = northbound_metrics.get('net_flow_20d_sum', 0)
            nb_net_score = 0.5 + net_flow_20d / 100
            nb_net_score = max(0, min(1, nb_net_score))
            nb_scores.append(nb_net_score)
            
            buy_ratio = northbound_metrics.get('buy_ratio', 0.5)
            nb_scores.append(buy_ratio)
            
            nb_trend = northbound_metrics.get('trend', 0)
            nb_trend_score = 0.5 + nb_trend
            nb_trend_score = max(0, min(1, nb_trend_score))
            nb_scores.append(nb_trend_score)
            
            nb_score = sum(nb_scores) / len(nb_scores)
            scores.append(nb_score)
            weights.append(0.20)
            
            metrics['northbound_20d_sum'] = net_flow_20d
            metrics['northbound_buy_ratio'] = buy_ratio
        else:
            # 无北向数据时，用前 4 项平均代替
            base_avg = sum(scores[:4]) / 4
            scores.append(base_avg)
            weights.append(0.20)
        
        flow_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        
        return flow_score, metrics
    
    def calc_fundamental_score(self, 
                               etf_code: str,
                               index_code: Optional[str] = None,
                               fundamental_fetcher: Optional[object] = None) -> tuple:
        """
        基本面评分 (基于指数 PE/PB/ROE)
        
        评分逻辑:
        1. PE 历史分位 (40%) - 分位越低分越高
        2. PB 历史分位 (30%) - 分位越低分越高
        3. ROE (20%) - ROE 越高分越高
        4. 盈利增长 (10%) - 增长越高分越高
        
        Returns:
            (score, metrics_dict)
        """
        metrics = {}
        
        # 如果没有提供基本面获取器，返回中性分数
        if fundamental_fetcher is None:
            # 尝试用估值分数近似
            metrics['fundamental_note'] = '使用估值分数近似'
            metrics['roe_median'] = None
            metrics['pe_percentile'] = None
            return 0.5, metrics
        
        try:
            # 获取基本面评分
            score, details = fundamental_fetcher.get_fundamental_score(index_code or etf_code)
            
            # 合并指标
            metrics.update(details)
            metrics['fundamental_score'] = score
            
            return score, metrics
            
        except Exception as e:
            logger.error(f"Fundamental score calculation failed: {e}")
            metrics['fundamental_error'] = str(e)
            return 0.5, metrics
    
    def calc_sentiment_score(self, 
                             prices: pd.Series,
                             volumes: pd.Series,
                             etf_shares_metrics: Optional[Dict[str, float]] = None) -> tuple:
        """
        情绪评分 (基于市场情绪指标)
        
        指标:
        1. ETF 份额变化 (资金流入 = 情绪好)
        2. 成交量异常 (放量 = 情绪高涨)
        3. 价格动量加速 (动量增强 = 情绪乐观)
        
        Returns:
            (score, metrics_dict)
        """
        metrics = {}
        
        scores = []
        weights = []
        
        # 1. ETF 份额变化 (40%)
        if etf_shares_metrics is not None:
            shares_change = etf_shares_metrics.get('shares_change_20d', 0)
            shares_score = 0.5 + shares_change / 0.4  # ±20% -> 0~1
            shares_score = max(0, min(1, shares_score))
            scores.append(shares_score)
            weights.append(0.40)
            metrics['etf_shares_change_20d'] = shares_change * 100
        else:
            scores.append(0.5)
            weights.append(0.40)
        
        # 2. 成交量异常 (30%)
        if len(volumes) >= 60:
            vol_zscore = (volumes.iloc[-1] - volumes.iloc[-60:].mean()) / volumes.iloc[-60:].std()
            vol_zscore = max(-3, min(3, vol_zscore))  # 限制在±3
            vol_score = 0.5 + vol_zscore / 6  # ±3σ -> 0~1
            scores.append(vol_score)
            weights.append(0.30)
            metrics['volume_zscore'] = vol_zscore
        else:
            scores.append(0.5)
            weights.append(0.30)
        
        # 3. 动量加速 (30%)
        if len(prices) >= 42:
            mom_20d = prices.iloc[-1] / prices.iloc[-21] - 1
            mom_40d = prices.iloc[-21] / prices.iloc[-42] - 1
            mom_acceleration = mom_20d - mom_40d
            mom_score = 0.5 + mom_acceleration / 0.2  # ±20% -> 0~1
            mom_score = max(0, min(1, mom_score))
            scores.append(mom_score)
            weights.append(0.30)
            metrics['momentum_acceleration'] = mom_acceleration * 100
        else:
            scores.append(0.5)
            weights.append(0.30)
        
        sentiment_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        
        return sentiment_score, metrics
    
    def calc_relative_strength(self, prices: pd.Series, benchmark_prices: pd.Series) -> tuple:
        """
        相对强弱评分
        
        Returns:
            (score, metrics_dict)
        """
        metrics = {}
        
        if benchmark_prices is None or len(benchmark_prices) < 10:
            metrics['rs_note'] = '基准数据不足'
            return 0.5, metrics
        
        if len(prices) < 10:
            metrics['rs_note'] = '价格数据不足'
            return 0.5, metrics
        
        # 对齐
        common_idx = prices.index.intersection(benchmark_prices.index)
        if len(common_idx) < 10:
            metrics['rs_note'] = f'共同数据不足 ({len(common_idx)} rows)'
            return 0.5, metrics
        
        prices_aligned = prices.loc[common_idx]
        bench_aligned = benchmark_prices.loc[common_idx]
        
        # 根据可用数据选择周期
        available_days = len(common_idx)
        if available_days >= 60:
            lookback = 60
        elif available_days >= 20:
            lookback = 20
        else:
            lookback = min(10, available_days - 1)
        
        metrics['rs_lookback_days'] = lookback
        
        # 计算相对收益
        idx_return = prices_aligned.iloc[-1] / prices_aligned.iloc[-lookback] - 1
        bench_return = bench_aligned.iloc[-1] / bench_aligned.iloc[-lookback] - 1
        excess_return = idx_return - bench_return
        
        metrics['index_return'] = idx_return * 100
        metrics['benchmark_return'] = bench_return * 100
        metrics['excess_return'] = excess_return * 100
        
        # 归一化：±50% 超额收益对应 0~1 分
        score = 0.5 + excess_return / 1.0
        score = max(0, min(1, score))
        
        return score, metrics
    
    def score_index(self, 
                    etf_data: pd.DataFrame, 
                    benchmark_data: Optional[pd.DataFrame] = None,
                    northbound_metrics: Optional[Dict[str, float]] = None,
                    etf_shares_metrics: Optional[Dict[str, float]] = None,
                    dynamic_weights: Optional[Dict[str, float]] = None,
                    fundamental_fetcher: Optional[object] = None,
                    index_code: Optional[str] = None) -> Dict[str, float]:
        """
        计算综合评分 (增强版)
        
        Args:
            fundamental_fetcher: 基本面数据获取器 (可选)
            index_code: 指数代码 (用于获取基本面数据)
        
        Returns:
            包含各因子得分、归因数据和总分
        """
        if etf_data.empty:
            return {'total_score': 0.0, 'attribution': {}}
        
        close = etf_data['close']
        volume = etf_data.get('volume', pd.Series())
        amount = etf_data.get('amount', pd.Series())
        returns = close.pct_change().dropna()
        
        scores = {}
        attribution = {}
        
        # 使用动态权重（如果提供）
        weights_to_use = dynamic_weights if dynamic_weights else self.weights
        
        # ===== 动量 (20%) =====
        scores['momentum'], mom_metrics = self.calc_momentum_score(returns)
        attribution.update(mom_metrics)
        
        # ===== 波动 (15%) =====
        scores['volatility'], vol_metrics = self.calc_volatility_score(returns)
        attribution.update(vol_metrics)
        
        # ===== 趋势 (20%) =====
        scores['trend'], trend_metrics = self.calc_trend_score(close)
        attribution.update(trend_metrics)
        
        # ===== 估值 (20%) =====
        scores['value'], value_metrics = self.calc_value_score(close)
        attribution.update(value_metrics)
        
        # ===== 资金流 (15%) =====
        scores['flow'], flow_metrics = self.calc_flow_score(
            close, volume, 
            amount if not amount.empty else None,
            northbound_metrics, etf_shares_metrics
        )
        attribution.update(flow_metrics)
        
        # ===== 相对强弱 (20%) =====
        scores['relative_strength'], rs_metrics = self.calc_relative_strength(
            close, 
            benchmark_data['close'] if benchmark_data is not None and not benchmark_data.empty else None
        )
        attribution.update(rs_metrics)
        
        # ===== 基本面 (10%, 新增) =====
        scores['fundamental'], fund_metrics = self.calc_fundamental_score(
            etf_data.name if hasattr(etf_data, 'name') else 'unknown',
            index_code=index_code,
            fundamental_fetcher=fundamental_fetcher
        )
        attribution.update(fund_metrics)
        
        # ===== 情绪 (10%, 新增) =====
        scores['sentiment'], sent_metrics = self.calc_sentiment_score(
            close, volume, etf_shares_metrics
        )
        attribution.update(sent_metrics)
        
        # 确保所有值都是有效的数字
        for key in scores:
            if pd.isna(scores[key]) or scores[key] is None:
                scores[key] = 0.5
        
        # 加权总分
        total = (
            scores.get('momentum', 0.5) * weights_to_use.get('momentum', 0.20) +
            scores.get('volatility', 0.5) * weights_to_use.get('volatility', 0.15) +
            scores.get('trend', 0.5) * weights_to_use.get('trend', 0.20) +
            scores.get('value', 0.5) * weights_to_use.get('value', 0.20) +
            scores.get('flow', 0.5) * weights_to_use.get('flow', 0.15) +
            scores.get('relative_strength', 0.5) * weights_to_use.get('relative_strength', 0.20) +
            scores.get('fundamental', 0.5) * weights_to_use.get('fundamental', 0.10) +
            scores.get('sentiment', 0.5) * weights_to_use.get('sentiment', 0.10)
        )
        
        weight_sum = sum([
            weights_to_use.get('momentum', 0.20),
            weights_to_use.get('volatility', 0.15),
            weights_to_use.get('trend', 0.20),
            weights_to_use.get('value', 0.20),
            weights_to_use.get('flow', 0.15),
            weights_to_use.get('relative_strength', 0.20),
            weights_to_use.get('fundamental', 0.10),
            weights_to_use.get('sentiment', 0.10)
        ])
        
        if weight_sum > 0:
            total = total / weight_sum
        
        scores['total_score'] = total
        scores['attribution'] = attribution
        
        # 添加因子排名
        factor_scores = {k: v for k, v in scores.items() if k not in ['total_score', 'attribution']}
        sorted_factors = sorted(factor_scores.items(), key=lambda x: x[1], reverse=True)
        attribution['best_factor'] = sorted_factors[0][0] if sorted_factors else 'unknown'
        attribution['worst_factor'] = sorted_factors[-1][0] if sorted_factors else 'unknown'
        
        return scores
    
    def rank_indices(self, scores_dict: Dict[str, Dict[str, float]]) -> pd.DataFrame:
        """对所有指数排名"""
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
    logging.basicConfig(level=logging.INFO)
    
    config = {
        'factor_weights': {
            'momentum': 0.20,
            'volatility': 0.15,
            'trend': 0.20,
            'value': 0.20,
            'flow': 0.15,
            'relative_strength': 0.20,
            'fundamental': 0.10,
            'sentiment': 0.10
        }
    }
    
    engine = EnhancedScoringEngine(config)
    
    # 模拟数据测试
    dates = pd.date_range('2025-01-01', periods=100, freq='D')
    prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    volumes = np.random.randn(100) * 1000000 + 5000000
    
    df = pd.DataFrame({'close': prices, 'volume': volumes}, index=dates)
    
    scores = engine.score_index(df)
    print(f"Total Score: {scores['total_score']:.3f}")
    print(f"Attribution: {scores['attribution']}")
