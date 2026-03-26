#!/usr/bin/env python3
"""
量化诊断脚本

生成以下研究产物：
- 因子 RankIC / ICIR
- 单因子分层收益
- 因子冗余相关性
- 因子开关（ablation）回测
- 固定权重 vs 动态权重
- 核心池 vs 扩展池
- 参数扫描（持仓数 / 缓冲区 / 调仓频率）
- 成本敏感性
- 滚动窗口回测
- OOS 验证
- 压力测试与风控摘要
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config_loader import load_app_config
from src.data_fetcher_baostock import IndexDataFetcher
from src.market_regime import DynamicWeightScoringEngine, MarketRegimeDetector
from src.portfolio import SimulatedPortfolio
from src.scoring_baostock import ScoringEngine


OUTPUT_DIR = ROOT_DIR / "outputs" / "diagnostics"
REPORT_PATH = ROOT_DIR / "docs" / "QUANT_DIAGNOSTIC_REPORT.md"
BENCHMARK_CODE = "000300.SH"

IC_COLUMNS = ["factor", "horizon", "ic_mean", "ic_std", "ic_ir", "positive_ratio", "observations"]
QUANTILE_COLUMNS = ["factor", "quantile", "avg_forward_return", "median_forward_return", "count"]
OOS_COLUMNS = ["name", "train_return", "test_return", "train_sharpe", "test_sharpe", "train_rebalance_count", "test_rebalance_count"]


@dataclass
class BacktestResult:
    name: str
    summary: Dict[str, float]
    daily: pd.DataFrame
    trades: pd.DataFrame
    selected_history: pd.DataFrame


def get_rebalance_dates(trade_dates: List[pd.Timestamp], frequency: str) -> List[pd.Timestamp]:
    if not trade_dates:
        return []

    if frequency == "daily":
        return trade_dates

    if frequency == "weekly":
        chosen = []
        seen = set()
        for d in trade_dates:
            yw = d.isocalendar()[:2]
            if yw not in seen:
                chosen.append(d)
                seen.add(yw)
        return chosen or [trade_dates[0]]

    if frequency == "biweekly":
        chosen = []
        seen = []
        for d in trade_dates:
            yw = d.isocalendar()[:2]
            if yw not in seen:
                seen.append(yw)
                if len(seen) % 2 == 1:
                    chosen.append(d)
        return chosen or [trade_dates[0]]

    if frequency == "monthly":
        chosen = []
        seen = set()
        for d in trade_dates:
            ym = (d.year, d.month)
            if ym not in seen:
                chosen.append(d)
                seen.add(ym)
        return chosen or [trade_dates[0]]

    raise ValueError(f"Unsupported rebalance frequency: {frequency}")


def annualized_return(total_return: float, start_date: pd.Timestamp, end_date: pd.Timestamp) -> float:
    days = max((end_date - start_date).days, 1)
    years = days / 365
    return (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return


def sharpe_ratio(returns: pd.Series) -> float:
    returns = returns.dropna()
    if len(returns) < 5 or returns.std() == 0:
        return 0.0
    return float(returns.mean() / returns.std() * np.sqrt(252))


def summarize_backtest(
    name: str,
    daily_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    selected_history: pd.DataFrame,
    bucket_map: Dict[str, str],
) -> BacktestResult:
    if daily_df.empty:
        return BacktestResult(name=name, summary={"status": "empty"}, daily=daily_df, trades=trades_df, selected_history=selected_history)

    df = daily_df.copy()
    df["rolling_max"] = df["value"].cummax()
    df["drawdown"] = (df["value"] - df["rolling_max"]) / df["rolling_max"]

    total_return = float(df["value"].iloc[-1] / df["value"].iloc[0] - 1)
    annual_return_value = annualized_return(total_return, df["date"].iloc[0], df["date"].iloc[-1])
    max_drawdown = float(df["drawdown"].min())
    sharpe = sharpe_ratio(df["daily_return"])
    turnover_mean = float(df["turnover"].mean()) if "turnover" in df else 0.0
    turnover_total = float(df["turnover"].sum()) if "turnover" in df else 0.0
    avg_positions = float(df["num_positions"].mean()) if "num_positions" in df else 0.0
    max_weight_avg = float(df["max_weight"].mean()) if "max_weight" in df else 0.0
    max_bucket_avg = float(df["max_bucket_weight"].mean()) if "max_bucket_weight" in df else 0.0

    drawdown_idx = int(df["drawdown"].idxmin())
    max_drawdown_date = df.loc[drawdown_idx, "date"].strftime("%Y-%m-%d")

    stress_slice = df.nsmallest(10, "benchmark_daily_return")
    stress_alpha = float((stress_slice["daily_return"] - stress_slice["benchmark_daily_return"]).mean()) if not stress_slice.empty else 0.0

    summary = {
        "status": "ok",
        "total_return": total_return,
        "annual_return": annual_return_value,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "turnover_mean": turnover_mean,
        "turnover_total": turnover_total,
        "avg_positions": avg_positions,
        "avg_max_single_weight": max_weight_avg,
        "avg_max_bucket_weight": max_bucket_avg,
        "trade_count": int(len(trades_df)),
        "rebalance_count": int(selected_history["date"].nunique()) if not selected_history.empty else 0,
        "max_drawdown_date": max_drawdown_date,
        "stress_alpha_vs_benchmark": stress_alpha,
    }
    return BacktestResult(name=name, summary=summary, daily=df, trades=trades_df, selected_history=selected_history)


def compute_bucket_concentration(weights: Dict[str, float], bucket_map: Dict[str, str]) -> float:
    bucket_weights: Dict[str, float] = {}
    for code, weight in weights.items():
        bucket = bucket_map.get(code, "unknown")
        bucket_weights[bucket] = bucket_weights.get(bucket, 0.0) + weight
    return max(bucket_weights.values()) if bucket_weights else 0.0


def build_scores(
    code: str,
    hist_df: pd.DataFrame,
    scorer: ScoringEngine,
    benchmark_hist: pd.DataFrame,
    dynamic_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    kwargs = {
        "benchmark_data": benchmark_hist,
    }
    if dynamic_weights is not None:
        kwargs["dynamic_weights"] = dynamic_weights
    return scorer.score_index(hist_df, **kwargs)


def get_benchmark_history(etf_data: Dict[str, pd.DataFrame], benchmark_code: str = BENCHMARK_CODE) -> pd.DataFrame:
    benchmark_df = etf_data.get(benchmark_code)
    if benchmark_df is None or benchmark_df.empty:
        raise ValueError(f"Benchmark {benchmark_code} not available in ETF dataset")
    return benchmark_df


def run_strategy_backtest(
    name: str,
    config: dict,
    etf_data: Dict[str, pd.DataFrame],
    indices: List[dict],
    start_date: str,
    end_date: str,
    universe_codes: Iterable[str],
    top_n: int,
    buffer_n: int,
    rebalance_frequency: str,
    commission_rate: float,
    slippage: float,
    active_factors: Optional[List[str]] = None,
    use_dynamic_weights: bool = False,
) -> BacktestResult:
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    universe_codes = list(universe_codes)
    benchmark_df = get_benchmark_history(etf_data)
    trade_dates = [d for d in benchmark_df.index if start_dt <= d <= end_dt]
    rebalance_dates = set(get_rebalance_dates(trade_dates, rebalance_frequency))

    scorer_config = json.loads(json.dumps(config))
    if active_factors is not None:
        scorer_config.setdefault("factor_model", {})
        scorer_config["factor_model"]["active_factors"] = active_factors
        weights = scorer_config.get("factor_weights", {})
        norm = sum(weights.get(factor, 0.0) for factor in active_factors)
        if norm > 0:
            scorer_config["factor_weights"] = {
                **weights,
                **{factor: weights.get(factor, 0.0) / norm for factor in active_factors},
            }

    scorer = DynamicWeightScoringEngine(scorer_config) if use_dynamic_weights else ScoringEngine(scorer_config)
    detector = MarketRegimeDetector()
    portfolio = SimulatedPortfolio(
        initial_capital=config.get("portfolio", {}).get("initial_capital", 1_000_000),
        commission_rate=commission_rate,
        slippage=slippage,
    )

    name_map = {idx["code"]: idx["name"] for idx in indices}
    bucket_map = {idx["code"]: idx.get("bucket", "unknown") for idx in indices}
    trade_rows: List[dict] = []
    daily_rows: List[dict] = []
    selected_rows: List[dict] = []

    for i, date in enumerate(trade_dates):
        prices = {}
        for code in universe_codes:
            df = etf_data.get(code)
            if df is None or date not in df.index:
                continue
            prices[code] = float(df.loc[date, "close"])

        benchmark_hist = benchmark_df[benchmark_df.index <= date]
        if len(benchmark_hist) < 60:
            continue

        regime = detector.detect_regime(benchmark_hist["close"]) if len(benchmark_hist) >= 252 else "sideways"
        benchmark_return = 0.0
        if i > 0:
            prev_date = trade_dates[i - 1]
            if prev_date in benchmark_df.index and date in benchmark_df.index:
                benchmark_return = float(benchmark_df.loc[date, "close"] / benchmark_df.loc[prev_date, "close"] - 1)

        turnover = 0.0
        if prices:
            pre_value = portfolio.get_portfolio_value(prices)
        else:
            pre_value = portfolio.initial_capital

        if date in rebalance_dates:
            scores_dict = {}
            dynamic_weights = None
            if use_dynamic_weights and len(benchmark_hist) >= 252:
                scorer.update_market_regime(benchmark_hist["close"])
                dynamic_weights = scorer.current_weights

            for code in universe_codes:
                hist_df = etf_data[code][etf_data[code].index <= date]
                if len(hist_df) < 60:
                    continue
                scores = build_scores(code, hist_df, scorer, benchmark_hist, dynamic_weights)
                scores_dict[code] = scores

            ranking = scorer.rank_indices(scores_dict)
            if not ranking.empty:
                selected = ranking.head(top_n)["code"].tolist()
                hold_range = ranking.head(buffer_n)["code"].tolist()
                current_codes = set(portfolio.positions.keys())
                signals = {
                    "sell": [code for code in current_codes if code not in hold_range],
                    "buy": [code for code in selected if code not in current_codes],
                }
                trades = portfolio.execute_signal(signals, prices, name_map, date.strftime("%Y-%m-%d")) if prices else []
                if pre_value > 0:
                    turnover = float(sum(trade.amount for trade in trades) / pre_value) if trades else 0.0
                for trade in trades:
                    trade_rows.append(
                        {
                            "date": trade.date,
                            "type": trade.type,
                            "code": trade.code,
                            "name": trade.name,
                            "shares": trade.shares,
                            "price": trade.price,
                            "amount": trade.amount,
                            "commission": trade.commission,
                            "strategy": name,
                        }
                    )
                for _, row in ranking.head(top_n).iterrows():
                    selected_rows.append(
                        {
                            "date": date,
                            "code": row["code"],
                            "rank": int(row["rank"]),
                            "score": float(row["total_score"]),
                            "strategy": name,
                            "regime": regime,
                        }
                    )

        if prices:
            record = portfolio.record_daily_value(date.strftime("%Y-%m-%d"), prices)
            weights = portfolio.get_position_weights(prices)
            daily_rows.append(
                {
                    "date": pd.Timestamp(record["date"]),
                    "value": float(record["value"]),
                    "nav": float(record["nav"]),
                    "daily_return": float(record["return"] if not daily_rows else (record["value"] / daily_rows[-1]["value"] - 1)),
                    "turnover": turnover,
                    "num_positions": int(record["num_positions"]),
                    "cash": float(record["cash"]),
                    "regime": regime,
                    "benchmark_daily_return": benchmark_return,
                    "max_weight": float(max(weights.values()) if weights else 0.0),
                    "max_bucket_weight": float(compute_bucket_concentration(weights, bucket_map)),
                }
            )

    daily_df = pd.DataFrame(daily_rows)
    trades_df = pd.DataFrame(trade_rows)
    selected_df = pd.DataFrame(selected_rows)
    return summarize_backtest(name, daily_df, trades_df, selected_df, bucket_map)


def prepare_factor_dataset(
    config: dict,
    etf_data: Dict[str, pd.DataFrame],
    indices: List[dict],
    start_date: str,
    end_date: str,
    forward_days: List[int],
) -> pd.DataFrame:
    scorer = ScoringEngine(config)
    benchmark_df = get_benchmark_history(etf_data)
    trade_dates = [d for d in benchmark_df.index if pd.to_datetime(start_date) <= d <= pd.to_datetime(end_date)]
    rebalance_dates = get_rebalance_dates(trade_dates, "weekly")
    rows = []

    for date in rebalance_dates:
        benchmark_hist = benchmark_df[benchmark_df.index <= date]
        if len(benchmark_hist) < 60:
            continue
        for idx in indices:
            code = idx["code"]
            df = etf_data.get(code)
            if df is None or date not in df.index:
                continue
            hist_df = df[df.index <= date]
            if len(hist_df) < 60:
                continue
            scores = scorer.score_index(hist_df, benchmark_hist)
            row = {
                "date": date,
                "code": code,
                "bucket": idx.get("bucket", "unknown"),
            }
            for factor in scorer.active_factors + scorer.auxiliary_factors:
                row[factor] = float(scores.get(factor, 0.5))

            current_loc = df.index.get_loc(date)
            if isinstance(current_loc, slice):
                continue
            for horizon in forward_days:
                future_loc = current_loc + horizon
                if future_loc < len(df.index):
                    row[f"fwd_{horizon}d"] = float(df.iloc[future_loc]["close"] / df.iloc[current_loc]["close"] - 1)
                else:
                    row[f"fwd_{horizon}d"] = np.nan
            rows.append(row)

    return pd.DataFrame(rows)


def compute_ic_table(factor_df: pd.DataFrame, factors: List[str], horizons: List[int]) -> pd.DataFrame:
    if factor_df.empty:
        return pd.DataFrame(columns=IC_COLUMNS)
    rows = []
    for factor in factors:
        for horizon in horizons:
            ic_series = []
            for _, group in factor_df.dropna(subset=[factor, f"fwd_{horizon}d"]).groupby("date"):
                if len(group) < 5:
                    continue
                ranked_factor = group[factor].rank(method="average")
                ranked_return = group[f"fwd_{horizon}d"].rank(method="average")
                ic = ranked_factor.corr(ranked_return)
                if pd.notna(ic):
                    ic_series.append(ic)
            if ic_series:
                series = pd.Series(ic_series)
                rows.append(
                    {
                        "factor": factor,
                        "horizon": horizon,
                        "ic_mean": float(series.mean()),
                        "ic_std": float(series.std(ddof=0)),
                        "ic_ir": float(series.mean() / series.std(ddof=0)) if series.std(ddof=0) not in (0, np.nan) else 0.0,
                        "positive_ratio": float((series > 0).mean()),
                        "observations": int(len(series)),
                    }
                )
    if not rows:
        return pd.DataFrame(columns=IC_COLUMNS)
    return pd.DataFrame(rows, columns=IC_COLUMNS).sort_values(["horizon", "ic_mean"], ascending=[True, False])


def compute_quantile_returns(factor_df: pd.DataFrame, factors: List[str], horizon: int, quantiles: int = 5) -> pd.DataFrame:
    if factor_df.empty:
        return pd.DataFrame(columns=QUANTILE_COLUMNS)
    rows = []
    for factor in factors:
        for date, group in factor_df.dropna(subset=[factor, f"fwd_{horizon}d"]).groupby("date"):
            if len(group) < quantiles:
                continue
            try:
                ranked = group.assign(
                    quantile=pd.qcut(group[factor].rank(method="first"), quantiles, labels=False) + 1
                )
            except ValueError:
                continue
            for quantile, q_group in ranked.groupby("quantile"):
                rows.append(
                    {
                        "factor": factor,
                        "date": date,
                        "quantile": int(quantile),
                        "forward_return": float(q_group[f"fwd_{horizon}d"].mean()),
                    }
                )
    result = pd.DataFrame(rows)
    if result.empty:
        return pd.DataFrame(columns=QUANTILE_COLUMNS)
    summary = (
        result.groupby(["factor", "quantile"])["forward_return"]
        .agg(["mean", "median", "count"])
        .reset_index()
        .rename(columns={"mean": "avg_forward_return", "median": "median_forward_return"})
    )
    return summary[QUANTILE_COLUMNS]


def compute_factor_redundancy(factor_df: pd.DataFrame, factors: List[str]) -> pd.DataFrame:
    available = [factor for factor in factors if factor in factor_df.columns]
    if not available:
        return pd.DataFrame()
    corr = pd.DataFrame(index=available, columns=available, dtype=float)
    for left in available:
        for right in available:
            lhs = factor_df[left]
            rhs = factor_df[right]
            if lhs.std(ddof=0) == 0 or rhs.std(ddof=0) == 0:
                corr.loc[left, right] = np.nan
            else:
                corr.loc[left, right] = lhs.corr(rhs)
    return corr


def compare_regimes(backtest: BacktestResult) -> pd.DataFrame:
    if backtest.daily.empty:
        return pd.DataFrame()
    rows = []
    for regime, group in backtest.daily.groupby("regime"):
        returns = group["daily_return"].dropna()
        rows.append(
            {
                "regime": regime,
                "days": int(len(group)),
                "avg_daily_return": float(returns.mean()) if not returns.empty else 0.0,
                "volatility": float(returns.std(ddof=0) * np.sqrt(252)) if len(returns) > 1 else 0.0,
                "sharpe": sharpe_ratio(returns),
                "total_return": float(group["value"].iloc[-1] / group["value"].iloc[0] - 1) if len(group) > 1 else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("regime")


def rolling_windows(start: pd.Timestamp, end: pd.Timestamp, months: int = 6, step_days: int = 63) -> List[tuple[pd.Timestamp, pd.Timestamp]]:
    windows = []
    current = start
    delta = pd.Timedelta(days=months * 30)
    while current + delta <= end:
        windows.append((current, current + delta))
        current += pd.Timedelta(days=step_days)
    return windows


def markdown_table(df: pd.DataFrame, max_rows: int = 12) -> str:
    if df.empty:
        return "_No data_"
    head = df.head(max_rows).copy()
    columns = list(head.columns)
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = []
    for _, row in head.iterrows():
        body.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join([header, divider, *body])


def classify_strategy_rating(baseline: Dict[str, float], oos: Dict[str, float]) -> tuple[str, str, str]:
    annual = baseline.get("annual_return", 0.0)
    drawdown = baseline.get("max_drawdown", 0.0)
    sharpe = baseline.get("sharpe", 0.0)
    test_count = oos.get("test_rebalance_count", 0)
    if test_count < 3:
        return "观察", "验证不足", "继续研究，不建议单独实盘"
    if annual > 0.10 and sharpe > 0.6 and drawdown > -0.18:
        return "可小仓位试运行", "初步验证", "冻结基线后做小仓位跟踪"
    if annual > 0.05 and sharpe > 0.4 and drawdown > -0.22:
        return "观察", "初步验证", "缩小标的池并继续验证"
    return "弱", "验证不足", "先优化模型与标的池"


def format_oos_status(oos: Dict[str, float]) -> str:
    if oos.get("test_rebalance_count", 0) < 3:
        return "OOS 验证暂不成立：测试窗口过短或无有效调仓，当前结果不具统计解释力。"
    return (
        f"OOS 最优参数：`{oos.get('best_name', 'n/a')}`，训练期收益 `{oos.get('train_return', 0):.2%}`，"
        f"测试期收益 `{oos.get('test_return', 0):.2%}`。"
    )


def build_key_findings(
    baseline: Dict[str, float],
    dynamic: Dict[str, float],
    oos: Dict[str, float],
    ablation_df: pd.DataFrame,
    universe_df: pd.DataFrame,
    cost_df: pd.DataFrame,
) -> List[str]:
    findings = []
    if dynamic.get("dynamic_annual", 0.0) > dynamic.get("fixed_annual", 0.0):
        findings.append(
            f"动态权重优于固定权重：年化 `{dynamic.get('dynamic_annual', 0):.2%}` 对 `{dynamic.get('fixed_annual', 0):.2%}`。"
        )
    if not ablation_df.empty:
        best = ablation_df.iloc[0]
        full_row = ablation_df[ablation_df["name"] == "ablation_full_model"]
        if not full_row.empty and best["name"] != "ablation_full_model" and best["annual_return"] > full_row.iloc[0]["annual_return"]:
            findings.append(
                f"删减模型优于全模型：`{best['name']}` 年化 `{best['annual_return']:.2%}`，说明当前因子组合存在拖累或冗余。"
            )
    if len(universe_df) >= 2:
        top = universe_df.iloc[0]
        bottom = universe_df.iloc[-1]
        if top["annual_return"] > bottom["annual_return"]:
            findings.append(
                f"核心池明显优于扩展池：`{top['name']}` 年化 `{top['annual_return']:.2%}`，扩池后排序质量下降。"
            )
    if not cost_df.empty:
        high_cost = cost_df.sort_values("cost_bps").iloc[-1]
        findings.append(
            f"成本敏感性较高：`{int(high_cost['cost_bps'])}bps` 下年化仅 `{high_cost['annual_return']:.2%}`。"
        )
    if oos.get("test_rebalance_count", 0) < 3:
        findings.append("OOS 验证暂不成立：测试窗口过短，当前结果不具统计解释力。")
    elif oos.get("test_return", 0.0) <= 0:
        findings.append("OOS 测试未确认当前参数优势，需继续观察样本外稳定性。")
    if not findings:
        findings.append(
            f"基线策略当前年化 `{baseline.get('annual_return', 0):.2%}`，需结合更长样本继续验证。"
        )
    return findings


def write_report(report_data: Dict[str, pd.DataFrame], summary_blob: Dict[str, dict]) -> None:
    lines = [
        "# 量化诊断报告",
        "",
        "本报告由 `scripts/run_quant_diagnostics.py` 自动生成。",
        "",
        "## 核心结论",
        "",
    ]
    baseline = summary_blob.get("baseline", {})
    dynamic = summary_blob.get("dynamic_vs_fixed", {})
    oos = summary_blob.get("oos", {})
    rating, validation_status, action = classify_strategy_rating(baseline, oos)
    findings = build_key_findings(
        baseline,
        dynamic,
        oos,
        report_data.get("ablation", pd.DataFrame()),
        report_data.get("universe", pd.DataFrame()),
        report_data.get("cost", pd.DataFrame()),
    )
    lines.extend(
        [
            f"- 当前评级：`{rating}`",
            f"- 数据结论：基线年化 `{baseline.get('annual_return', 0):.2%}`，最大回撤 `{baseline.get('max_drawdown', 0):.2%}`，夏普 `{baseline.get('sharpe', 0):.2f}`。",
            f"- 策略验证度：`{validation_status}`",
            f"- 当前动作：`{action}`",
            "",
            "## 最重要发现",
            "",
            *[f"- {finding}" for finding in findings],
            "",
            "## 口径说明",
            "",
            "- `value` 当前是价格分位代理，不是基本面估值因子，应解读为均值回复/位置因子。",
            "- `flow` 当前诊断口径主要反映量价代理，尚未完整复刻正式策略中的北向资金和 ETF 份额数据链。",
            "- 动态权重当前只能解读为“替代权重配置在本样本更优”，不能视为跨市场状态切换已经被验证。",
            "",
            "## 验证状态",
            "",
            f"- 固定权重 vs 动态权重：固定 `{dynamic.get('fixed_annual', 0):.2%}` / 动态 `{dynamic.get('dynamic_annual', 0):.2%}`。",
            f"- {format_oos_status(oos)}",
            f"- OOS 有效调仓次数：训练 `{int(oos.get('train_rebalance_count', 0))}` / 测试 `{int(oos.get('test_rebalance_count', 0))}`。",
            "",
            "## RankIC",
            "",
            markdown_table(report_data["ic"]),
            "",
            "## 单因子分层",
            "",
            markdown_table(report_data["quantiles"]),
            "",
            "## 因子冗余",
            "",
            markdown_table(report_data["factor_redundancy"].reset_index().rename(columns={"index": "factor"})),
            "",
            "## 因子开关实验",
            "",
            markdown_table(report_data["ablation"]),
            "",
            "## 参数扫描",
            "",
            markdown_table(report_data["parameter_sweep"]),
            "",
            "## OOS 明细",
            "",
            markdown_table(report_data["oos"]),
            "",
            "## Universe 对比",
            "",
            markdown_table(report_data["universe"]),
            "",
            "## 成本敏感性",
            "",
            markdown_table(report_data["cost"]),
            "",
            "## 滚动窗口",
            "",
            markdown_table(report_data["rolling"]),
            "",
            "## 市场阶段",
            "",
            markdown_table(report_data["regime"]),
            "",
            "## 风控摘要",
            "",
            f"- 平均换手率：`{baseline.get('turnover_mean', 0):.2%}`",
            f"- 平均持仓数：`{baseline.get('avg_positions', 0):.2f}`",
            f"- 平均单标的最大权重：`{baseline.get('avg_max_single_weight', 0):.2%}`",
            f"- 平均单类资产最大集中度：`{baseline.get('avg_max_bucket_weight', 0):.2%}`",
            f"- 压力日超额：`{baseline.get('stress_alpha_vs_benchmark', 0):.2%}`",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_diagnostics(start_date: str = "20240101", end_date: Optional[str] = None) -> dict:
    end_date = end_date or pd.Timestamp.today().strftime("%Y%m%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    config = load_app_config(ROOT_DIR)
    indices = config.get("indices", [])
    fetcher = IndexDataFetcher()

    etf_data: Dict[str, pd.DataFrame] = {}
    print("Loading ETF history...")
    for idx in indices:
        code = idx["code"]
        etf = idx.get("etf")
        if not etf:
            continue
        df = fetcher.fetch_etf_history(etf, start_date, force_refresh=False)
        if not df.empty:
            etf_data[code] = df

    active_codes = [idx["code"] for idx in indices if idx["code"] in etf_data]
    core_codes = [idx["code"] for idx in indices if idx.get("bucket") == "core" and idx["code"] in etf_data]
    extended_codes = active_codes
    active_factors = config.get("factor_model", {}).get("active_factors", ["momentum", "trend", "value", "relative_strength"])
    aux_factors = config.get("factor_model", {}).get("auxiliary_factors", ["volatility", "flow"])

    factor_df = prepare_factor_dataset(config, etf_data, indices, start_date, end_date, [5, 20])
    print("Computing factor diagnostics...")
    ic_table = compute_ic_table(factor_df, active_factors + aux_factors, [5, 20])
    quantile_table = compute_quantile_returns(factor_df, active_factors, 20)
    redundancy = compute_factor_redundancy(factor_df, active_factors + aux_factors)

    print("Running baseline and dynamic backtests...")
    baseline_bt = run_strategy_backtest(
        name="baseline_extended",
        config=config,
        etf_data=etf_data,
        indices=indices,
        start_date=start_date,
        end_date=end_date,
        universe_codes=extended_codes,
        top_n=config["strategy"].get("top_n", 5),
        buffer_n=config["strategy"].get("buffer_n", 8),
        rebalance_frequency=config["strategy"].get("rebalance_frequency", "weekly"),
        commission_rate=config.get("portfolio", {}).get("commission", 0.0003),
        slippage=config.get("portfolio", {}).get("slippage", 0.001),
        active_factors=active_factors,
        use_dynamic_weights=False,
    )

    dynamic_bt = run_strategy_backtest(
        name="dynamic_extended",
        config=config,
        etf_data=etf_data,
        indices=indices,
        start_date=start_date,
        end_date=end_date,
        universe_codes=extended_codes,
        top_n=config["strategy"].get("top_n", 5),
        buffer_n=config["strategy"].get("buffer_n", 8),
        rebalance_frequency=config["strategy"].get("rebalance_frequency", "weekly"),
        commission_rate=config.get("portfolio", {}).get("commission", 0.0003),
        slippage=config.get("portfolio", {}).get("slippage", 0.001),
        active_factors=active_factors,
        use_dynamic_weights=True,
    )

    ablation_rows = []
    print("Running factor ablation experiments...")
    for factor in ["full_model", *active_factors]:
        subset = active_factors if factor == "full_model" else [f for f in active_factors if f != factor]
        result = run_strategy_backtest(
            name=f"ablation_{factor}",
            config=config,
            etf_data=etf_data,
            indices=indices,
            start_date=start_date,
            end_date=end_date,
            universe_codes=extended_codes,
            top_n=config["strategy"].get("top_n", 5),
            buffer_n=config["strategy"].get("buffer_n", 8),
            rebalance_frequency=config["strategy"].get("rebalance_frequency", "weekly"),
            commission_rate=config.get("portfolio", {}).get("commission", 0.0003),
            slippage=config.get("portfolio", {}).get("slippage", 0.001),
            active_factors=subset,
            use_dynamic_weights=False,
        )
        ablation_rows.append({"name": result.name, **result.summary, "active_factors": ",".join(subset)})
    ablation_df = pd.DataFrame(ablation_rows).sort_values("annual_return", ascending=False)

    universe_rows = []
    print("Running universe comparison...")
    for name, universe_codes in [("core_pool", core_codes), ("extended_pool", extended_codes)]:
        result = run_strategy_backtest(
            name=name,
            config=config,
            etf_data=etf_data,
            indices=indices,
            start_date=start_date,
            end_date=end_date,
            universe_codes=universe_codes,
            top_n=min(config["strategy"].get("top_n", 5), len(universe_codes)),
            buffer_n=min(config["strategy"].get("buffer_n", 8), len(universe_codes)),
            rebalance_frequency=config["strategy"].get("rebalance_frequency", "weekly"),
            commission_rate=config.get("portfolio", {}).get("commission", 0.0003),
            slippage=config.get("portfolio", {}).get("slippage", 0.001),
            active_factors=active_factors,
            use_dynamic_weights=False,
        )
        universe_rows.append({"name": name, "universe_size": len(universe_codes), **result.summary})
    universe_df = pd.DataFrame(universe_rows).sort_values("annual_return", ascending=False)

    parameter_rows = []
    print("Running parameter sweep...")
    for top_n in [3, 5, 8]:
        for buffer_gap in [1, 3, 5]:
            for frequency in ["weekly", "biweekly", "monthly"]:
                buffer_n = min(len(extended_codes), top_n + buffer_gap)
                result = run_strategy_backtest(
                    name=f"param_t{top_n}_b{buffer_gap}_{frequency}",
                    config=config,
                    etf_data=etf_data,
                    indices=indices,
                    start_date=start_date,
                    end_date=end_date,
                    universe_codes=extended_codes,
                    top_n=min(top_n, len(extended_codes)),
                    buffer_n=buffer_n,
                    rebalance_frequency=frequency,
                    commission_rate=config.get("portfolio", {}).get("commission", 0.0003),
                    slippage=config.get("portfolio", {}).get("slippage", 0.001),
                    active_factors=active_factors,
                    use_dynamic_weights=False,
                )
                parameter_rows.append(
                    {
                        "name": result.name,
                        "top_n": top_n,
                        "buffer_n": buffer_n,
                        "frequency": frequency,
                        **result.summary,
                    }
                )
    parameter_df = pd.DataFrame(parameter_rows).sort_values(["annual_return", "sharpe"], ascending=False)

    cost_rows = []
    print("Running cost sensitivity...")
    for bps in [0, 5, 10, 20]:
        unit = bps / 10000 / 2
        result = run_strategy_backtest(
            name=f"cost_{bps}bps",
            config=config,
            etf_data=etf_data,
            indices=indices,
            start_date=start_date,
            end_date=end_date,
            universe_codes=extended_codes,
            top_n=config["strategy"].get("top_n", 5),
            buffer_n=config["strategy"].get("buffer_n", 8),
            rebalance_frequency=config["strategy"].get("rebalance_frequency", "weekly"),
            commission_rate=unit,
            slippage=unit,
            active_factors=active_factors,
            use_dynamic_weights=False,
        )
        cost_rows.append({"cost_bps": bps, **result.summary})
    cost_df = pd.DataFrame(cost_rows).sort_values("cost_bps")

    rolling_rows = []
    print("Running rolling windows...")
    for window_start, window_end in rolling_windows(pd.to_datetime(start_date), pd.to_datetime(end_date), months=6, step_days=63):
        result = run_strategy_backtest(
            name=f"roll_{window_start:%Y%m%d}_{window_end:%Y%m%d}",
            config=config,
            etf_data=etf_data,
            indices=indices,
            start_date=window_start.strftime("%Y%m%d"),
            end_date=window_end.strftime("%Y%m%d"),
            universe_codes=extended_codes,
            top_n=config["strategy"].get("top_n", 5),
            buffer_n=config["strategy"].get("buffer_n", 8),
            rebalance_frequency=config["strategy"].get("rebalance_frequency", "weekly"),
            commission_rate=config.get("portfolio", {}).get("commission", 0.0003),
            slippage=config.get("portfolio", {}).get("slippage", 0.001),
            active_factors=active_factors,
            use_dynamic_weights=False,
        )
        rolling_rows.append(
            {
                "window_start": window_start.strftime("%Y-%m-%d"),
                "window_end": window_end.strftime("%Y-%m-%d"),
                **result.summary,
            }
        )
    rolling_df = pd.DataFrame(rolling_rows).sort_values("window_start")

    train_end = "20241231"
    test_start = "20250101"
    candidate_grid = parameter_df[["top_n", "buffer_n", "frequency"]].drop_duplicates()
    best_train = None
    best_train_return = -np.inf
    oos_rows = []
    print("Running OOS validation...")
    for _, row in candidate_grid.iterrows():
        train_result = run_strategy_backtest(
            name=f"train_t{row.top_n}_b{row.buffer_n}_{row.frequency}",
            config=config,
            etf_data=etf_data,
            indices=indices,
            start_date=start_date,
            end_date=train_end,
            universe_codes=extended_codes,
            top_n=int(row.top_n),
            buffer_n=int(row.buffer_n),
            rebalance_frequency=row.frequency,
            commission_rate=config.get("portfolio", {}).get("commission", 0.0003),
            slippage=config.get("portfolio", {}).get("slippage", 0.001),
            active_factors=active_factors,
            use_dynamic_weights=False,
        )
        test_result = run_strategy_backtest(
            name=f"test_t{row.top_n}_b{row.buffer_n}_{row.frequency}",
            config=config,
            etf_data=etf_data,
            indices=indices,
            start_date=test_start,
            end_date=end_date,
            universe_codes=extended_codes,
            top_n=int(row.top_n),
            buffer_n=int(row.buffer_n),
            rebalance_frequency=row.frequency,
            commission_rate=config.get("portfolio", {}).get("commission", 0.0003),
            slippage=config.get("portfolio", {}).get("slippage", 0.001),
            active_factors=active_factors,
            use_dynamic_weights=False,
        )
        oos_rows.append(
            {
                "name": f"t{row.top_n}_b{row.buffer_n}_{row.frequency}",
                "train_return": train_result.summary.get("total_return", 0.0),
                "test_return": test_result.summary.get("total_return", 0.0),
                "train_sharpe": train_result.summary.get("sharpe", 0.0),
                "test_sharpe": test_result.summary.get("sharpe", 0.0),
                "train_rebalance_count": train_result.summary.get("rebalance_count", 0),
                "test_rebalance_count": test_result.summary.get("rebalance_count", 0),
            }
        )
        if train_result.summary.get("total_return", -np.inf) > best_train_return:
            best_train_return = train_result.summary.get("total_return", -np.inf)
            best_train = oos_rows[-1]
    oos_df = pd.DataFrame(oos_rows, columns=OOS_COLUMNS).sort_values("test_return", ascending=False)

    regime_df = compare_regimes(baseline_bt)

    report_tables = {
        "ic": ic_table,
        "quantiles": quantile_table,
        "factor_redundancy": redundancy,
        "ablation": ablation_df,
        "parameter_sweep": parameter_df,
        "oos": oos_df,
        "universe": universe_df,
        "cost": cost_df,
        "rolling": rolling_df,
        "regime": regime_df,
    }
    for name, table in report_tables.items():
        if isinstance(table, pd.DataFrame):
            table.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)
    redundancy.to_csv(OUTPUT_DIR / "factor_redundancy.csv")
    baseline_bt.daily.to_csv(OUTPUT_DIR / "baseline_daily.csv", index=False)
    baseline_bt.trades.to_csv(OUTPUT_DIR / "baseline_trades.csv", index=False)
    baseline_bt.selected_history.to_csv(OUTPUT_DIR / "baseline_selected.csv", index=False)

    summary_blob = {
        "baseline": baseline_bt.summary,
        "dynamic_vs_fixed": {
            "fixed_annual": baseline_bt.summary.get("annual_return", 0.0),
            "dynamic_annual": dynamic_bt.summary.get("annual_return", 0.0),
            "fixed_sharpe": baseline_bt.summary.get("sharpe", 0.0),
            "dynamic_sharpe": dynamic_bt.summary.get("sharpe", 0.0),
        },
        "oos": {
            "best_name": best_train.get("name") if best_train else "n/a",
            "train_return": best_train.get("train_return", 0.0) if best_train else 0.0,
            "test_return": best_train.get("test_return", 0.0) if best_train else 0.0,
            "train_rebalance_count": best_train.get("train_rebalance_count", 0) if best_train else 0,
            "test_rebalance_count": best_train.get("test_rebalance_count", 0) if best_train else 0,
        },
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary_blob, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(report_tables, summary_blob)
    fetcher.close()
    print(f"Diagnostics completed. Report written to {REPORT_PATH}")
    return summary_blob


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "20240101"
    end = sys.argv[2] if len(sys.argv) > 2 else None
    summary = run_diagnostics(start, end)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
