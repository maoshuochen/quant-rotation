#!/usr/bin/env python3
"""
回测脚本 - Baostock 版本
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.data_fetcher_baostock import IndexDataFetcher
from src.scoring_baostock import ScoringEngine
from src.backtest_utils import (
    build_rebalance_signals,
    compute_backtest_metrics,
    create_portfolio,
    load_etf_history,
    load_strategy_config,
    select_rebalance_dates,
)

# 优化日志：仅保留 warning 及以上，减少输出噪音
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s %(message)s'
)
# 关闭第三方库的 debug 日志
logging.getLogger('akshare').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """加载配置"""
    return load_strategy_config(root_dir)


def run_backtest(start_date: str = "20250101",
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

    end_date = end_date or datetime.now().strftime('%Y%m%d')

    print("=" * 60)
    print(f"回测期间：{start_date} ~ {end_date}")
    print(f"初始资金：{initial_capital:,.0f}")
    print("=" * 60)

    # 初始化组件
    fetcher = IndexDataFetcher()
    # 使用固定权重评分引擎（避免未来函数）
    scorer = ScoringEngine(config)
    portfolio = create_portfolio(config, initial_capital=initial_capital)

    # 策略参数
    strategy = config.get('strategy', {})
    top_n = strategy.get('top_n', 5)
    buffer_n = strategy.get('buffer_n', 8)
    rebalance_freq = strategy.get('rebalance_frequency', 'weekly')

    # 指数列表
    indices = config.get('indices', [])

    # 获取所有 ETF 数据（优先使用缓存，仅获取需要的日期范围）
    print("获取 ETF 数据（优先缓存）...")
    start = "20240101" if start_date < "20250101" else start_date
    etf_data = load_etf_history(fetcher, indices, start, force_refresh=False)
    for idx in indices:
        code = idx.get("code")
        etf = idx.get("etf")
        if code in etf_data:
            print(f"  {code} ({etf}): {len(etf_data[code])} rows")

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

    print(f"调仓次数：{len(rebalance_dates)}")
    
    # 回测循环
    daily_values = []
    stop_loss_stats = {'individual': 0, 'trailing': 0, 'portfolio': 0}

    # 批量日志输出，减少 IO
    log_interval = 50  # 每 50 天输出一次进度

    for idx, date in enumerate(trade_dates):
        date_str = date.strftime('%Y-%m-%d')

        # 进度日志（降频）
        if (idx + 1) % log_interval == 0:
            print(f"进度：{idx + 1}/{len(trade_dates)} 天 ({(idx + 1) / len(trade_dates) * 100:.0f}%)")

        # 获取当日价格
        prices = {}
        for code, df in etf_data.items():
            if date in df.index:
                prices[code] = df.loc[date, 'close']

        # 检查止损（在每个交易日）
        if prices and portfolio.positions:
            stop_loss_signals = portfolio.check_stop_loss(prices, date_str)
            if any(stop_loss_signals.values()):
                for signal_type, codes in stop_loss_signals.items():
                    if codes:
                        stop_loss_stats[signal_type] += len(codes)
                names = {idx['code']: idx['name'] for idx in indices}
                portfolio.execute_stop_loss(stop_loss_signals, prices, names, date_str)

        # 记录每日净值
        if prices:
            portfolio.record_daily_value(date_str, prices)
            value = portfolio.get_portfolio_value(prices)
            daily_values.append({'date': date_str, 'value': value})

        # 调仓日运行策略
        if date in rebalance_dates and len(trade_dates) - trade_dates.index(date) > 5:
            # 计算评分（固定权重）
            scores_dict = {}
            for code, df in etf_data.items():
                hist_df = df[df.index <= date]
                if len(hist_df) >= 20:
                    scores = scorer.score_index(hist_df, benchmark_data)
                    scores_dict[code] = scores

            # 排名
            ranking = scorer.rank_indices(scores_dict)

            if ranking.empty:
                continue

            signals = build_rebalance_signals(ranking, set(portfolio.positions.keys()), top_n, buffer_n)

            # 执行（仅在有信号时输出）
            if signals['buy'] or signals['sell']:
                names = {idx['code']: idx['name'] for idx in indices}
                trades = portfolio.execute_signal(signals, prices, names, date_str)
                for trade in trades:
                    print(f"  {trade.type.upper()} {trade.code}: {trade.shares} @ {trade.price:.3f}")

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

    start = sys.argv[1] if len(sys.argv) > 1 else "20250101"
    end = sys.argv[2] if len(sys.argv) > 2 else None

    run_backtest(start, end)
