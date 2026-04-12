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
from src.scoring_baostock import ScoringEngine
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
    indices = CONFIG.get('indices', [])
    active_factors = CONFIG.get('factor_model', {}).get('active_factors', ['momentum', 'trend', 'flow'])

    print("加载 ETF 历史数据...")
    # 只获取一次数据
    strategy = RotationStrategy()
    strategy.load_benchmark()
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

        # 使用 run_scoring 方法
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

    # 按日期排序
    history.sort(key=lambda x: x['date'], reverse=True)

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


def generate_recommendation(ranking_df, strategy, data_dict) -> dict:
    """生成推荐信号"""
    indices = CONFIG.get('indices', [])
    strategy_cfg = CONFIG.get('strategy', {})
    top_n = strategy_cfg.get('top_n', 5)
    buffer_n = strategy_cfg.get('buffer_n', 8)

    # 获取前一期持仓（用于生成调仓信号）
    history = generate_history_data()
    prev_holdings = set()
    if len(history) > 0:
        prev_holdings = set(h['code'] for h in history[0].get('holdings', []))

    # 当前排名
    if ranking_df.empty:
        return {'holdings': [], 'signals': [], 'selected_codes': []}

    ranking_list = []
    for _, row in ranking_df.iterrows():
        code = row['code']
        idx_info = next((idx for idx in indices if idx.get('code') == code), {})
        ranking_list.append({
            'code': code,
            'name': idx_info.get('name', code),
            'etf': idx_info.get('etf', ''),
            'rank': int(row['rank']),
            'score': round(float(row['total_score']), 4)
        })

    # 选股
    selected = ranking_df.head(top_n)['code'].tolist()
    hold_range = ranking_df.head(buffer_n)['code'].tolist()

    # 生成信号
    signals = []
    for code in prev_holdings:
        if code not in hold_range:
            idx_info = next((idx for idx in indices if idx.get('code') == code), {})
            signals.append({'action': 'sell', 'code': code, 'name': idx_info.get('name', code)})
    for code in selected:
        if code not in prev_holdings:
            idx_info = next((idx for idx in indices if idx.get('code') == code), {})
            signals.append({'action': 'buy', 'code': code, 'name': idx_info.get('name', code)})

    # 持仓
    holdings = []
    for code in selected:
        idx_info = next((idx for idx in indices if idx.get('code') == code), {})
        row = ranking_df[ranking_df['code'] == code].iloc[0] if code in ranking_df['code'].values else None
        if row is not None:
            holdings.append({
                'code': code,
                'name': idx_info.get('name', code),
                'weight': 1.0 / top_n,
                'score': round(float(row['total_score']), 4)
            })

    return {
        'holdings': holdings,
        'signals': signals,
        'selected_codes': selected,
        'top_n': top_n,
        'buffer_n': buffer_n,
        'rebalance_frequency': strategy_cfg.get('rebalance_frequency', 'weekly')
    }


def generate_health(data_dict) -> dict:
    """生成数据健康检查"""
    indices = CONFIG.get('indices', [])
    active_indices = [idx for idx in indices if idx.get('enabled', True)]
    active_codes = set(idx['code'] for idx in active_indices)

    # 价格数据
    available_count = sum(1 for code in active_codes if code in data_dict and len(data_dict[code]) > 0)
    price_data_status = 'ok' if available_count == len(active_codes) else 'degraded' if available_count > 0 else 'missing'

    # 北向资金（模拟）
    northbound_rows = 20  # 假设最近 20 日有数据
    northbound_status = 'ok' if northbound_rows >= 20 else 'degraded' if northbound_rows > 0 else 'missing'

    # ETF 份额快照
    snapshot_count = len([code for code in active_codes if code in data_dict])
    etf_shares_status = 'ok' if snapshot_count >= len(active_codes) * 0.8 else 'degraded' if snapshot_count > 0 else 'missing'

    return {
        'price_data': {
            'status': price_data_status,
            'available_count': available_count,
            'expected_count': len(active_codes)
        },
        'northbound': {
            'status': northbound_status,
            'recent_rows': northbound_rows
        },
        'etf_shares': {
            'status': etf_shares_status,
            'snapshot_count': snapshot_count
        },
        'universe': {
            'active_count': available_count
        }
    }


def generate_universe() -> dict:
    """生成指数池信息"""
    indices = CONFIG.get('indices', [])
    active = [idx for idx in indices if idx.get('enabled', True)]
    inactive = [idx for idx in indices if not idx.get('enabled', True)]

    return {
        'active': [{'code': idx['code'], 'name': idx.get('name', idx['code']), 'etf': idx.get('etf', '')} for idx in active],
        'inactive': [{'code': idx['code'], 'name': idx.get('name', idx['code']), 'etf': idx.get('etf', '')} for idx in inactive]
    }


def main():
    print("=" * 60)
    print("生成前端数据")
    print("=" * 60)

    # 初始化策略和获取数据
    strategy = RotationStrategy()
    strategy.load_benchmark()

    print("获取 ETF 数据...")
    data_dict = strategy.fetch_all_data()

    print("运行评分...")
    ranking_df = strategy.run_scoring(data_dict)

    # 生成所有数据
    backtest = generate_backtest_data()
    print(f"回测数据：{len(backtest['chart_data'])} 天")

    history = generate_history_data()
    print(f"历史记录：{len(history)} 个周期")

    ranking = generate_ranking_data()
    print(f"排名数据：{len(ranking['ranking'])} 个指数")

    recommendation = generate_recommendation(ranking_df, strategy, data_dict)
    print(f"推荐信号：{len(recommendation['signals'])} 个")

    health = generate_health(data_dict)
    print(f"健康检查：{health['price_data']['status']}")

    universe = generate_universe()
    print(f"指数池：{len(universe['active'])} 只活跃")

    # 合并输出为前端期望的格式
    output = {
        'backtest': backtest,
        'history': history,
        'ranking': ranking['ranking'],
        'recommendation': recommendation,
        'health': health,
        'universe': universe,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'market_regime': 'sideways',
        'market_regime_desc': '震荡市'
    }

    # 保存到 web/dist/data.json
    output_file = OUTPUT_DIR / 'data.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n数据已保存：{output_file}")

    # 同时生成独立的 ranking.json（包含 health 和 recommendation 供前端使用）
    ranking_output = {
        'ranking': ranking['ranking'],
        'recommendation': recommendation,
        'health': health,
        'universe': universe,
        'factor_weights': {},
        'factor_model': {'active_factors': CONFIG.get('factor_model', {}).get('active_factors', [])},
        'dynamic_weights': {},
        'market_regime': 'sideways',
        'market_regime_desc': '震荡市',
        'strategy': CONFIG.get('strategy', {}),
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    ranking_file = OUTPUT_DIR / 'ranking.json'
    with open(ranking_file, 'w', encoding='utf-8') as f:
        json.dump(ranking_output, f, indent=2, ensure_ascii=False)
    print(f"排名已保存：{ranking_file}")

    strategy.fetcher.close()


if __name__ == '__main__':
    main()
