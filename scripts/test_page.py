#!/usr/bin/env python3
"""
量化页面测试脚本
每次代码改动后自动执行验证

用法:
    python3 test_page.py                    # 运行全部测试
    python3 test_page.py --focus data       # 只测试数据相关
    python3 test_page.py --focus backtest   # 只测试回测相关
"""
import sys
import json
import argparse
from pathlib import Path

root_dir = Path(__file__).parent.parent  # 回到项目根目录
web_dist = root_dir / 'web' / 'dist'

def test_data_generation():
    """测试数据生成"""
    print("\n📊 测试数据生成...")
    
    ranking_path = web_dist / 'ranking.json'
    if not ranking_path.exists():
        print("  ❌ ranking.json 不存在")
        return False
    
    with open(ranking_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 检查指数数量
    if len(data.get('ranking', [])) < 15:
        print(f"  ❌ 指数数量不足：{len(data['ranking'])}")
        return False
    print(f"  ✅ 指数数量：{len(data['ranking'])}")
    
    # 检查因子得分（不能全为 0.5）
    zero_point_five_count = 0
    total_factors = 0
    for item in data['ranking'][:5]:  # 检查前 5 名
        factors = item.get('factors', {})
        for key in ['momentum', 'trend', 'value']:
            if key in factors:
                total_factors += 1
                if factors[key] == 0.5:
                    zero_point_five_count += 1
    
    if total_factors > 0 and zero_point_five_count / total_factors > 0.8:
        print(f"  ❌ 因子得分异常：{zero_point_five_count}/{total_factors} 为 0.5")
        return False
    print(f"  ✅ 因子得分正常")
    
    # 检查更新时间
    if 'update_time' not in data:
        print("  ⚠️ 缺少更新时间")
    else:
        print(f"  ✅ 更新时间：{data['update_time']}")
    
    return True


def test_backtest_data():
    """测试回测数据"""
    print("\n📈 测试回测数据...")
    
    backtest_path = web_dist / 'backtest.json'
    if not backtest_path.exists():
        print("  ⚠️ backtest.json 不存在（可选）")
        return True
    
    with open(backtest_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 检查必要字段（可能在 summary 嵌套中）
    summary = data.get('summary', data)  # 兼容两种格式
    
    required_fields = ['total_return', 'max_drawdown', 'sharpe_ratio']
    for field in required_fields:
        if field not in summary:
            print(f"  ❌ 缺少字段：{field}")
            return False
    
    print(f"  ✅ 总收益：{summary['total_return']*100:.2f}%")
    print(f"  ✅ 最大回撤：{summary['max_drawdown']*100:.2f}%")
    print(f"  ✅ 夏普比率：{summary['sharpe_ratio']:.2f}")
    
    return True


def test_data_quality():
    """数据质量检查"""
    print("\n🔍 数据质量检查...")
    
    ranking_path = web_dist / 'ranking.json'
    with open(ranking_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 检查前 3 名的得分分布
    for item in data['ranking'][:3]:
        factors = item.get('factors', {})
        score = item.get('score', 0)
        
        # 总分应该在 0.4-0.8 之间（合理范围）
        if score < 0.3 or score > 0.9:
            print(f"  ⚠️ {item['name']} 得分异常：{score:.4f}")
        
        # 检查是否有极端因子得分
        for key, val in factors.items():
            if val < 0 or val > 1:
                print(f"  ❌ {item['name']} 因子 {key} 超出范围：{val}")
                return False
    
    print("  ✅ 数据质量正常")
    return True


def test_data_rows():
    """针对性测试：数据行数（针对 2026-03-22 数据源切换）"""
    print("\n📏 测试数据行数（针对性测试）...")
    
    cache_dir = root_dir / 'data' / 'raw'  # 缓存目录是 data/raw
    if not cache_dir.exists():
        print("  ⚠️ 缓存目录不存在")
        return True
    
    parquet_files = list(cache_dir.glob('*_etf_history.parquet'))
    if not parquet_files:
        print("  ⚠️ 无 ETF 缓存文件")
        return True
    
    import pandas as pd
    
    min_rows = float('inf')
    for pf in parquet_files[:5]:  # 检查前 5 个
        df = pd.read_parquet(pf)
        min_rows = min(min_rows, len(df))
    
    if min_rows < 252:
        print(f"  ❌ 数据行数不足：{min_rows} < 252（1 年）")
        return False
    
    print(f"  ✅ 最少数据行数：{min_rows} >= 252")
    return True


def test_factor_diversity():
    """针对性测试：因子得分多样性（针对 2026-03-22 因子全 0.5 问题）"""
    print("\n🎯 测试因子得分多样性（针对性测试）...")
    
    ranking_path = web_dist / 'ranking.json'
    if not ranking_path.exists():
        print("  ❌ ranking.json 不存在")
        return False
    
    with open(ranking_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 检查关键因子是否不再全为 0.5
    critical_factors = ['momentum', 'trend', 'value']
    zero_point_five_ratio = {}
    
    for factor in critical_factors:
        count_05 = 0
        total = 0
        for item in data['ranking'][:10]:  # 检查前 10 名
            factors = item.get('factors', {})
            if factor in factors:
                total += 1
                if factors[factor] == 0.5:
                    count_05 += 1
        zero_point_five_ratio[factor] = count_05 / total if total > 0 else 0
    
    # 如果任何关键因子的 0.5 比例 > 80%，说明有问题
    for factor, ratio in zero_point_five_ratio.items():
        if ratio > 0.8:
            print(f"  ❌ {factor} 因子 80% 以上为 0.5（{ratio*100:.1f}%）")
            return False
    
    print(f"  ✅ 因子得分多样性正常")
    print(f"     动量 0.5 比例：{zero_point_five_ratio['momentum']*100:.1f}%")
    print(f"     趋势 0.5 比例：{zero_point_five_ratio['trend']*100:.1f}%")
    print(f"     估值 0.5 比例：{zero_point_five_ratio['value']*100:.1f}%")
    return True


def main():
    parser = argparse.ArgumentParser(description='量化页面测试')
    parser.add_argument('--focus', choices=['data', 'backtest', 'data_quality', 'recent'],
                       help='聚焦特定测试类型')
    args = parser.parse_args()
    
    print("=" * 50)
    print("量化页面自动化测试")
    if args.focus:
        print(f"（聚焦模式：{args.focus}）")
    print("=" * 50)
    
    results = []
    
    # 根据改动类型选择测试
    if args.focus == 'recent':
        # 最近改动（2026-03-22 数据源切换）的针对性测试
        print("\n🔍 运行最近改动的针对性测试...")
        results.append(("数据行数", test_data_rows()))
        results.append(("因子多样性", test_factor_diversity()))
    elif args.focus == 'data':
        results.append(("数据生成", test_data_generation()))
        results.append(("数据行数", test_data_rows()))
        results.append(("因子多样性", test_factor_diversity()))
    elif args.focus == 'backtest':
        results.append(("回测数据", test_backtest_data()))
    elif args.focus == 'data_quality':
        results.append(("数据质量", test_data_quality()))
        results.append(("因子多样性", test_factor_diversity()))
    else:
        # 完整测试
        results.append(("数据生成", test_data_generation()))
        results.append(("回测数据", test_backtest_data()))
        results.append(("数据质量", test_data_quality()))
        results.append(("数据行数", test_data_rows()))
        results.append(("因子多样性", test_factor_diversity()))
    
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
        if not passed:
            all_passed = False
    
    print("=" * 50)
    
    if all_passed:
        print("🎉 所有测试通过！")
        return 0
    else:
        print("⚠️  部分测试失败，请检查！")
        return 1


if __name__ == "__main__":
    sys.exit(main())
