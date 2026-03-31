#!/usr/bin/env python3
"""测试不同冷却期配置"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_fetcher_baostock import IndexDataFetcher
from src.scoring_baostock import ScoringEngine
from src.portfolio import SimulatedPortfolio
from src.config_loader import load_app_config
import pandas as pd
from datetime import datetime
import time
import yaml

def load_config():
    with open('config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def run_backtest(cooldown_days, start_date="20250101", end_date="20260331"):
    config = load_config()
    indices = config.get('indices', [])
    strategy = config.get('strategy', {})
    top_n = strategy.get('top_n', 5)
    buffer_n = strategy.get('buffer_n', 8)
    rebalance_freq = strategy.get('rebalance_frequency', 'weekly')
    stop_loss_config = config.get('stop_loss', {})
    
    # 覆盖冷却期配置
    test_config = stop_loss_config.copy()
    test_config['cooldown_days'] = cooldown_days
    
    fetcher = IndexDataFetcher()
    scorer = ScoringEngine(config)
    portfolio = SimulatedPortfolio(
        initial_capital=1_000_000,
        commission_rate=config.get('portfolio', {}).get('commission', 0.0003),
        slippage=config.get('portfolio', {}).get('slippage', 0.001),
        stop_loss_config=test_config,
        cooldown_days=cooldown_days
    )
    
    # 获取数据
    etf_data = {}
    for idx in indices:
        etf = idx.get('etf')
        code = idx.get('code')
        if etf:
            start = "20240101" if start_date < "20250101" else start_date
            df = fetcher.fetch_etf_history(etf, start, force_refresh=False)
            if not df.empty:
                etf_data[code] = df
    
    if not etf_data:
        return None
    
    benchmark_data = etf_data.get('000300.SH', pd.DataFrame())
    first_df = list(etf_data.values())[0]
    all_dates = first_df.index.tolist()
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    trade_dates = [d for d in all_dates if start_dt <= d <= end_dt]
    
    # 确定调仓日期
    rebalance_dates = []
    for date in trade_dates:
        if rebalance_freq == 'weekly':
            if date.weekday() == 0:
                rebalance_dates.append(date)
        elif rebalance_freq == 'monthly':
            if date.day <= 5:
                rebalance_dates.append(date)
        else:
            rebalance_dates.append(date)
    
    if not rebalance_dates:
        rebalance_dates = [trade_dates[0]]
    
    # 回测循环
    daily_values = []
    stop_loss_stats = {'individual': 0, 'trailing': 0, 'portfolio': 0}
    skipped_cooldown = 0
    
    for date in trade_dates:
        date_str = date.strftime('%Y-%m-%d')
        
        prices = {code: df.loc[date, 'close'] for code, df in etf_data.items() if date in df.index}
        
        if prices and portfolio.positions:
            stop_loss_signals = portfolio.check_stop_loss(prices, date_str)
            if any(stop_loss_signals.values()):
                for signal_type, codes in stop_loss_signals.items():
                    if codes:
                        stop_loss_stats[signal_type] += len(codes)
                names = {idx['code']: idx['name'] for idx in indices}
                portfolio.execute_stop_loss(stop_loss_signals, prices, names, date_str)
        
        if prices:
            portfolio.record_daily_value(date_str, prices)
            value = portfolio.get_portfolio_value(prices)
            daily_values.append({'date': date_str, 'value': value})
        
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
                trades = portfolio.execute_signal(signals, prices, names, date_str)
                # 统计因冷却期跳过的买入
                for code in signals['buy']:
                    if portfolio.is_in_cooldown(code, date_str):
                        skipped_cooldown += 1
    
    # 计算统计
    values_df = pd.DataFrame(daily_values)
    values_df['date'] = pd.to_datetime(values_df['date'])
    values_df['return'] = values_df['value'].pct_change()
    
    final_value = values_df['value'].iloc[-1]
    total_return = (final_value - 1_000_000) / 1_000_000
    
    days = (values_df['date'].iloc[-1] - values_df['date'].iloc[0]).days
    years = days / 365
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return
    
    values_df['rolling_max'] = values_df['value'].cummax()
    values_df['drawdown'] = (values_df['value'] - values_df['rolling_max']) / values_df['rolling_max']
    max_drawdown = values_df['drawdown'].min()
    
    daily_returns = values_df['return'].dropna()
    sharpe = daily_returns.mean() / daily_returns.std() * (252 ** 0.5) if len(daily_returns) > 20 else 0
    
    fetcher.close()
    
    return {
        'cooldown': cooldown_days,
        'total_return': total_return * 100,
        'annual_return': annual_return * 100,
        'max_drawdown': max_drawdown * 100,
        'sharpe': sharpe,
        'stop_loss_count': sum(stop_loss_stats.values()),
        'individual_sl': stop_loss_stats['individual'],
        'trailing_sl': stop_loss_stats['trailing'],
        'portfolio_sl': stop_loss_stats['portfolio'],
        'skipped_cooldown': skipped_cooldown
    }

if __name__ == "__main__":
    print("测试不同冷却期配置 (0=无冷却期)\n")
    print("=" * 100)
    
    cooldowns = [0, 3, 5, 7, 10, 15]
    results = []
    
    for cd in cooldowns:
        print(f"\n测试冷却期 {cd} 天...", end=" ")
        start = time.time()
        result = run_backtest(cd)
        elapsed = time.time() - start
        if result:
            results.append(result)
            print(f"完成 ({elapsed:.1f}s)")
            print(f"  收益:{result['total_return']:6.2f}%  年化:{result['annual_return']:6.2f}%  回撤:{result['max_drawdown']:6.2f}%  夏普:{result['sharpe']:.2f}  止损:{result['stop_loss_count']}次  跳过:{result['skipped_cooldown']}次")
        else:
            print("失败")
    
    print("\n" + "=" * 100)
    print("\n📊 冷却期对比汇总\n")
    print(f"{'冷却期':>8} {'总收益%':>10} {'年化%':>10} {'回撤%':>10} {'夏普':>8} {'止损次':>8} {'跳过次':>8}")
    print("-" * 78)
    
    best_sharpe = max(results, key=lambda x: x['sharpe']) if results else None
    best_return = max(results, key=lambda x: x['total_return']) if results else None
    best_dd = min(results, key=lambda x: x['max_drawdown']) if results else None
    
    for r in results:
        marker = ""
        if r == best_sharpe:
            marker = " ⭐夏普最优"
        if r == best_return:
            marker += " 📈收益最优"
        if r == best_dd:
            marker += " 🛡️回撤最优"
        print(f"{r['cooldown']:>8} {r['total_return']:>10.2f}{r['annual_return']:>10.2f}{r['max_drawdown']:>10.2f}{r['sharpe']:>8.2f}{r['stop_loss_count']:>8} {r['skipped_cooldown']:>8}{marker}")
    
    print("\n" + "=" * 100)
    if best_sharpe:
        print(f"\n✅ 推荐配置：冷却期 {best_sharpe['cooldown']} 天 (夏普比率最高 {best_sharpe['sharpe']:.2f})")
