#!/usr/bin/env python3
"""
生成历史周期持仓和排名数据
输出到 web/dist/history.json
使用 RotationStrategy 确保与 ranking.json 使用相同的评分逻辑（动态权重）
"""
import sys
from pathlib import Path
import json
import pandas as pd
from datetime import datetime, timedelta

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.strategy_baostock import RotationStrategy  # noqa: E402
from src.config_loader import load_app_config  # noqa: E402

CONFIG = load_app_config(root_dir)


def get_historical_rankings(
    start_date: str,
    end_date: str,
    frequency: str = 'weekly'
) -> list:
    """
    获取历史周期的排名和持仓数据

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        frequency: 'weekly' 或 'monthly'

    Returns:
        历史数据列表
    """
    # 使用 RotationStrategy 确保与 ranking.json 使用相同的评分逻辑（动态权重）
    strategy = RotationStrategy()
    strategy.load_benchmark()  # 加载基准并设置动态权重

    print(f"市场状态：{strategy.scorer.current_regime}")
    print(f"动态权重：{strategy.scorer.current_weights}")

    indices = CONFIG.get('indices', [])
    active_factors = CONFIG.get('factor_model', {}).get(
        'active_factors', ['momentum', 'trend', 'flow'])

    # 获取所有 ETF 数据
    print("加载 ETF 历史数据...")
    etf_data_dict = strategy.fetch_all_data()

    # 生成日期序列
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    if frequency == 'weekly':
        dates = pd.date_range(start_dt, end_dt, freq='W-MON')
    else:
        dates = pd.date_range(start_dt, end_dt, freq='MS')

    history = []

    for date in dates:
        # 找到最接近的交易日（向前找）
        trade_date = date
        # 获取活跃指数列表
        active_indices = [idx for idx in indices if idx.get('enabled', True)]
        first_code = active_indices[0]['code'] if active_indices else None
        if not first_code or first_code not in etf_data_dict:
            continue

        while trade_date not in etf_data_dict[first_code].index:
            trade_date -= timedelta(days=1)
            if (date - trade_date).days > 10:
                break

        cutoff_date = trade_date

        # 使用策略的评分逻辑（动态权重）
        data_dict = {}
        for code, df in etf_data_dict.items():
            df_cutoff = df[df.index <= cutoff_date]
            if len(df_cutoff) >= 60:
                data_dict[code] = df_cutoff.tail(252)

        if not data_dict:
            continue

        # 运行评分
        ranking_df = strategy.run_scoring(data_dict)

        if ranking_df.empty:
            continue

        # 提取前 20 名
        top_ranking = []
        for _, row in ranking_df.head(20).iterrows():
            code = row['code']
            idx_info = next(
                (idx for idx in indices if idx.get('code') == code), {})

            # 只提取活跃因子得分
            factors = {}
            for factor in active_factors:
                is_valid = isinstance(row[factor], (int, float))
                if factor in row and is_valid and not pd.isna(row[factor]):
                    factors[factor] = round(float(row[factor]), 4)
                else:
                    factors[factor] = 0.5

            top_ranking.append({
                'code': code,
                'name': idx_info.get('name', code),
                'etf': idx_info.get('etf', ''),
                'rank': int(row['rank']),
                'score': round(float(row['total_score']), 4),
                'factors': factors
            })

        # 前 5 名持仓
        holdings = []
        for _, row in ranking_df.head(5).iterrows():
            code = row['code']
            idx_info = next(
                (idx for idx in indices if idx.get('code') == code), {})
            factors = {}
            for factor in active_factors:
                is_valid = isinstance(row[factor], (int, float))
                if factor in row and is_valid and not pd.isna(row[factor]):
                    factors[factor] = round(float(row[factor]), 4)
                else:
                    factors[factor] = 0.5
            holdings.append({
                'code': code,
                'name': idx_info.get('name', code),
                'etf': idx_info.get('etf', ''),
                'rank': int(row['rank']),
                'score': round(float(row['total_score']), 4),
                'factors': factors
            })

        history.append({
            'date': cutoff_date.strftime('%Y-%m-%d'),
            'ranking': top_ranking,
            'holdings': holdings
        })

        print(f"  {cutoff_date.strftime('%Y-%m-%d')}: {len(holdings)} 持仓")

    # 关闭资源
    strategy.fetcher.close()

    # 去除重复日期（保留第一个）
    seen_dates = set()
    unique_history = []
    for item in history:
        if item['date'] not in seen_dates:
            seen_dates.add(item['date'])
            unique_history.append(item)
        else:
            print(f"  ⚠️ 去除重复日期：{item['date']}")

    return unique_history


def main():
    print("生成历史周期数据...")

    # 生成近一年的数据
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    history = get_historical_rankings(start_date, end_date, frequency='weekly')

    if not history:
        print("未生成任何数据")
        return

    # 输出到文件
    output_dir = root_dir / 'web' / 'dist'
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / 'history.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'history': history,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M')
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已生成 {output_file}")
    print(f"   共 {len(history)} 个周期")
    print(f"   日期范围：{history[0]['date']} ~ {history[-1]['date']}")


if __name__ == "__main__":
    main()
