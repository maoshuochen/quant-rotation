#!/usr/bin/env python3
"""
导出排名数据为 JSON 格式，供前端使用
"""
import sys
from pathlib import Path
import json
from datetime import datetime
import pandas as pd

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.data_fetcher_baostock import IndexDataFetcher
from src.scoring_baostock import ScoringEngine
import yaml

def load_config() -> dict:
    """加载配置"""
    config_path = root_dir / 'config' / 'config.yaml'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}

def export_ranking_json():
    """导出排名数据为 JSON"""
    config = load_config()
    
    # 初始化
    fetcher = IndexDataFetcher()
    scorer = ScoringEngine(config)
    
    # 加载基准
    benchmark_data = fetcher.fetch_etf_history("510300", "20250101")
    
    # 获取所有 ETF 数据
    indices = config.get('indices', [])
    data_dict = {}
    
    for idx in indices:
        etf = idx.get('etf')
        code = idx.get('code')
        if etf:
            df = fetcher.fetch_etf_history(etf, "20250101")
            if not df.empty:
                data_dict[code] = df
    
    # 计算评分（需要获取各因子详细得分）
    ranking_list = []
    
    for idx in indices:
        code = idx.get('code')
        etf = idx.get('etf')
        
        if code not in data_dict:
            continue
        
        df = data_dict[code]
        
        # 计算各因子得分
        close = df['close']
        returns = close.pct_change().dropna()
        
        factors = {
            'momentum': scorer.calc_momentum_score(returns),
            'volatility': scorer.calc_volatility_score(returns),
            'trend': scorer.calc_trend_score(close),
            'value': scorer.calc_value_score(close),
            'relative_strength': scorer.calc_relative_strength(close, benchmark_data['close']) if not benchmark_data.empty else 0.5
        }
        
        # 处理 NaN 值
        for key in factors:
            if pd.isna(factors[key]) or factors[key] is None:
                factors[key] = 0.5
        
        # 计算总分
        weights = config.get('factor_weights', {})
        total_score = (
            factors.get('momentum', 0.5) * weights.get('momentum', 0.20) +
            factors.get('volatility', 0.5) * weights.get('volatility', 0.15) +
            factors.get('trend', 0.5) * weights.get('trend', 0.20) +
            factors.get('value', 0.5) * weights.get('value', 0.25) +
            factors.get('relative_strength', 0.5) * weights.get('relative_strength', 0.20)
        )
        
        ranking_list.append({
            'code': code,
            'name': idx.get('name', ''),
            'etf': etf,
            'score': round(total_score, 4),
            'factors': {k: round(v, 4) for k, v in factors.items()}
        })
    
    # 排序
    ranking_list.sort(key=lambda x: x['score'], reverse=True)
    for i, item in enumerate(ranking_list):
        item['rank'] = i + 1
    
    # 输出 JSON
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': 'Baostock',
        'ranking': ranking_list,
        'factor_weights': config.get('factor_weights', {}),
        'strategy': config.get('strategy', {})
    }
    
    # 保存到文件
    output_dir = root_dir / 'web' / 'public'
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / 'ranking.json'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 数据已导出到：{output_file}")
    print(f"📊 共 {len(ranking_list)} 个指数")
    
    fetcher.close()
    
    return output_file

if __name__ == "__main__":
    export_ranking_json()
