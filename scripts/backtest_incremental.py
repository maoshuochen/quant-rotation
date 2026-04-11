#!/usr/bin/env python3
"""
增量回测脚本 - 仅计算新增交易日
支持断点续跑和并行数据获取
"""
import sys
from pathlib import Path
import logging
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.data_fetcher_baostock import IndexDataFetcher
from src.scoring_baostock import ScoringEngine
from src.portfolio import SimulatedPortfolio
from src.config_loader import load_app_config

logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

RESULTS_FILE = root_dir / 'backtest_results' / 'current.parquet'
CONFIG = load_app_config(root_dir)


def get_last_trading_date() -> tuple:
    """获取最后交易日和已有数据"""
    if not RESULTS_FILE.exists():
        return None, None

    try:
        df = pd.read_parquet(RESULTS_FILE)
        if df.empty:
            return None, None

        last_date = df['date'].iloc[-1]
        last_value = df['value'].iloc[-1]
        positions = None

        # 读取持仓信息 (如果有)
        pos_file = RESULTS_FILE.with_suffix('.positions.json')
        if pos_file.exists():
            with open(pos_file) as f:
                positions = json.load(f)

        return last_date, {'value': last_value, 'positions': positions, 'history': df}

    except Exception as e:
        logger.warning(f"读取结果文件失败：{e}")
        return None, None


def fetch_single_etf(args):
    """获取单个 ETF 数据"""
    idx, fetcher, start_date = args
    code = idx['code']
    etf = idx.get('etf')

    if not etf:
        return None

    try:
        df = fetcher.fetch_etf_history(etf, start_date, force_refresh=False)
        if not df.empty:
            return (code, df)
    except Exception as e:
        logger.warning(f"获取 {code} 失败：{e}")

    return None


def fetch_etfs_parallel(indices, start_date, max_workers=5):
    """并行获取 ETF 数据"""
    fetcher = IndexDataFetcher()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        tasks = [(idx, fetcher, start_date) for idx in indices if idx.get('etf')]
        results = list(executor.map(fetch_single_etf, tasks))

    fetcher.close()
    return dict([r for r in results if r])


