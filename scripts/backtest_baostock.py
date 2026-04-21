#!/usr/bin/env python3
"""
回测脚本 - Baostock 版本
"""
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.data_fetcher_baostock import IndexDataFetcher
from src.backtest_utils import (
    build_rebalance_signals,
    compute_fetch_start_date,
    compute_backtest_metrics,
    create_portfolio,
    load_etf_history,
    load_strategy_config,
    resolve_backtest_start_date,
    select_rebalance_dates,
    validate_etf_history_coverage,
)
from src.scoring_factory import create_scoring_engine, resolve_scoring_mode

# 优化日志：仅保留 warning 及以上，减少输出噪音
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s %(message)s'
)
# 关闭第三方库的 debug 日志
logging.getLogger('akshare').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('src.portfolio').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """加载配置"""
    return load_strategy_config(root_dir)


def run_backtest(start_date: str = None,
                 end_date: str = None,
                 initial_capital: float = 1_000_000):
    """
    运行回测

    Args:
        start_date: 开始日期
        end_date: 结束日期
        initial_capital: 初始资金
    """
    config = load_config()
    start_date = resolve_backtest_start_date(config, start_date)

    end_date = end_date or datetime.now().strftime('%Y%m%d')

    print("=" * 60)
    print(f"回测期间：{start_date} ~ {end_date}")
    print(f"初始资金：{initial_capital:,.0f}")
    print("=" * 60)

    # 初始化组件
    fetcher = IndexDataFetcher()
    scorer = create_scoring_engine(config)
    scoring_mode = resolve_scoring_mode(config)
    portfolio = create_portfolio(config, initial_capital=initial_capital)

    # 策略参数
    strategy = config.get('strategy', {})
    backtest_config = config.get('backtest', {})
    top_n = strategy.get('top_n', 5)
    buffer_n = strategy.get('buffer_n', 8)
    rebalance_freq = strategy.get('rebalance_frequency', 'weekly')
    strict_weekly_execution = bool(strategy.get('strict_weekly_execution', False))
    warmup_days = int(backtest_config.get('warmup_days', 370))
    progress_interval = int(backtest_config.get('progress_interval', 100))
    verbose_trades = bool(backtest_config.get('verbose_trades', False))
    score_workers = max(1, int(backtest_config.get('score_workers', 1)))
    required_price_mode = str(config.get("data", {}).get("etf_price_mode", "continuous") or "")
    require_consistent_adjust = bool(config.get("data", {}).get("require_consistent_adjust", True))

    # 指数列表
    indices = config.get('indices', [])
    code_to_name = {idx['code']: idx['name'] for idx in indices}

    # 获取所有 ETF 数据（优先使用缓存，并预留足够 warmup 供因子计算）
    print("获取 ETF 数据（优先缓存）...")
    fetch_start = compute_fetch_start_date(start_date, warmup_days)
    etf_data = load_etf_history(fetcher, indices, fetch_start, force_refresh=False)
    for idx in indices:
        code = idx.get("code")
        etf = idx.get("etf")
        if code in etf_data:
            print(f"  {code} ({etf}): {len(etf_data[code])} rows")

    coverage_issues = validate_etf_history_coverage(
        etf_data,
        indices,
        start_date,
        required_price_mode=required_price_mode if require_consistent_adjust and required_price_mode else None,
    )
    if coverage_issues:
        print("ETF 数据覆盖不完整，已终止回测：")
        for issue in coverage_issues:
            print(f"  - {issue}")
        fetcher.close()
        return

    if not etf_data:
        print("没有获取到任何数据!")
        return

    # 基准数据
    benchmark_data = etf_data.get('000300.SH', pd.DataFrame())

    # 生成交易日期
    first_df = list(etf_data.values())[0]
    all_dates = first_df.index.tolist()

    # 筛选日期范围
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    trade_dates = [d for d in all_dates if start_dt <= d <= end_dt]

    if not trade_dates:
        print("没有交易日期!")
        return

    print(f"交易日期数：{len(trade_dates)}")

    # 确定调仓日期
    rebalance_dates = select_rebalance_dates(trade_dates, rebalance_freq)
    rebalance_set = set(rebalance_dates)
    last_rebalance_date = trade_dates[-6] if len(trade_dates) > 5 else trade_dates[-1]
    history_window = max(252, int(strategy.get('momentum_window', 126)) * 2)

    print(f"调仓次数：{len(rebalance_dates)}")

    close_matrix = pd.DataFrame(
        {code: df["close"].reindex(trade_dates) for code, df in etf_data.items()},
        index=trade_dates,
    )
    open_matrix = pd.DataFrame(
        {code: df["open"].reindex(trade_dates) for code, df in etf_data.items()},
        index=trade_dates,
    )
    
    # 回测循环
    daily_values = []
    stop_loss_stats = {'individual': 0, 'trailing': 0, 'portfolio': 0}
    pending_signals = None

    def score_candidate(item, date, benchmark_slice, dynamic_weights):
        code, df = item
        end_pos = df.index.searchsorted(date, side="right")
        hist_df = df.iloc[max(0, end_pos - history_window):end_pos]
        if len(hist_df) < 20:
            return None
        return code, scorer.score_index(hist_df, benchmark_slice, dynamic_weights=dynamic_weights)

    executor = ThreadPoolExecutor(max_workers=score_workers) if score_workers > 1 else None
    try:
        for idx, date in enumerate(trade_dates):
            date_str = date.strftime('%Y-%m-%d')

            # 进度日志（降频）
            if progress_interval > 0 and (idx + 1) % progress_interval == 0:
                print(f"进度：{idx + 1}/{len(trade_dates)} 天 ({(idx + 1) / len(trade_dates) * 100:.0f}%)")

            # 先用前一交易日收盘生成的信号，在今日开盘执行。
            open_row = open_matrix.loc[date].dropna()
            open_prices = {code: float(price) for code, price in open_row.items()}
            if pending_signals and open_prices:
                trades = portfolio.execute_signal(pending_signals, open_prices, code_to_name, date_str)
                if verbose_trades:
                    for trade in trades:
                        print(f"  {trade.type.upper()} {trade.code}: {trade.shares} @ {trade.price:.3f}")
                pending_signals = None

            # 获取当日收盘价格
            price_row = close_matrix.loc[date].dropna()
            prices = {code: float(price) for code, price in price_row.items()}

            # 检查止损（在每个交易日）
            if prices and portfolio.positions and (not strict_weekly_execution or date in rebalance_set):
                stop_loss_signals = portfolio.check_stop_loss(prices, date_str)
                if any(stop_loss_signals.values()):
                    for signal_type, codes in stop_loss_signals.items():
                        if codes:
                            stop_loss_stats[signal_type] += len(codes)
                    portfolio.execute_stop_loss(stop_loss_signals, prices, code_to_name, date_str)

            # 记录每日净值
            if prices:
                portfolio.record_daily_value(date_str, prices)
                value = portfolio.get_portfolio_value(prices)
                daily_values.append({'date': date_str, 'value': value})

            # 调仓日运行策略
            if date in rebalance_set and date <= last_rebalance_date:
                # 计算评分（固定权重）
                scores_dict = {}
                benchmark_slice = benchmark_data
                dynamic_weights = None
                if not benchmark_data.empty:
                    bench_end_pos = benchmark_data.index.searchsorted(date, side="right")
                    benchmark_slice = benchmark_data.iloc[max(0, bench_end_pos - history_window):bench_end_pos]
                    if (
                        scoring_mode == "dynamic"
                        and hasattr(scorer, "update_market_regime")
                        and not benchmark_slice.empty
                    ):
                        scorer.update_market_regime(benchmark_slice["close"])
                        dynamic_weights = getattr(scorer, "current_weights", None)
                if executor is not None:
                    for result in executor.map(lambda item: score_candidate(item, date, benchmark_slice, dynamic_weights), etf_data.items()):
                        if result is None:
                            continue
                        code, scores = result
                        scores_dict[code] = scores
                else:
                    for item in etf_data.items():
                        result = score_candidate(item, date, benchmark_slice, dynamic_weights)
                        if result is None:
                            continue
                        code, scores = result
                        scores_dict[code] = scores

                # 排名
                ranking = scorer.rank_indices(scores_dict)

                if ranking.empty:
                    continue

                signals = build_rebalance_signals(ranking, set(portfolio.positions.keys()), top_n, buffer_n)

                # 调仓信号延迟到下一交易日开盘执行，避免同收盘信号同收盘成交。
                if signals['buy'] or signals['sell']:
                    pending_signals = signals
    finally:
        if executor is not None:
            executor.shutdown(wait=True)

    # 回测结果
    print("\n" + "=" * 60)
    print("回测完成")
    print("=" * 60)
    
    # 计算统计
    values_df = compute_backtest_metrics(pd.DataFrame(daily_values), initial_capital)
    summary = values_df.attrs["summary"]
    final_value = summary["final_value"]
    total_return = summary["total_return"]
    annual_return = summary["annual_return"]
    max_drawdown = summary["max_drawdown"]
    sharpe = summary["sharpe"]

    # 输出结果（精简版）
    print(f"\n📊 回测结果")
    print(f"  初始资金：{initial_capital:,.0f}")
    print(f"  最终价值：{final_value:,.0f}")
    print(f"  总收益率：{total_return*100:.2f}%")
    print(f"  年化收益：{annual_return*100:.2f}%")
    print(f"  最大回撤：{max_drawdown*100:.2f}%")
    print(f"  夏普比率：{sharpe:.2f}")
    print(f"  交易天数：{len(values_df)}")
    print(f"  调仓次数：{len(rebalance_dates)}")

    # 止损统计（仅在有触发时输出）
    total_stop_loss = sum(stop_loss_stats.values())
    if total_stop_loss > 0:
        print(f"\n🛡️ 止损统计")
        print(f"  个体止损：{stop_loss_stats['individual']} 次")
        print(f"  移动止损：{stop_loss_stats['trailing']} 次")
        print(f"  组合止损：{stop_loss_stats['portfolio']} 次")
        print(f"  总计：{total_stop_loss} 次")

    # 保存结果
    results_dir = root_dir / 'backtest_results'
    results_dir.mkdir(exist_ok=True)

    # 保存 CSV
    result_file = results_dir / f'backtest_{start_date}_{end_date}.csv'
    values_df.to_csv(result_file, index=False)
    logger.warning(f"\n结果已保存：{result_file}")

    # 更新 current.parquet（供增量回测和前端使用）
    current_file = results_dir / 'current.parquet'
    values_df.to_parquet(current_file, compression='snappy', index=False)
    logger.warning(f"current.parquet 已更新")

    # 清理
    fetcher.close()


if __name__ == "__main__":
    import sys

    start = sys.argv[1] if len(sys.argv) > 1 else None
    end = sys.argv[2] if len(sys.argv) > 2 else None

    run_backtest(start, end)
