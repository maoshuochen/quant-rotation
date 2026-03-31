#!/usr/bin/env python3
"""
因子分析运行脚本
"""
import sys
import logging
from pathlib import Path

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.factor_analysis import run_factor_analysis
from src.data_fetcher_baostock import IndexDataFetcher
from src.config_loader import load_app_config

logging.basicConfig(level=logging.WARNING)

config = load_app_config(root_dir)
fetcher = IndexDataFetcher()

try:
    report = run_factor_analysis(fetcher, config, "20250101", "20260331")

    print("\n" + "=" * 70)
    print("IC 分析详细统计")
    print("=" * 70)

    for factor, data in report['ic_analysis'].items():
        print(f"\n{factor}:")
        print(f"  IC Mean: {data['ic_mean']:.4f}")
        print(f"  IC Std: {data['ic_std']:.4f}")
        print(f"  IC IR: {data['ic_ir']:.2f}")
        print(f"  t-stat: {data['t_stat']:.2f}")
        print(f"  p-value: {data['p_value']:.4f}")
        print(f"  Positive Ratio: {data['positive_ratio']:.1%}")

    print("\n" + "=" * 70)
    print("分层回测详细统计")
    print("=" * 70)

    for factor, data in report['quantile_analysis'].items():
        print(f"\n{factor}:")
        print(f"  多空收益：{data['long_short_return']:.2%}")
        print(f"  多空夏普：{data['long_short_sharpe']:.2f}")
        print(f"  各组收益：", end="")
        for q in range(1, 6):
            print(f" Q{q}={data['final_returns'].get(q, 0):.2%}", end="")
        print()
        print(f"  各组夏普：", end="")
        for q in range(1, 6):
            print(f" Q{q}={data['sharpe_ratios'].get(q, 0):.2f}", end="")
        print()

finally:
    fetcher.close()