def run_incremental_backtest(end_date: str = None):
    """
    增量回测 - 同步更新所有数据到最新日期

    Args:
        end_date: 结束日期，默认今天
    """
    end_date = end_date or datetime.now().strftime('%Y%m%d')
    end_dt = pd.to_datetime(end_date)

    # 获取最后交易日
    last_date, cached_data = get_last_trading_date()

    if last_date:
        # 从已有数据的第二天开始
        start_date = (pd.to_datetime(last_date) + timedelta(days=1)).strftime('%Y%m%d')
        start_dt = pd.to_datetime(start_date)

        # 检查是否需要更新
        if start_dt > end_dt:
            print("无需更新，已是最新数据")
            return

        print(f"增量回测：{start_date} ~ {end_date}")
        print(f"已有数据：{cached_data['history']['date'].iloc[-1] if 'date' in cached_data['history'].columns else cached_data['history'].iloc[-1]['date']}")

        # 恢复投资组合状态
        last_value = cached_data['value']
        portfolio = SimulatedPortfolio(
            initial_capital=CONFIG.get('initial_capital', 1_000_000),
            commission_rate=CONFIG.get('portfolio', {}).get('commission', 0.0003),
            slippage=CONFIG.get('portfolio', {}).get('slippage', 0.001),
            stop_loss_config=CONFIG.get('stop_loss'),
            cooldown_days=CONFIG.get('stop_loss', {}).get('cooldown_days', 5)
        )

        # 恢复持仓
        if cached_data['positions']:
            from src.portfolio import Position
            for pos_data in cached_data['positions']:
                portfolio.positions[pos_data['code']] = Position(**pos_data)
            print(f"恢复持仓：{len(portfolio.positions)} 只股票")

        # 历史数据用于计算指标（需要完整历史，不仅仅是不止日期）
        history_df = cached_data['history'].copy()
        if 'date' in history_df.columns:
            history_df['date'] = pd.to_datetime(history_df['date'])
            history_df = history_df.set_index('date')
        daily_values = list(cached_data['history'].to_dict('records'))

    else:
        # 全量回测
        start_date = CONFIG.get('backtest_start_date', '20240101')
        start_dt = pd.to_datetime(start_date)
        print(f"全量回测：{start_date} ~ {end_date}")

        portfolio = SimulatedPortfolio(
            initial_capital=CONFIG.get('initial_capital', 1_000_000),
            commission_rate=CONFIG.get('portfolio', {}).get('commission', 0.0003),
            slippage=CONFIG.get('portfolio', {}).get('slippage', 0.001),
            stop_loss_config=CONFIG.get('stop_loss'),
            cooldown_days=CONFIG.get('stop_loss', {}).get('cooldown_days', 5)
        )
        daily_values = []
        history_df = None

    # 获取 ETF 数据 - 从最初开始，确保有足够历史计算指标
    data_start = "20240101"
    print(f"获取 ETF 数据（从 {data_start} 开始）...")
    etf_data = fetch_etfs_parallel(CONFIG.get('indices', []), data_start)

    if not etf_data:
        print("没有获取到数据!")
        return

    # 如果是增量回测且有持仓，需要恢复现金状态
    # 现金 = 最后交易日净值 - 持仓市值（使用最后交易日价格计算）
    if last_date and cached_data['positions']:
        last_date_str = pd.to_datetime(last_date).strftime('%Y-%m-%d')
        last_value = cached_data['value']

        # 获取最后交易日的价格
        last_prices = {}
        for code, df in etf_data.items():
            if last_date_str in df.index:
                last_prices[code] = df.loc[last_date_str, 'close']

        # 计算持仓市值
        stock_value = 0
        for pos_data in cached_data['positions']:
            code = pos_data['code']
            if code in last_prices:
                stock_value += pos_data['shares'] * last_prices[code]

        # 恢复现金：最后净值 - 持仓市值
        portfolio.cash = last_value - stock_value

        # 验证：现金不应该为负数（除非有杠杆或做空）
        if portfolio.cash < 0:
            print(f"⚠️ 警告：现金为负数！cash={portfolio.cash:,.2f}")
            print(f"   净值={last_value:,.2f}, 持仓市值={stock_value:,.2f}")

        # 验证：恢复后的总资产应该等于最后净值
        restored_value = portfolio.cash + stock_value
        if abs(restored_value - last_value) > 0.01:
            print(f"⚠️ 警告：恢复后资产与最后净值不一致！")
            print(f"   恢复后={restored_value:,.2f}, 最后净值={last_value:,.2f}, 差异={restored_value - last_value:,.2f}")

        print(f"恢复组合状态：净值={last_value:,.2f}, 持仓市值={stock_value:,.2f}, 现金={portfolio.cash:,.2f}")

    # 获取基准数据
    benchmark_data = etf_data.get('000300.SH', pd.DataFrame())

    # 生成交易日期
    first_df = list(etf_data.values())[0]
    all_dates = first_df.index.tolist()
    trade_dates = [d for d in all_dates if start_dt <= d <= end_dt]

    if not trade_dates:
        print("没有交易日期!")
        return

    # 确定调仓日期
    rebalance_dates = []
    for date in trade_dates:
        if date.weekday() == 0:  # 周一调仓
            rebalance_dates.append(date)

    # 初始化评分引擎
    scorer = ScoringEngine(CONFIG)
    top_n = CONFIG.get('strategy', {}).get('top_n', 5)
    buffer_n = CONFIG.get('strategy', {}).get('buffer_n', 8)

    names = {idx['code']: idx['name'] for idx in CONFIG.get('indices', []) if idx.get('code')}

    print(f"交易日数：{len(trade_dates)}, 调仓次数：{len(rebalance_dates)}")

    # 回测循环
    for idx, date in enumerate(trade_dates):
        date_str = date.strftime('%Y-%m-%d')

        # 获取价格
        prices = {code: df.loc[date, 'close'] for code, df in etf_data.items() if date in df.index}

        if not prices:
            continue

        # 检查止损
        if portfolio.positions:
            stop_loss_signals = portfolio.check_stop_loss(prices, date_str)
            if any(stop_loss_signals.values()):
                portfolio.execute_stop_loss(stop_loss_signals, prices, names, date_str)

        # 记录净值
        portfolio.record_daily_value(date_str, prices)
        value = portfolio.get_portfolio_value(prices)
        daily_values.append({'date': date_str, 'value': value})

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

            signals = {
                'buy': [c for c in selected if c not in current_codes],
                'sell': [c for c in current_codes if c not in hold_range]
            }

            if signals['buy'] or signals['sell']:
                portfolio.execute_signal(signals, prices, names, date_str)

        # 进度日志
        if (idx + 1) % 50 == 0:
            print(f"进度：{idx + 1}/{len(trade_dates)} ({(idx + 1) / len(trade_dates) * 100:.0f}%)")

    # 保存结果
    print("\n保存结果...")
    results_dir = root_dir / 'backtest_results'
    results_dir.mkdir(exist_ok=True)

    # 合并历史数据
    if cached_data and cached_data['history'] is not None:
        all_values = pd.concat([
            cached_data['history'],
            pd.DataFrame(daily_values)
        ]).drop_duplicates(subset=['date'], keep='last')
    else:
        all_values = pd.DataFrame(daily_values)

    # 保存为 Parquet
    all_values.to_parquet(RESULTS_FILE, compression='snappy', index=False)

    # 保存持仓状态
    pos_file = RESULTS_FILE.with_suffix('.positions.json')
    positions_data = []
    for pos in portfolio.positions.values():
        positions_data.append({
            'code': pos.code,
            'name': pos.name,
            'shares': pos.shares,
            'avg_price': pos.avg_price,
            'entry_date': pos.entry_date,
            'highest_price': pos.highest_price,
            'stop_loss_triggered': pos.stop_loss_triggered
        })

    with open(pos_file, 'w') as f:
        json.dump(positions_data, f, indent=2)

    # 输出摘要
    final_value = all_values['value'].iloc[-1]
    total_return = (final_value - all_values['value'].iloc[0]) / all_values['value'].iloc[0] if len(all_values) > 1 else 0

    print(f"\n✅ 回测完成")
    print(f"最终价值：{final_value:,.0f}")
    print(f"区间收益：{total_return * 100:.2f}%")
    print(f"持仓数：{len(portfolio.positions)}")
    print(f"结果文件：{RESULTS_FILE}")


if __name__ == "__main__":
    end = sys.argv[1] if len(sys.argv) > 1 else None
    run_incremental_backtest(end)
