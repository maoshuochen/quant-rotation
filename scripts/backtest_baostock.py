#!/usr/bin/env python3
"""
回测脚本 - Baostock 版本
"""
from __future__ import annotations

import logging
import sys
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.data_fetcher_baostock import IndexDataFetcher
from src.backtest_utils import (
    build_rebalance_signals,
    build_target_weights,
    build_rebalance_targets,
    compute_fetch_start_date,
    compute_backtest_metrics,
    create_portfolio,
    load_etf_history,
    load_strategy_config,
    resolve_backtest_start_date,
    select_rebalance_dates,
    validate_etf_history_coverage,
)
from src.scoring_factory import create_scoring_engine
from src.provenance import build_run_metadata

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


def _clip01(frame: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    return frame.clip(lower=0.0, upper=1.0)


def _relative_strength_benchmark(config: dict) -> str:
    return str(
        config.get("price_strength_model", {}).get(
            "relative_strength_benchmark",
            config.get("alpha_optimization", {}).get("relative_strength_benchmark", "hs300"),
        )
    )


def _overheat_config(config: dict) -> dict:
    return (
        config.get("price_strength_model", {}).get("overheat")
        or config.get("alpha_optimization", {}).get("overheat_penalty", {})
    )


def _flow_trend_filter_config(config: dict | None) -> dict:
    config = config or {}
    return (
        config.get("flow_model", {}).get("trend_filter")
        or config.get("alpha_optimization", {}).get("conditional_flow", {})
    )


def _price_strength_component_weights(config: dict) -> dict:
    configured = config.get("price_strength_model", {}).get("components")
    if configured:
        weights = {
            "momentum": max(float(configured.get("momentum", 0.0)), 0.0),
            "relative_strength": max(float(configured.get("relative_strength", 0.0)), 0.0),
            "trend": max(float(configured.get("trend", 0.0)), 0.0),
        }
    else:
        strength_blend = config.get('strength_blend', {})
        momentum_weight = max(float(strength_blend.get('momentum', 0.5)), 0.0)
        rs_weight = max(float(strength_blend.get('relative_strength', 0.5)), 0.0)
        blend_total = momentum_weight + rs_weight
        if blend_total <= 0:
            momentum_weight = rs_weight = 0.5
            blend_total = 1.0
        price_strength_blend = config.get('price_strength_blend', {})
        strength_weight = max(float(price_strength_blend.get('strength', 0.235)), 0.0)
        trend_weight = max(float(price_strength_blend.get('trend', 0.18)), 0.0)
        weights = {
            "momentum": strength_weight * momentum_weight / blend_total,
            "relative_strength": strength_weight * rs_weight / blend_total,
            "trend": trend_weight,
        }
    total = sum(weights.values())
    if total <= 0:
        return {"momentum": 1 / 3, "relative_strength": 1 / 3, "trend": 1 / 3}
    return {key: value / total for key, value in weights.items()}


def _score_trend_matrix(close_matrix: pd.DataFrame, trend_weights: dict) -> pd.DataFrame:
    ma20 = close_matrix.rolling(20).mean()
    ma60 = close_matrix.rolling(60).mean()

    price_vs_ma20 = (close_matrix - ma20) / ma20
    price_vs_ma60 = (close_matrix - ma60) / ma60
    ma20_vs_ma60 = (ma20 - ma60) / ma60
    ma20_slope = (ma20 - ma20.shift(10)) / ma20.shift(10)

    total = sum(max(float(weight), 0.0) for weight in trend_weights.values())
    if total <= 0:
        trend_weights = {
            'price_vs_ma20': 0.40,
            'price_vs_ma60': 0.35,
            'ma20_vs_ma60': 0.20,
            'ma20_slope': 0.05,
        }
        total = 1.0
    weights = {key: max(float(value), 0.0) / total for key, value in trend_weights.items()}

    components = {
        'price_vs_ma20': _clip01(0.5 + price_vs_ma20 / (2 * 0.08)),
        'price_vs_ma60': _clip01(0.5 + price_vs_ma60 / (2 * 0.12)),
        'ma20_vs_ma60': _clip01(0.5 + ma20_vs_ma60 / (2 * 0.10)),
        'ma20_slope': _clip01(0.5 + ma20_slope / (2 * 0.05)),
    }
    trend = sum(components[key] * weights[key] for key in weights)
    return trend.where(close_matrix.notna()).fillna(0.5)


def _overheat_penalty_matrix(close_matrix: pd.DataFrame, config: dict) -> pd.DataFrame:
    penalty_config = _overheat_config(config)
    if not penalty_config.get("enabled", False):
        return pd.DataFrame(0.0, index=close_matrix.index, columns=close_matrix.columns)

    ma20 = close_matrix.rolling(20).mean()
    ma60 = close_matrix.rolling(60).mean()
    price_vs_ma20 = (close_matrix - ma20) / ma20
    price_vs_ma60 = (close_matrix - ma60) / ma60
    recent_return = close_matrix / close_matrix.shift(20) - 1

    ma20_threshold = float(penalty_config.get("ma20_threshold", 0.10))
    ma60_threshold = float(penalty_config.get("ma60_threshold", 0.18))
    strength = float(penalty_config.get("penalty_strength", 0.20))

    ma20_hot = ((price_vs_ma20 - ma20_threshold) / max(ma20_threshold, 1e-6)).clip(lower=0, upper=1)
    ma60_hot = ((price_vs_ma60 - ma60_threshold) / max(ma60_threshold, 1e-6)).clip(lower=0, upper=1)
    short_hot = ((recent_return - ma20_threshold) / max(ma20_threshold, 1e-6)).clip(lower=0, upper=1)
    penalty = (ma20_hot * 0.4 + ma60_hot * 0.4 + short_hot * 0.2) * strength
    return penalty.where(close_matrix.notna()).fillna(0.0)


def _score_flow_matrix(
    close_matrix: pd.DataFrame,
    volume_matrix: pd.DataFrame,
    amount_matrix: pd.DataFrame,
    flow_weights: dict,
    history_window: int,
    config: dict | None = None,
) -> pd.DataFrame:
    total = sum(max(float(weight), 0.0) for weight in flow_weights.values())
    if total <= 0:
        flow_weights = {
            'volume_trend': 0.25,
            'price_volume_corr': 0.25,
            'amount_trend': 0.25,
            'flow_intensity': 0.25,
        }
        total = 1.0
    weights = {key: max(float(value), 0.0) / total for key, value in flow_weights.items()}

    recent_vol = volume_matrix.rolling(20).mean()
    prev_vol = volume_matrix.shift(20).rolling(20).mean()
    vol_score = _clip01(0.5 + (recent_vol - prev_vol) / prev_vol)

    return_window = max(history_window - 1, 20)
    price_returns = close_matrix.pct_change()
    vol_returns = volume_matrix.pct_change()
    corr = price_returns.rolling(return_window, min_periods=20).corr(vol_returns)
    corr_score = _clip01(0.5 + corr.fillna(0) * 0.5)

    recent_amt = amount_matrix.rolling(20).mean()
    prev_amt = amount_matrix.shift(20).rolling(20).mean()
    amt_score = _clip01(0.5 + (recent_amt - prev_amt) / prev_amt)
    amt_score = amt_score.where(amount_matrix.notna(), vol_score)

    vol_median = volume_matrix.rolling(60).median()
    intensity = (volume_matrix > vol_median).rolling(20).sum() / 20

    flow = (
        vol_score * weights['volume_trend']
        + corr_score * weights['price_volume_corr']
        + amt_score * weights['amount_trend']
        + intensity * weights['flow_intensity']
    )
    conditional_config = _flow_trend_filter_config(config)
    if conditional_config.get("enabled", False):
        ma20 = close_matrix.rolling(20).mean()
        ma60 = close_matrix.rolling(60).mean()
        uptrend = (close_matrix > ma20) & (ma20 > ma60)
        weak_trend = (close_matrix > ma20) & ~uptrend
        downtrend_cap = float(conditional_config.get("downtrend_cap", 0.50))
        weak_multiplier = float(conditional_config.get("weak_trend_multiplier", 0.50))
        neutral = pd.DataFrame(0.5, index=flow.index, columns=flow.columns)
        weak_flow = neutral + (flow - neutral) * weak_multiplier
        down_flow = flow.clip(upper=downtrend_cap)
        flow = flow.where(uptrend, weak_flow.where(weak_trend, down_flow))
    return flow.where(close_matrix.notna()).fillna(0.5)


def _score_relative_strength_matrix(
    close_matrix: pd.DataFrame,
    benchmark_close: pd.Series,
) -> pd.DataFrame:
    benchmark = benchmark_close.reindex(close_matrix.index)
    score = pd.DataFrame(0.5, index=close_matrix.index, columns=close_matrix.columns)

    for lookback in (10, 20, 60):
        index_return = close_matrix / close_matrix.shift(lookback) - 1
        benchmark_return = benchmark / benchmark.shift(lookback) - 1
        lookback_score = _clip01(0.5 + index_return.sub(benchmark_return, axis=0))
        score = score.where(lookback_score.isna(), lookback_score)

    return score.where(close_matrix.notna()).fillna(0.5)


def _build_vectorized_score_frames(
    config: dict,
    close_matrix: pd.DataFrame,
    volume_matrix: pd.DataFrame,
    amount_matrix: pd.DataFrame,
    benchmark_data: pd.DataFrame,
    history_window: int,
) -> dict[str, pd.DataFrame]:
    returns = close_matrix.pct_change()
    momentum = _clip01(0.5 + returns.rolling(126, min_periods=126).sum()).fillna(0.5)
    trend = _score_trend_matrix(close_matrix, config.get('trend_subfactor_weights', {}))
    flow = _score_flow_matrix(
        close_matrix,
        volume_matrix,
        amount_matrix,
        config.get('flow_subfactor_weights', {}),
        history_window,
        config,
    )

    rs_benchmark = _relative_strength_benchmark(config)
    if rs_benchmark == "equal_weight_all":
        benchmark_close = (1 + close_matrix.ffill().pct_change().fillna(0).mean(axis=1)).cumprod()
        relative_strength = _score_relative_strength_matrix(close_matrix, benchmark_close)
    elif benchmark_data.empty or 'close' not in benchmark_data.columns:
        relative_strength = pd.DataFrame(
            0.5,
            index=close_matrix.index,
            columns=close_matrix.columns,
        )
    else:
        relative_strength = _score_relative_strength_matrix(close_matrix, benchmark_data['close'])

    overheat_penalty = _overheat_penalty_matrix(close_matrix, config)
    component_weights = _price_strength_component_weights(config)
    strength_weight_total = component_weights["momentum"] + component_weights["relative_strength"]
    if strength_weight_total > 0:
        strength = (
            momentum * component_weights["momentum"]
            + relative_strength * component_weights["relative_strength"]
        ) / strength_weight_total
        strength = (strength - overheat_penalty).clip(lower=0.0, upper=1.0)
    else:
        strength = (momentum + relative_strength) / 2
    momentum = (momentum - overheat_penalty).clip(lower=0.0, upper=1.0)
    price_strength = (
        strength * strength_weight_total
        + trend * component_weights["trend"]
    )

    volatility = _clip01(
        1.0
        - (returns.rolling(max(history_window - 1, 20), min_periods=20).std() * np.sqrt(252) - 0.1)
        / 0.3
    ).fillna(0.5)

    return {
        'momentum': momentum,
        'relative_strength': relative_strength,
        'strength': strength,
        'price_strength': price_strength,
        'trend': trend,
        'flow': flow,
        'volatility': volatility,
    }


def _rank_from_score_frames(
    scorer,
    score_frames: dict[str, pd.DataFrame],
    date: pd.Timestamp,
    active_factors: list[str],
    weights: dict,
) -> pd.DataFrame:
    scores_dict = {}
    weight_sum = sum(float(weights.get(factor, 0.0)) for factor in active_factors)
    if weight_sum <= 0:
        weight_sum = 1.0

    for code in score_frames['strength'].columns:
        scores = {}
        total = 0.0
        for factor in active_factors:
            frame = score_frames.get(factor)
            value = 0.5 if frame is None else frame.at[date, code]
            if pd.isna(value):
                value = 0.5
            scores[factor] = float(value)
            total += scores[factor] * float(weights.get(factor, 0.0))
        scores['total_score'] = total / weight_sum
        scores_dict[code] = scores

    return scorer.rank_indices(scores_dict)


def _compute_benchmark_curves(
    close_matrix: pd.DataFrame,
    initial_capital: float,
    strategy_values: pd.DataFrame,
) -> tuple[list[dict], dict]:
    benchmark = close_matrix.copy().ffill()
    dates = pd.to_datetime(strategy_values["date"])
    benchmark = benchmark.reindex(dates).dropna(axis=1, how="any")
    benchmarks: dict[str, pd.Series] = {}
    if not benchmark.empty:
        returns = benchmark.pct_change().fillna(0)
        benchmarks["equal_weight_all"] = (1 + returns.mean(axis=1)).cumprod() * initial_capital
    if "000300.SH" in benchmark:
        benchmarks["hs300"] = benchmark["000300.SH"] / benchmark["000300.SH"].iloc[0] * initial_capital

    chart_data = []
    strategy_series = pd.Series(strategy_values["value"].values, index=dates)
    for date in dates:
        item = {
            "date": date.strftime("%Y-%m-%d"),
            "strategy": round(float(strategy_series.loc[date] / initial_capital - 1), 4),
        }
        for key, series in benchmarks.items():
            item[key] = round(float(series.loc[date] / initial_capital - 1), 4)
        chart_data.append(item)

    summary = {}
    for key, series in benchmarks.items():
        metrics = compute_backtest_metrics(
            pd.DataFrame({"date": series.index, "value": series.values}),
            initial_capital,
        ).attrs["summary"]
        summary[key] = {
            "final_value": round(float(metrics["final_value"]), 2),
            "total_return": round(float(metrics["total_return"]), 4),
            "annual_return": round(float(metrics["annual_return"]), 4),
            "max_drawdown": round(float(metrics["max_drawdown"]), 4),
            "sharpe_ratio": round(float(metrics["sharpe"]), 2),
        }
    return chart_data, summary


def load_config() -> dict:
    """加载配置"""
    return load_strategy_config(root_dir)


def run_backtest(start_date: str = None,
                 end_date: str = None,
                 initial_capital: float = 1_000_000,
                 config_override: dict | None = None,
                 write_outputs: bool = True):
    """
    运行回测

    Args:
        start_date: 开始日期
        end_date: 结束日期
        initial_capital: 初始资金
    """
    config = config_override or load_config()
    start_date = resolve_backtest_start_date(config, start_date)

    end_date = end_date or datetime.now().strftime('%Y%m%d')

    print("=" * 60)
    print(f"回测期间：{start_date} ~ {end_date}")
    print(f"初始资金：{initial_capital:,.0f}")
    print("=" * 60)

    # 初始化组件
    fetcher = IndexDataFetcher()
    scorer = create_scoring_engine(config)
    portfolio = create_portfolio(config, initial_capital=initial_capital)

    # 策略参数
    strategy = config.get('strategy', {})
    backtest_config = config.get('backtest', {})
    top_n = strategy.get('top_n', 5)
    buffer_n = strategy.get('buffer_n', 8)
    rebalance_freq = strategy.get('rebalance_frequency', 'weekly')
    strict_weekly_execution = bool(strategy.get('strict_weekly_execution', False))
    active_factors = list(
        config.get('factor_model', {}).get('active_factors', ['strength', 'trend', 'flow'])
    )
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
    etf_data = load_etf_history(
        fetcher,
        indices,
        fetch_start,
        force_refresh=False,
        allow_stale_cache=True,
    )
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
    volume_matrix = pd.DataFrame(
        {code: df["volume"].reindex(trade_dates) for code, df in etf_data.items()},
        index=trade_dates,
    )
    amount_matrix = pd.DataFrame(
        {code: df["amount"].reindex(trade_dates) for code, df in etf_data.items()},
        index=trade_dates,
    )
    supported_vector_factors = {
        'momentum',
        'relative_strength',
        'strength',
        'price_strength',
        'trend',
        'flow',
        'volatility',
    }
    use_vectorized_scoring = set(active_factors).issubset(supported_vector_factors)
    score_frames = {}
    if use_vectorized_scoring:
        print("预计算调仓评分因子...")
        score_frames = _build_vectorized_score_frames(
            config,
            close_matrix,
            volume_matrix,
            amount_matrix,
            benchmark_data,
            history_window,
        )
    else:
        print(f"检测到非矩阵化因子 {active_factors}，回退逐标的评分。")
    
    # 回测循环
    daily_values = []
    stop_loss_stats = {'individual': 0, 'trailing': 0, 'portfolio': 0}
    pending_signals = None
    pending_stop_loss_signals = None

    def score_candidate(item, date, benchmark_slice):
        code, df = item
        end_pos = df.index.searchsorted(date, side="right")
        hist_df = df.iloc[max(0, end_pos - history_window):end_pos]
        if len(hist_df) < 20:
            return None
        return code, scorer.score_index(hist_df, benchmark_slice)

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
            if pending_stop_loss_signals and open_prices:
                trades = portfolio.execute_stop_loss(pending_stop_loss_signals, open_prices, code_to_name, date_str)
                if verbose_trades:
                    for trade in trades:
                        print(f"  STOP {trade.code}: {trade.shares} @ {trade.price:.3f}")
                pending_stop_loss_signals = None
            if pending_signals and open_prices:
                target_weights = pending_signals.get("target_weights")
                if target_weights:
                    trades = portfolio.execute_rebalance_weights(target_weights, open_prices, code_to_name, date_str)
                else:
                    trades = portfolio.execute_rebalance(pending_signals["target"], open_prices, code_to_name, date_str)
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
                    pending_stop_loss_signals = stop_loss_signals

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
                if not benchmark_data.empty:
                    bench_end_pos = benchmark_data.index.searchsorted(date, side="right")
                    benchmark_slice = benchmark_data.iloc[max(0, bench_end_pos - history_window):bench_end_pos]
                if use_vectorized_scoring:
                    ranking = _rank_from_score_frames(
                        scorer,
                        score_frames,
                        date,
                        active_factors,
                        scorer.weights,
                    )
                elif executor is not None:
                    for result in executor.map(lambda item: score_candidate(item, date, benchmark_slice), etf_data.items()):
                        if result is None:
                            continue
                        code, scores = result
                        scores_dict[code] = scores
                    ranking = scorer.rank_indices(scores_dict)
                else:
                    for item in etf_data.items():
                        result = score_candidate(item, date, benchmark_slice)
                        if result is None:
                            continue
                        code, scores = result
                        scores_dict[code] = scores
                    ranking = scorer.rank_indices(scores_dict)

                if ranking.empty:
                    continue

                signals = build_rebalance_signals(ranking, set(portfolio.positions.keys()), top_n, buffer_n)
                target_codes = build_rebalance_targets(ranking, set(portfolio.positions.keys()), top_n, buffer_n)

                # 调仓信号延迟到下一交易日开盘执行，避免同收盘信号同收盘成交。
                if target_codes:
                    signals["target"] = target_codes
                    signals["target_weights"] = build_target_weights(
                        ranking,
                        target_codes,
                        config.get("alpha_optimization", {}).get("target_weighting", {}),
                    )
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
    values_df.attrs["close_matrix"] = close_matrix
    benchmark_chart_data, benchmark_summary = _compute_benchmark_curves(close_matrix, initial_capital, values_df)
    values_df.attrs["benchmark_chart_data"] = benchmark_chart_data
    values_df.attrs["benchmark_summary"] = benchmark_summary
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

    if not write_outputs:
        fetcher.close()
        return values_df

    # 保存结果
    results_dir = root_dir / 'backtest_results'
    results_dir.mkdir(exist_ok=True)

    # 保存 CSV
    result_file = results_dir / f'backtest_{start_date}_{end_date}.csv'
    values_df.to_csv(result_file, index=False)
    logger.warning(f"\n结果已保存：{result_file}")

    # 更新 current.parquet（供增量回测和前端使用）
    current_file = results_dir / 'current.parquet'
    values_to_save = values_df.copy()
    values_to_save.attrs = {}
    values_to_save.to_parquet(current_file, compression='snappy', index=False)
    logger.warning(f"current.parquet 已更新")

    metadata = build_run_metadata(
        root_dir=root_dir,
        config=config,
        source="scripts/backtest_baostock.py",
        requested_start=start_date,
        requested_end=end_date,
        actual_start=values_df["date"].iloc[0].strftime("%Y-%m-%d"),
        actual_end=values_df["date"].iloc[-1].strftime("%Y-%m-%d"),
        trading_days=len(values_df),
        summary={
            "final_value": round(float(final_value), 2),
            "total_return": round(float(total_return), 6),
            "annual_return": round(float(annual_return), 6),
            "max_drawdown": round(float(max_drawdown), 6),
            "sharpe": round(float(sharpe), 6),
        },
    )
    metadata_file = results_dir / "current.meta.json"
    metadata_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.warning("current.meta.json 已更新")

    benchmark_file = results_dir / "current.benchmarks.json"
    benchmark_file.write_text(
        json.dumps(
            {
                "chart_data": benchmark_chart_data,
                "summary": benchmark_summary,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    logger.warning("current.benchmarks.json 已更新")

    # 清理
    fetcher.close()
    return values_df


if __name__ == "__main__":
    import sys

    start = sys.argv[1] if len(sys.argv) > 1 else None
    end = sys.argv[2] if len(sys.argv) > 2 else None

    run_backtest(start, end)
