#!/usr/bin/env python3
"""
测试扩展资金因子 - 北向资金 + ETF 份额
"""
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import pandas as pd
import numpy as np
from src.scoring_baostock import ScoringEngine
from src.data_fetcher_baostock import BaostockFetcher

def test_northbound_flow():
    """测试北向资金数据获取"""
    print("=" * 60)
    print("测试北向资金数据获取")
    print("=" * 60)
    
    fetcher = BaostockFetcher()
    
    # 获取北向资金数据
    df = fetcher.fetch_northbound_flow("20260101")
    
    if df.empty:
        print("❌ 北向资金数据获取失败 (可能网络问题或 API 限制)")
        return None
    
    print(f"✅ 获取成功：{len(df)} 行数据")
    print(f"\n最新数据:")
    print(df.tail(3))
    
    # 计算指标
    metrics = fetcher.calc_northbound_metrics(df)
    print(f"\n📊 北向资金指标:")
    print(f"   近 20 日净买入总和：{metrics['net_flow_20d_sum']:+.2f} 亿元")
    print(f"   近 5 日日均净买入：{metrics['net_flow_5d_avg']:+.2f} 亿元")
    print(f"   买入天数占比：{metrics['buy_ratio']:.1%}")
    print(f"   资金趋势：{metrics['trend']:+.2f}")
    
    return metrics


def test_etf_shares():
    """测试 ETF 份额数据获取"""
    print("\n" + "=" * 60)
    print("测试 ETF 份额数据获取")
    print("=" * 60)
    
    fetcher = BaostockFetcher()
    
    # 测试沪深 300ETF
    etf_code = "510300"
    df = fetcher.fetch_etf_shares(etf_code, "20260101")
    
    if df.empty:
        print(f"❌ ETF 份额数据获取失败 ({etf_code})")
        return None
    
    print(f"✅ 获取成功：{len(df)} 行数据")
    print(f"\n最新数据:")
    print(df[['shares', 'shares_change_1d', 'shares_change_5d', 'shares_change_20d']].tail(3))
    
    # 计算指标
    metrics = fetcher.calc_etf_shares_metrics(df)
    print(f"\n📊 ETF 份额指标:")
    print(f"   20 日份额变化：{metrics['shares_change_20d']:+.2%}")
    print(f"   5 日份额变化：{metrics['shares_change_5d']:+.2%}")
    print(f"   流入天数占比：{metrics['inflow_days_ratio']:.1%}")
    print(f"   份额趋势：{metrics['trend']:+.4f}")
    
    return metrics


def test_enhanced_flow_score():
    """测试增强版资金流评分"""
    print("\n" + "=" * 60)
    print("测试增强版资金流评分")
    print("=" * 60)
    
    # 创建模拟数据
    np.random.seed(42)
    n_days = 100
    dates = pd.date_range('2025-01-01', periods=n_days, freq='D')
    
    prices = pd.Series(100 + np.cumsum(np.random.randn(n_days) * 0.5 + 0.05), index=dates)
    volumes = pd.Series(np.random.randint(1000000, 5000000, n_days), index=dates)
    volumes.iloc[-20:] = volumes.iloc[-20:] * 1.5  # 近期放量
    amounts = prices * volumes
    
    # 模拟北向资金指标
    northbound_metrics = {
        'net_flow_20d_sum': 150.0,  # 净流入 150 亿
        'net_flow_5d_avg': 12.0,    # 日均 12 亿
        'buy_ratio': 0.70,          # 70% 天数买入
        'trend': 0.3                # 趋势向上
    }
    
    # 模拟 ETF 份额指标
    etf_shares_metrics = {
        'shares_change_20d': 0.08,   # 份额增长 8%
        'shares_change_5d': 0.02,    # 5 日增长 2%
        'inflow_days_ratio': 0.65,   # 65% 天数流入
        'trend': 0.05                # 趋势向上
    }
    
    config = {
        'factor_weights': {
            'value': 0.25,
            'momentum': 0.20,
            'volatility': 0.15,
            'trend': 0.20,
            'flow': 0.15,
            'relative_strength': 0.20
        }
    }
    
    scorer = ScoringEngine(config)
    
    # 测试 1: 基础评分 (无北向/ETF 数据)
    print("\n📊 测试 1: 基础资金流评分")
    flow_score_basic = scorer.calc_flow_score(prices, volumes, amounts)
    print(f"   得分：{flow_score_basic:.4f}")
    
    # 测试 2: 增强评分 (含北向资金)
    print("\n📊 测试 2: 增强评分 (含北向资金)")
    flow_score_nb = scorer.calc_flow_score(prices, volumes, amounts, northbound_metrics=northbound_metrics)
    print(f"   得分：{flow_score_nb:.4f}")
    print(f"   北向资金影响：{flow_score_nb - flow_score_basic:+.4f}")
    
    # 测试 3: 完整评分 (北向 + ETF 份额)
    print("\n📊 测试 3: 完整评分 (北向 + ETF 份额)")
    flow_score_full = scorer.calc_flow_score(
        prices, volumes, amounts,
        northbound_metrics=northbound_metrics,
        etf_shares_metrics=etf_shares_metrics
    )
    print(f"   得分：{flow_score_full:.4f}")
    print(f"   相对基础评分提升：{flow_score_full - flow_score_basic:+.4f}")
    
    # 子因子分解
    print("\n📈 子因子权重分布:")
    print("   基础指标 (成交量/量价/金额/强度): 60%")
    print("   北向资金指标：20%")
    print("   ETF 份额指标：20%")
    
    return flow_score_full


