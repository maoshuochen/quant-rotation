#!/usr/bin/env python3
"""
优化结果验证脚本
系统性地验证贝叶斯优化找到的最优参数
"""
import sys
import numpy as np
from pathlib import Path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import yaml
import pandas as pd
from src.data_fetcher_baostock import IndexDataFetcher
from src.scoring_baostock import ScoringEngine
from src.portfolio import SimulatedPortfolio
from datetime import datetime

def load_config():
    with open(root_dir / 'config' / 'config.yaml', 'r') as f:
        return yaml.safe_load(f)

def run_backtest_with_params(config, params, start_date, end_date, fetcher, verbose=False):
    """使用指定参数运行回测"""

    # 构建配置
    test_config = config.copy()

    # 转换参数名 (value_weight -> value)
    if any('_weight' in k for k in params.keys()):
        weights = {}
        for k, v in params.items():
            factor_name = k.replace('_weight', '')
            weights[factor_name] = v
        test_config['factor_weights'] = weights

    scorer = ScoringEngine(test_config)

    # 获取数据
    etf_data = {}
    indices = config.get('indices', [])
    start = "20240101" if start_date < "20250101" else start_date

    for idx in indices:
        etf = idx.get('etf')
        code = idx.get('code')
        if etf:
            df = fetcher.fetch_etf_history(etf, start, force_refresh=False)
            if not df.empty:
                etf_data[code] = df

    benchmark_data = etf_data.get('000300.SH', pd.DataFrame())

    strategy = config.get('strategy', {})
    top_n = strategy.get('top_n', 5)
    buffer_n = strategy.get('buffer_n', 8)

    portfolio = SimulatedPortfolio(
        initial_capital=1_000_000,
        commission_rate=0.0003,
        slippage=0.001,
        stop_loss_config=config.get('stop_loss', {}),
        cooldown_days=0
    )

    # 生成交易日期
    first_df = list(etf_data.values())[0]
    all_dates = first_df.index.tolist()
    trade_dates = [d for d in all_dates
                   if pd.to_datetime(start_date) <= d <= pd.to_datetime(end_date)]

    # 调仓日期
    rebalance_dates = [d for d in trade_dates if d.weekday() == 0]  # 周一

    daily_values = []

    for date in trade_dates:
        prices = {code: df.loc[date, 'close']
                  for code, df in etf_data.items() if date in df.index}

        # 检查止损
        if prices and portfolio.positions:
            stop_loss_signals = portfolio.check_stop_loss(prices, date.strftime('%Y-%m-%d'))
            if any(stop_loss_signals.values()):
                names = {idx['code']: idx['name'] for idx in indices}
                portfolio.execute_stop_loss(stop_loss_signals, prices, names, date.strftime('%Y-%m-%d'))

        # 记录净值
        if prices:
            portfolio.record_daily_value(date.strftime('%Y-%m-%d'), prices)
            daily_values.append({
                'date': date,
                'value': portfolio.get_portfolio_value(prices)
            })

        # 调仓
        if date in rebalance_dates and len(trade_dates) - trade_dates.index(date) > 5:
            scores_dict = {}
            for code, df in etf_data.items():
                hist_df = df[df.index <= date]
                if len(hist_df) >= 20:
                    scores = scorer.score_index(hist_df, benchmark_data)
                    scores_dict[code] = scores

            ranking = scorer.rank_indices(scores_dict)
            if ranking.empty:
                continue

            selected = ranking.head(top_n)['code'].tolist()
            hold_range = ranking.head(buffer_n)['code'].tolist()
            current_codes = set(portfolio.positions.keys())

            signals = {'buy': [], 'sell': []}
            for code in current_codes:
                if code not in hold_range:
                    signals['sell'].append(code)
            for code in selected:
                if code not in current_codes:
                    signals['buy'].append(code)

            if signals['buy'] or signals['sell']:
                names = {idx['code']: idx['name'] for idx in indices}
                portfolio.execute_signal(signals, prices, names, date.strftime('%Y-%m-%d'))

    # 计算指标
    values_df = pd.DataFrame(daily_values)
    values_df['return'] = values_df['value'].pct_change()
    values_df['cum_return'] = (1 + values_df['return']).cumprod() - 1

    final_value = values_df['value'].iloc[-1]
    total_return = (final_value - 1_000_000) / 1_000_000

    # 最大回撤
    values_df['rolling_max'] = values_df['value'].cummax()
    values_df['drawdown'] = (values_df['value'] - values_df['rolling_max']) / values_df['rolling_max']
    max_drawdown = values_df['drawdown'].min()

    # 夏普比率
    daily_returns = values_df['return'].dropna()
    sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252) if len(daily_returns) > 20 and daily_returns.std() > 0 else 0

    # 索提诺比率
    downside_returns = daily_returns[daily_returns < 0]
    sortino = daily_returns.mean() / downside_returns.std() * np.sqrt(252) if len(downside_returns) > 10 and downside_returns.std() > 0 else 0

    # 卡玛比率
    calmar = total_return / abs(max_drawdown) if max_drawdown != 0 else 0

    return {
        'sharpe': sharpe,
        'sortino': sortino,
        'calmar': calmar,
        'total_return': total_return,
        'max_drawdown': max_drawdown,
        'final_value': final_value
    }


