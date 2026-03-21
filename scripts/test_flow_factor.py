#!/usr/bin/env python3
"""
测试资金流因子计算
"""
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import numpy as np
import pandas as pd
from src.scoring_baostock import ScoringEngine

def test_flow_factor():
    """测试资金流因子"""
    print("=" * 60)
    print("测试资金流因子 (Flow Factor)")
    print("=" * 60)
    
    # 创建模拟数据
    np.random.seed(42)
    n_days = 100
    
    dates = pd.date_range('2025-01-01', periods=n_days, freq='D')
    
    # 模拟价格 (上涨趋势)
    prices = 100 + np.cumsum(np.random.randn(n_days) * 0.5 + 0.05)
    
    # 模拟成交量 (近期放量)
    volumes = np.random.randint(1000000, 5000000, n_days)
    # 后 20 天成交量放大
    volumes[-20:] = volumes[-20:] * 1.5
    
    # 模拟成交金额
    amounts = prices * volumes
    
    # 转为 Series
    prices_s = pd.Series(prices, index=dates)
    volumes_s = pd.Series(volumes, index=dates)
    amounts_s = pd.Series(amounts, index=dates)
    
    # 创建 DataFrame
    df = pd.DataFrame({
        'close': prices_s,
        'volume': volumes_s,
        'amount': amounts_s
    }, index=dates)
    
    print(f"\n📊 模拟数据：{n_days} 天")
    print(f"   价格范围：{prices_s.min():.2f} - {prices_s.max():.2f}")
    print(f"   成交量范围：{volumes_s.min():,.0f} - {volumes_s.max():,.0f}")
    
    # 配置
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
    
    # 测试资金流评分
    flow_score = scorer.calc_flow_score(prices_s, volumes_s, amounts_s)
    print(f"\n💰 资金流得分：{flow_score:.4f}")
    
    # 分解各子因子
    print("\n📈 子因子分解:")
    
    # 1. 成交量趋势
    recent_vol = volumes_s.iloc[-20:].mean()
    prev_vol = volumes_s.iloc[-40:-20].mean()
    vol_change = (recent_vol - prev_vol) / prev_vol if prev_vol > 0 else 0
    vol_score = 0.5 + vol_change
    vol_score = max(0, min(1, vol_score))
    print(f"   成交量趋势：{vol_change:+.2%} → 得分 {vol_score:.3f}")
    
    # 2. 量价配合
    price_returns = prices_s.pct_change().dropna()
    vol_returns = volumes_s.pct_change().dropna()
    common_idx = price_returns.index.intersection(vol_returns.index)
    if len(common_idx) >= 20:
        corr = price_returns.loc[common_idx].corr(vol_returns.loc[common_idx])
        corr_score = 0.5 + corr * 0.5
        corr_score = max(0, min(1, corr_score))
        print(f"   量价相关性：{corr:.3f} → 得分 {corr_score:.3f}")
    
    # 3. 成交金额趋势
    recent_amt = amounts_s.iloc[-20:].mean()
    prev_amt = amounts_s.iloc[-40:-20].mean()
    amt_change = (recent_amt - prev_amt) / prev_amt if prev_amt > 0 else 0
    amt_score = 0.5 + amt_change
    amt_score = max(0, min(1, amt_score))
    print(f"   成交金额趋势：{amt_change:+.2%} → 得分 {amt_score:.3f}")
    
    # 4. 资金流入强度
    vol_median = volumes_s.iloc[-60:].median()
    high_vol_days = (volumes_s.iloc[-20:] > vol_median).sum()
    flow_intensity = high_vol_days / 20
    print(f"   资金流入强度：{high_vol_days}/20 天放量 → 得分 {flow_intensity:.3f}")
    
    # 计算最终得分
    final_score = (
        vol_score * 0.30 +
        corr_score * 0.30 +
        amt_score * 0.25 +
        flow_intensity * 0.15
    )
    print(f"\n🎯 最终资金流得分：{final_score:.4f}")
    
    # 评分解读
    print("\n📋 评分解读:")
    if final_score > 0.7:
        print("   ✅ 资金大幅流入，强烈看好")
    elif final_score > 0.5:
        print("   ✅ 资金温和流入")
    elif final_score > 0.3:
        print("   ⚠️ 资金流出或观望")
    else:
        print("   ❌ 资金大幅流出，警惕")
    
    # 测试完整评分
    print("\n" + "=" * 60)
    print("测试完整评分系统")
    print("=" * 60)
    
    scores = scorer.score_index(df)
    print(f"\n各因子得分:")
    for key, value in scores.items():
        if key != 'total_score':
            print(f"   {key}: {value:.4f}")
    print(f"\n🏆 综合总分：{scores['total_score']:.4f}")
    
    print("\n✅ 测试完成!")


if __name__ == "__main__":
    test_flow_factor()