def test_full_scoring():
    """测试完整评分系统"""
    print("\n" + "=" * 60)
    print("测试完整评分系统")
    print("=" * 60)
    
    # 创建模拟 ETF 数据
    np.random.seed(42)
    n_days = 100
    dates = pd.date_range('2025-01-01', periods=n_days, freq='D')
    
    etf_data = pd.DataFrame({
        'close': 100 + np.cumsum(np.random.randn(n_days) * 0.5 + 0.05),
        'volume': np.random.randint(1000000, 5000000, n_days),
        'amount': np.random.randint(1e8, 5e8, n_days)
    }, index=dates)
    
    # 模拟指标
    northbound_metrics = {
        'net_flow_20d_sum': 100.0,
        'net_flow_5d_avg': 8.0,
        'buy_ratio': 0.60,
        'trend': 0.2
    }
    
    etf_shares_metrics = {
        'shares_change_20d': 0.05,
        'shares_change_5d': 0.01,
        'inflow_days_ratio': 0.55,
        'trend': 0.03
    }
    
    config = {
        'factor_weights': {
            'value': 0.25,
            'momentum': 0.20,
            'volatility': 0.15,
            'trend': 0.20,
            'flow': 0.15,
            'relative_strength': 0.20
        }
    }
    
    scorer = ScoringEngine(config)
    scores = scorer.score_index(
        etf_data,
        northbound_metrics=northbound_metrics,
        etf_shares_metrics=etf_shares_metrics
    )
    
    print("\n🏆 各因子得分:")
    factor_names = {
        'value': '估值',
        'momentum': '动量',
        'volatility': '波动',
        'trend': '趋势',
        'flow': '资金流',
        'relative_strength': '相对强弱'
    }
    
    for key, name in factor_names.items():
        score = scores.get(key, 0)
        bar = '█' * int(score * 10)
        print(f"   {name}: {score:.4f} {bar}")
    
    print(f"\n🎯 综合总分：{scores['total_score']:.4f}")
    
    # 评级
    total = scores['total_score']
    if total > 0.7:
        rating = "⭐⭐⭐⭐⭐ 强烈推荐"
    elif total > 0.6:
        rating = "⭐⭐⭐⭐ 推荐"
    elif total > 0.5:
        rating = "⭐⭐⭐ 中性"
    elif total > 0.4:
        rating = "⭐⭐ 谨慎"
    else:
        rating = "⭐ 回避"
    
    print(f"📋 评级：{rating}")
    
    return scores


if __name__ == "__main__":
    print("🚀 扩展资金因子测试\n")
    
    # 测试数据获取
    nb_metrics = test_northbound_flow()
    etf_metrics = test_etf_shares()
    
    # 测试评分
    test_enhanced_flow_score()
    test_full_scoring()
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成!")
    print("=" * 60)
