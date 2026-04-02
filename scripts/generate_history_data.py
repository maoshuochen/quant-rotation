#!/usr/bin/env python3
"""
生成历史周期持仓和排名数据
输出到 web/dist/history.json
"""
import sys
from pathlib import Path
import json
import pandas as pd
from datetime import datetime, timedelta

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.data_fetcher_baostock import IndexDataFetcher
from src.scoring_baostock import ScoringEngine
from src.config_loader import load_app_config

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
    fetcher = IndexDataFetcher()
    indices = CONFIG.get('indices', [])
    active_indices = [idx for idx in indices if idx.get('enabled', True)]

    # 加载基准数据
    benchmark = fetcher.fetch_etf_history('510300', '20230101')

    # 加载所有 ETF 数据（一次性）
    print("加载 ETF 历史数据...")
    etf_data_dict = {}
    for idx in active_indices:
        etf = idx.get('etf')
        if etf:
            df = fetcher.fetch_etf_history(etf, '20230101')
            if not df.empty:
                etf_data_dict[idx['code']] = df
            print(f"  {idx['code']}: {len(df)} 行")

    # 初始化评分引擎
    scorer = ScoringEngine(CONFIG)

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
        while trade_date not in etf_data_dict.get(active_indices[0]['code'], pd.DataFrame()).index:
            trade_date -= timedelta(days=1)
            if (date - trade_date).days > 10:
                break
        else:
            trade_date = trade_date

        cutoff_date = trade_date

        # 截取到当前日期的数据
        scores_dict = {}
        for code, df in etf_data_dict.items():
            df_cutoff = df[df.index <= cutoff_date]
            if len(df_cutoff) < 60:  # 至少需要 60 天数据
                continue

            # 获取最新一条数据用于评分
            df_recent = df_cutoff.tail(252)  # 取近一年数据用于计算

            # 评分
            scores = scorer.score_index(
                df_recent,
                benchmark_data=benchmark[benchmark.index <= cutoff_date].tail(252) if not benchmark.empty else None
            )
            scores_dict[code] = scores

        if not scores_dict:
            continue

        # 排名
        ranking_df = scorer.rank_indices(scores_dict)

        if ranking_df.empty:
            continue

        # 提取前 20 名
        top_ranking = []
        # 只保存活跃因子
        active_factors = scorer.active_factors
        for _, row in ranking_df.head(20).iterrows():
            code = row['code']
            idx_info = next((idx for idx in indices if idx.get('code') == code), {})

            # 只提取活跃因子得分
            factors = {}
            for factor in active_factors:
                if factor in row and isinstance(row[factor], (int, float)) and not pd.isna(row[factor]):
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
            idx_info = next((idx for idx in indices if idx.get('code') == code), {})
            # 持仓也需要因子数据
            factors = {}
            for factor in active_factors:
                if factor in row and isinstance(row[factor], (int, float)) and not pd.isna(row[factor]):
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

    fetcher.close()

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
