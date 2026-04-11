#!/usr/bin/env python3
"""
生成前端所需的所有数据
统一输出到 web/dist/data.json
包含：
- backtest: 回测净值曲线
- history: 历史调仓记录
- ranking: 当前排名
"""
import sys
from pathlib import Path
import json
from datetime import datetime, timedelta
import pandas as pd

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.strategy_baostock import RotationStrategy
from src.config_loader import load_app_config

CONFIG = load_app_config(root_dir)
OUTPUT_DIR = root_dir / 'web' / 'dist'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_backtest_data() -> dict:
    """生成回测数据"""
    parquet_file = root_dir / 'backtest_results' / 'current.parquet'
    if not parquet_file.exists():
        print("警告：current.parquet 不存在")
        return {'summary': {}, 'chart_data': []}

    df = pd.read_parquet(parquet_file)
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])

    # 确保必要字段
    if 'drawdown' not in df.columns:
        df['rolling_max'] = df['value'].cummax()
        df['drawdown'] = (df['value'] - df['rolling_max']) / df['rolling_max']

    if 'return' not in df.columns:
        df['return'] = df['value'].pct_change()

    if 'cum_return' not in df.columns:
        df['cum_return'] = (df['value'] / df['value'].iloc[0]) - 1

    initial_capital = df['value'].iloc[0]
    final_value = df['value'].iloc[-1]
    total_return = (final_value - initial_capital) / initial_capital

    days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
    years = days / 365
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return

    max_drawdown = df['drawdown'].min()
    max_drawdown_date = df.loc[df['drawdown'].idxmin(), 'date']

    daily_returns = df['return'].dropna()
    sharpe = daily_returns.mean() / daily_returns.std() * (252 ** 0.5) if len(daily_returns) > 20 else 0

    chart_data = []
    for _, row in df.iterrows():
        chart_data.append({
            'date': row['date'].strftime('%Y-%m-%d'),
            'value': round(row['value'], 2),
            'cum_return': round(row['cum_return'], 4) if pd.notna(row['cum_return']) else 0,
            'drawdown': round(row['drawdown'], 4) if pd.notna(row['drawdown']) else 0
        })

    return {
        'summary': {
            'initial_capital': initial_capital,
            'final_value': round(final_value, 2),
            'total_return': round(total_return, 4),
            'annual_return': round(annual_return, 4),
            'max_drawdown': round(max_drawdown, 4),
            'max_drawdown_date': max_drawdown_date.strftime('%Y-%m-%d') if pd.notna(max_drawdown_date) else '',
            'sharpe_ratio': round(sharpe, 2),
            'trading_days': len(df),
            'period': {
                'start': df['date'].iloc[0].strftime('%Y-%m-%d'),
                'end': df['date'].iloc[-1].strftime('%Y-%m-%d')
            }
        },
        'chart_data': chart_data
    }


def generate_history_data() -> list:
    """生成历史调仓记录（最近 12 周）"""
    strategy = RotationStrategy()
    strategy.load_benchmark()

    indices = CONFIG.get('indices', [])
    active_factors = CONFIG.get('factor_model', {}).get('active_factors', ['momentum', 'trend', 'flow'])

    print("加载 ETF 历史数据...")
    etf_data_dict = strategy.fetch_all_data()

    end_date = datetime.now()
    start_date = datetime.now() - timedelta(days=90)

    dates = pd.date_range(start_date, end_date, freq='W-MON')
    history = []

    for date in dates:
        trade_date = date
        active_indices = [idx for idx in indices if idx.get('enabled', True)]
        first_code = active_indices[0]['code'] if active_indices else None

        if not first_code or first_code not in etf_data_dict:
            continue

        while trade_date not in etf_data_dict[first_code].index:
            trade_date -= timedelta(days=1)
            if (date - trade_date).days > 10:
                break

        cutoff_date = trade_date
        data_dict = {}
        for code, df in etf_data_dict.items():
            df_cutoff = df[df.index <= cutoff_date]
            if len(df_cutoff) >= 60:
                data_dict[code] = df_cutoff.tail(252)

        if not data_dict:
            continue

        ranking_df = strategy.run_scoring(data_dict)
        if ranking_df.empty:
            continue

        holdings = []
        for _, row in ranking_df.head(5).iterrows():
            code = row['code']
            idx_info = next((idx for idx in indices if idx.get('code') == code), {})

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
            'holdings': holdings
        })

    strategy.fetcher.close()
    return history


def generate_ranking_data() -> dict:
    """生成当前排名数据"""
    strategy = RotationStrategy()
    strategy.load_benchmark()

    indices = CONFIG.get('indices', [])
    active_factors = CONFIG.get('factor_model', {}).get('active_factors', ['momentum', 'trend', 'flow'])

    print("获取 ETF 数据...")
    data_dict = strategy.fetch_all_data()

    print("运行评分...")
    ranking_df = strategy.run_scoring(data_dict)

    ranking = []
    for _, row in ranking_df.iterrows():
        code = row['code']
        idx_info = next((idx for idx in indices if idx.get('code') == code), {})

        factors = {}
        for factor in active_factors:
            if factor in row and isinstance(row[factor], (int, float)) and not pd.isna(row[factor]):
                factors[factor] = round(float(row[factor]), 4)
            else:
                factors[factor] = 0.5

        ranking.append({
            'code': code,
            'name': idx_info.get('name', code),
            'etf': idx_info.get('etf', ''),
            'rank': int(row['rank']),
            'score': round(float(row['total_score']), 4),
            'factors': factors
        })

    return {
        'ranking': ranking,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M')
    }


def main():
    print("=" * 60)
    print("生成前端数据")
    print("=" * 60)

    # 生成所有数据
    backtest = generate_backtest_data()
    print(f"回测数据：{len(backtest['chart_data'])} 天")

    history = generate_history_data()
    print(f"历史记录：{len(history)} 个周期")

    ranking = generate_ranking_data()
    print(f"排名数据：{len(ranking['ranking'])} 个指数")

    # 合并输出
    output = {
        'backtest': backtest,
        'history': history,
        'ranking': ranking,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M')
    }

    # 保存到 web/dist/data.json
    output_file = OUTPUT_DIR / 'data.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n数据已保存：{output_file}")

    # 同时生成独立的 ranking.json 保持向后兼容
    ranking_file = OUTPUT_DIR / 'ranking.json'
    with open(ranking_file, 'w', encoding='utf-8') as f:
        json.dump(ranking, f, indent=2, ensure_ascii=False)
    print(f"排名已保存：{ranking_file}")


if __name__ == '__main__':
    main()
