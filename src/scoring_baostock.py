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
        factor_model = config.get('factor_model', {})
        # 从配置加载 active_factors，如果未配置则使用默认值
        if 'active_factors' in factor_model:
            self.active_factors = factor_model['active_factors']
        else:
            # 默认活跃因子：momentum, trend, flow
            self.active_factors = ['momentum', 'trend', 'flow']

        self.auxiliary_factors = factor_model.get('auxiliary_factors', [])
    
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
        
        计算逻辑：
        1. 优先使用 60 日相对收益，数据不足时降级到更短周期
        2. 使用更宽的归一化范围（±50% 才到极值）
        3. 数据严重不足时返回 0.5（中性）
        """
        # 数据严重不足时返回中性分数（至少需要 10 天）
        if benchmark_prices is None or len(benchmark_prices) < 10:
            logger.warning("Benchmark data severely insufficient, returning neutral score 0.5")
            return 0.5
        
        if len(prices) < 10:
            logger.warning(f"Price data severely insufficient ({len(prices)} rows), returning neutral score 0.5")
            return 0.5
        
        # 对齐
        common_idx = prices.index.intersection(benchmark_prices.index)
        if len(common_idx) < 10:
            logger.warning(f"Common index severely insufficient ({len(common_idx)} rows), returning neutral score 0.5")
            return 0.5
        
        prices_aligned = prices.loc[common_idx]
        bench_aligned = benchmark_prices.loc[common_idx]
        
        # 根据可用数据长度选择计算周期
        available_days = len(common_idx)
        if available_days >= 60:
            lookback = 60
            period_label = "60 日"
        elif available_days >= 20:
            lookback = 20
            period_label = "20 日"
        else:
            lookback = min(10, available_days - 1)
            period_label = f"{lookback}日"
        
        # 计算相对收益
        idx_return = prices_aligned.iloc[-1] / prices_aligned.iloc[-lookback] - 1
        bench_return = bench_aligned.iloc[-1] / bench_aligned.iloc[-lookback] - 1
        excess_return = idx_return - bench_return  # 超额收益
        
        # 归一化：±50% 超额收益对应 0~1 分
        # 超额 +50% → 1.0 分，超额 0% → 0.5 分，超额 -50% → 0.0 分
        score = 0.5 + excess_return / 1.0  # 除以 1.0 即 100% 的范围
        score = max(0, min(1, score))
        
        logger.debug(f"RS ({period_label}): idx_return={idx_return*100:.2f}%, bench_return={bench_return*100:.2f}%, excess={excess_return*100:.2f}%, score={score:.3f}")
        
        return score
    
    def calc_value_score(self, prices: pd.Series) -> float:
        """
        估值评分 (使用价格分位作为代理)

        逻辑：价格分位越低 (越接近区间低点) 得分越高
        - 分位 0% (最低点) → 得分 1.0
        - 分位 100% (最高点) → 得分 0.0

        注：优先使用 252 天 (1 年) 历史，不足时使用全部可用数据
        """
        lookback = min(252, len(prices))
        recent_prices = prices.iloc[-lookback:]
        current = prices.iloc[-1]

        # 计算价格在历史中的分位
        percentile = (recent_prices < current).mean()

        # 分位越低 (价格越低) 得分越高
        score = 1.0 - percentile
        return max(0, min(1, score))
    
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
            price_slice = price_returns.loc[common_idx].replace([np.inf, -np.inf], np.nan).dropna()
            vol_slice = vol_returns.loc[common_idx].replace([np.inf, -np.inf], np.nan).dropna()
            common_valid_idx = price_slice.index.intersection(vol_slice.index)

            if len(common_valid_idx) >= 20:
                price_valid = price_slice.loc[common_valid_idx]
                vol_valid = vol_slice.loc[common_valid_idx]
                if price_valid.std() > 1e-12 and vol_valid.std() > 1e-12:
                    corr = price_valid.corr(vol_valid)
                else:
                    corr = 0
            else:
                corr = 0

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
                    etf_shares_metrics: Optional[Dict[str, float]] = None,
                    dynamic_weights: Optional[Dict[str, float]] = None,
                    pe_data: Optional[pd.DataFrame] = None) -> Dict[str, float]:
        """
        计算综合评分 (增强版)

        Args:
            etf_data: ETF 数据 (包含 close, volume, amount)
            benchmark_data: 基准数据 (可选，用于相对强弱)
            northbound_metrics: 北向资金指标 (可选)
            etf_shares_metrics: ETF 份额指标 (可选)
            dynamic_weights: 动态权重 (可选，覆盖默认权重)
            pe_data: PE 历史数据 (可选，用于真实估值评分)

        Returns:
            包含各因子得分、归因数据和总分
        """
        if etf_data.empty:
            return {'total_score': 0.0}

        close = etf_data['close']
        volume = etf_data.get('volume', pd.Series())
        amount = etf_data.get('amount', pd.Series())
        returns = close.pct_change().dropna()

        scores = {}
        attribution = {}  # 归因数据

        # 使用动态权重（如果提供）
        weights_to_use = dynamic_weights if dynamic_weights else self.weights

        # ===== 动量 (20%) =====
        if len(returns) >= 126:
            momentum_6m = returns.iloc[-126:].sum()
            momentum_1m = returns.iloc[-21:].sum() if len(returns) >= 21 else 0
            scores['momentum'] = self.calc_momentum_score(returns)
            attribution['momentum_6m_return'] = round(momentum_6m * 100, 2)  # 百分比
            attribution['momentum_1m_return'] = round(momentum_1m * 100, 2)
        else:
            scores['momentum'] = 0.5
            attribution['momentum_6m_return'] = 0
            attribution['momentum_1m_return'] = 0

        # ===== 波动 (15%) =====
        if len(returns) >= 20:
            volatility = returns.std() * np.sqrt(252)
            scores['volatility'] = self.calc_volatility_score(returns)
            attribution['volatility_annual'] = round(volatility * 100, 2)  # 百分比
        else:
            scores['volatility'] = 0.5
            attribution['volatility_annual'] = 0

        # ===== 趋势 (20%) =====
        if len(close) >= 60:
            ma20 = close.rolling(20).mean().iloc[-1]
            ma60 = close.rolling(60).mean().iloc[-1]
            current = close.iloc[-1]
            scores['trend'] = self.calc_trend_score(close)
            attribution['price_vs_ma20'] = round((current - ma20) / ma20 * 100, 2)  # 相对 MA20 位置%
            attribution['price_vs_ma60'] = round((current - ma60) / ma60 * 100, 2)  # 相对 MA60 位置%
            attribution['ma20_above_ma60'] = ma20 > ma60  # 金叉状态
        else:
            scores['trend'] = 0.5
            attribution['price_vs_ma20'] = 0
            attribution['price_vs_ma60'] = 0
            attribution['ma20_above_ma60'] = False

        # ===== 估值 (使用真实 PE 数据) =====
        value_score = self.calc_value_score(close)
        scores['value'] = value_score
        if pe_data is not None and not pe_data.empty and 'pe' in pe_data.columns:
            current_pe = pe_data['pe'].iloc[-1] if len(pe_data) > 0 else None
            if current_pe and 0 < current_pe < 100:
                # 计算 PE 分位
                lookback = min(2520, len(pe_data))
                historical_pe = pe_data['pe'].iloc[-lookback:].dropna()
                valid_pe = historical_pe[(historical_pe > 0) & (historical_pe < 100)]
                if len(valid_pe) >= 60:
                    pe_percentile = (valid_pe < current_pe).mean()
                    attribution['value_percentile'] = round(pe_percentile * 100, 2)
                    attribution['value_assessment'] = '低估' if pe_percentile < 0.3 else ('高估' if pe_percentile > 0.7 else '合理')
                    attribution['current_pe'] = round(current_pe, 2)
                else:
                    attribution['value_percentile'] = 50
                    attribution['value_assessment'] = '数据不足'
                    attribution['current_pe'] = round(current_pe, 2)
            else:
                attribution['value_percentile'] = 50
                attribution['value_assessment'] = 'PE 异常'
                attribution['current_pe'] = current_pe if current_pe else None
        else:
            # 降级为价格分位
            lookback = min(252, len(close))
            recent_prices = close.iloc[-lookback:]
            current = close.iloc[-1]
            percentile = (recent_prices < current).mean()
            attribution['value_percentile'] = round(percentile * 100, 2)
            attribution['value_assessment'] = '低估' if percentile < 0.3 else ('高估' if percentile > 0.7 else '合理')
            attribution['current_pe'] = None
        
        # ===== 资金流 (15%) =====
        scores['flow'] = self.calc_flow_score(
            close, volume, 
            amount if not amount.empty else None,
            northbound_metrics, etf_shares_metrics
        )
        # 资金流归因
        if northbound_metrics:
            attribution['northbound_20d_sum'] = round(northbound_metrics.get('net_flow_20d_sum', 0), 2)
            attribution['northbound_trend'] = '流入' if northbound_metrics.get('trend', 0) > 0 else '流出'
        else:
            attribution['northbound_20d_sum'] = 0
            attribution['northbound_trend'] = '未知'
        
        if etf_shares_metrics:
            attribution['etf_shares_20d_change'] = round(etf_shares_metrics.get('shares_change_20d', 0) * 100, 2)
            attribution['etf_shares_trend'] = '申购' if etf_shares_metrics.get('shares_change_20d', 0) > 0 else '赎回'
        else:
            attribution['etf_shares_20d_change'] = 0
            attribution['etf_shares_trend'] = '未知'
        
        # ===== 相对强弱 (20%) =====
        if benchmark_data is not None and not benchmark_data.empty:
            scores['relative_strength'] = self.calc_relative_strength(close, benchmark_data['close'])
            # 计算相对收益（用于归因展示，使用动态周期）
            common_idx = close.index.intersection(benchmark_data['close'].index)
            available_days = len(common_idx)
            
            if available_days >= 10:
                # 根据可用数据选择周期
                if available_days >= 60:
                    lookback = 60
                elif available_days >= 20:
                    lookback = 20
                else:
                    lookback = min(10, available_days - 1)
                
                idx_return = (close.iloc[-1] / close.iloc[-lookback] - 1) * 100
                bench_return = (benchmark_data['close'].iloc[-1] / benchmark_data['close'].iloc[-lookback] - 1) * 100
                excess_return = idx_return - bench_return
                
                attribution['relative_return'] = round(excess_return, 2)  # 超额收益%
                attribution['index_return'] = round(idx_return, 2)  # 指数自身收益%
                attribution['benchmark_return'] = round(bench_return, 2)  # 基准收益%
                attribution['rs_lookback_days'] = lookback  # 计算周期
            else:
                attribution['relative_return'] = 0
                attribution['index_return'] = 0
                attribution['benchmark_return'] = 0
                attribution['rs_lookback_days'] = 0
        else:
            scores['relative_strength'] = 0.5
            attribution['relative_return'] = 0
            attribution['index_return'] = 0
            attribution['benchmark_return'] = 0
            attribution['rs_lookback_days'] = 0
        
        # 确保所有值都是有效的数字（处理 NaN）
        for key in scores:
            if pd.isna(scores[key]) or scores[key] is None:
                scores[key] = 0.5
        
        # 基线总分只使用主模型中的活跃因子，辅助因子与实验因子仅展示不入主分。
        total = 0.0
        weight_sum = 0.0
        for factor in self.active_factors:
            weight = weights_to_use.get(factor, self.weights.get(factor, 0.0))
            total += scores.get(factor, 0.5) * weight
            weight_sum += weight
        
        if weight_sum > 0:
            total = total / weight_sum
        else:
            total = 0.5
        
        scores['total_score'] = total
        scores['active_factors'] = list(self.active_factors)
        scores['attribution'] = attribution  # 添加归因数据
        
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