def verify_optimization_results():
    """验证优化结果"""
    import numpy as np

    print("=" * 70)
    print("优化结果验证")
    print("=" * 70)

    config = load_config()
    fetcher = IndexDataFetcher()

    # 读取最近的优化结果
    opt_dir = root_dir / 'optimization_results'
    opt_files = sorted(opt_dir.glob('trial_history_factor_weights_*.csv'), reverse=True)

    if not opt_files:
        print("未找到优化结果文件!")
        return

    df = pd.read_csv(opt_files[0])
    print(f"\n验证文件：{opt_files[0].name}")
    print(f"试验总数：{len(df)}")

    # 提取 score 列
    test_params = []
    test_scores = []

    for i, row in df.iterrows():
        params = {
            'value_weight': row['value_weight'],
            'momentum_weight': row['momentum_weight'],
            'trend_weight': row['trend_weight'],
            'flow_weight': row['flow_weight'],
            'volatility_weight': row['volatility_weight']
        }
        test_params.append(params)
        test_scores.append(row['score'])

    # 选择测试样本：最优、中等、最差
    test_indices = [
        df['score'].idxmax(),  # 最优
        df['score'].idxmin(),  # 最差
        len(df) // 2,  # 中等
        len(df) // 4,  # 中上
        3 * len(df) // 4  # 中下
    ]
    test_indices = sorted(set(test_indices))

    print("\n" + "=" * 70)
    print("实际回测验证")
    print("=" * 70)

    results = []
    for idx in test_indices:
        row = df.iloc[idx]
        params = {
            'value_weight': row['value_weight'],
            'momentum_weight': row['momentum_weight'],
            'trend_weight': row['trend_weight'],
            'flow_weight': row['flow_weight'],
            'volatility_weight': row['volatility_weight']
        }

        print(f"\n试验 #{idx}:")
        print(f"  权重：value={row['value_weight']:.2f}, mom={row['momentum_weight']:.2f}, "
              f"trend={row['trend_weight']:.2f}, flow={row['flow_weight']:.2f}, "
              f"vol={row['volatility_weight']:.2f}")
        print(f"  优化器 Sharpe: {row['score']:.3f}")

        # 实际回测
        result = run_backtest_with_params(config, params, "20250101", "20260331", fetcher)

        print(f"  实际 Sharpe: {result['sharpe']:.3f}")
        print(f"  实际收益：{result['total_return']:.1%}")
        print(f"  实际回撤：{result['max_drawdown']:.1%}")

        results.append({
            'idx': idx,
            'reported_sharpe': row['score'],
            'actual_sharpe': result['sharpe'],
            'actual_return': result['total_return'],
            'actual_drawdown': result['max_drawdown'],
            'params': params
        })

    # 汇总分析
    print("\n" + "=" * 70)
    print("验证汇总")
    print("=" * 70)

    summary_df = pd.DataFrame(results)
    summary_df['差异'] = summary_df['reported_sharpe'] - summary_df['actual_sharpe']
    summary_df['差异率'] = summary_df['差异'] / summary_df['reported_sharpe']

    print("\nSharpe 对比:")
    print(summary_df[['idx', 'reported_sharpe', 'actual_sharpe', '差异', '差异率']].to_string(index=False))

    avg_diff = summary_df['差异'].mean()
    avg_diff_pct = summary_df['差异率'].mean()
    print(f"\n平均差异：{avg_diff:.3f} ({avg_diff_pct:.1%})")

    if avg_diff > 0.5:
        print("⚠️  警告：优化器报告 Sharpe 与实际值存在显著差异，可能存在过拟合或逻辑不一致")
    elif avg_diff > 0.2:
        print("⚠️  注意：存在一定差异，建议谨慎使用优化结果")
    else:
        print("✓ 优化器报告与实际结果基本一致")

    fetcher.close()
    return results


if __name__ == "__main__":
    verify_optimization_results()
