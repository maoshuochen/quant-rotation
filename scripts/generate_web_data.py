#!/usr/bin/env python3
"""
生成前端页面所需数据 (包含扩展资金流因子)
使用策略对象统一处理
"""
import sys
from pathlib import Path
import json
from datetime import datetime

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))
outputs_dir = root_dir / 'outputs' / 'frontend'

from src.strategy_baostock import RotationStrategy

def run_scoring():
    """运行评分并生成前端数据"""
    print("🚀 生成前端数据...")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    
    # 初始化策略
    strategy = RotationStrategy()
    
    # 加载基准（同时更新市场状态和动态权重）
    print("  加载基准数据...")
    strategy.load_benchmark()
    
    # 获取所有 ETF 数据
    print("  获取 ETF 数据...")
    data_dict = strategy.fetch_all_data()
    
    # 运行评分（使用动态权重）
    print("  运行评分系统...")
    print(f"  市场状态：{strategy.scorer.current_regime}")
    print(f"  动态权重：{strategy.scorer.current_weights}")
    ranking_df = strategy.run_scoring(data_dict)
    signals = strategy.generate_signals(ranking_df)
    
    # 转换为列表 (需要从 ranking_df 提取数据)
    ranking = []
    
    # 从 scores_dict 获取名称和 ETF 信息
    scores_dict = {}  # 需要在策略中保存
    
    for _, row in ranking_df.iterrows():
        code = row['code']
        
        # 查找指数信息
        idx_info = {}
        for idx in strategy.indices:
            if idx.get('code') == code:
                idx_info = idx
                break
        
        # 提取因子得分（排除归因数据）
        factors = {}
        attribution = {}
        for k, v in row.items():
            if k in ['code', 'total_score', 'rank']:
                continue
            if k == 'attribution':
                attribution = v if isinstance(v, dict) else {}
            else:
                factors[k] = round(v, 4) if isinstance(v, (int, float)) else v
        
        item = {
            'code': code,
            'name': idx_info.get('name', code),
            'etf': idx_info.get('etf', ''),
            'score': round(row['total_score'], 4),
            'factors': factors,
            'attribution': attribution,  # 添加归因数据
            'rank': int(row['rank'])
        }
        ranking.append(item)
    
    # 获取资金流详情
    flow_details = getattr(strategy, 'flow_details', {})
    
    # 转换 numpy 类型为 Python 原生类型
    def convert_np(obj):
        import numpy as np
        if isinstance(obj, dict):
            return {k: convert_np(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_np(i) for i in obj]
        elif isinstance(obj, (np.floating, float)):
            return round(float(obj), 4)
        elif isinstance(obj, (np.integer, int)):
            return int(obj)
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        return obj
    
    flow_details = convert_np(flow_details)
    
    # 也要转换 ranking 中的 attribution 数据
    for item in ranking:
        item['attribution'] = convert_np(item.get('attribution', {}))
        item['factors'] = convert_np(item.get('factors', {}))
    
    # 生成 ranking.json
    ranking_data = {
        'ranking': ranking,
        'factor_weights': strategy.config.get('factor_weights', {}),
        'score_weights': strategy.scorer.current_weights,
        'factor_model': strategy.config.get('factor_model', {}),
        'dynamic_weights': strategy.scorer.current_weights,
        'market_regime': strategy.scorer.current_regime,
        'market_regime_desc': strategy.scorer.get_regime_description(),
        'strategy': strategy.config.get('strategy', {}),
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'flow_details': flow_details,
        'health': getattr(strategy, 'data_health', {}),
        'recommendation': strategy.build_recommendation(ranking_df, signals),
    }
    
    outputs_ranking_path = outputs_dir / 'ranking.json'
    with open(outputs_ranking_path, 'w', encoding='utf-8') as f:
        json.dump(ranking_data, f, ensure_ascii=False, indent=2)

    ranking_path = root_dir / 'web' / 'dist' / 'ranking.json'
    with open(ranking_path, 'w', encoding='utf-8') as f:
        json.dump(ranking_data, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ 已生成 {ranking_path}")
    print(f"  ✅ 已生成 {outputs_ranking_path}")
    print(f"     共 {len(ranking)} 个指数")
    
    # 生成 backtest.json (如果有回测数据)
    backtest_path = root_dir / 'backtest_results' / 'latest.json'
    if backtest_path.exists():
        with open(backtest_path, 'r', encoding='utf-8') as f:
            backtest_data = json.load(f)
        
        # 复制到 web/dist
        dist_backtest_path = root_dir / 'web' / 'dist' / 'backtest.json'
        with open(dist_backtest_path, 'w', encoding='utf-8') as f:
            json.dump(backtest_data, f, ensure_ascii=False, indent=2)

        outputs_backtest_path = outputs_dir / 'backtest.json'
        with open(outputs_backtest_path, 'w', encoding='utf-8') as f:
            json.dump(backtest_data, f, ensure_ascii=False, indent=2)
        
        print(f"  ✅ 已生成 {dist_backtest_path}")
        print(f"  ✅ 已生成 {outputs_backtest_path}")
    else:
        print(f"  ⚠️ 回测数据不存在")
    
    # 关闭资源
    strategy.fetcher.close()
    
    print("\n✅ 前端数据生成完成!")
    print(f"\n📊 排名预览:")
    for item in ranking[:5]:
        print(f"   {item['rank']}. {item['name']}: {item['score']:.4f}")
    
    print(f"\n💰 资金流详情:")
    for code in list(flow_details.keys())[:3]:
        fd = flow_details[code]
        print(f"   {code}: flow={fd.get('volume_trend', 'N/A'):.2f} (vol), nb={fd.get('northbound', 'N/A'):.2f}")


if __name__ == "__main__":
    run_scoring()
