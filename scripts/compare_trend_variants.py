from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import copy
import json
import os
import sys
import time

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.backtest_utils import (
    build_rebalance_signals,
    compute_backtest_metrics,
    compute_fetch_start_date,
    create_portfolio,
    load_etf_history,
    load_strategy_config,
    select_rebalance_dates,
    validate_etf_history_coverage,
)
from src.data_fetcher_baostock import IndexDataFetcher
from src.scoring_baostock import ScoringEngine

BASE_CONFIG = load_strategy_config(ROOT_DIR)


class LegacyTrendScoringEngine(ScoringEngine):
    def calc_trend_score(self, prices: pd.Series):
        if len(prices) < 60:
            return {
                "score": 0.5,
                "details": {
                    "price_vs_ma20": 0.5,
                    "price_vs_ma60": 0.5,
                    "ma20_vs_ma60": 0.5,
                    "ma20_slope": 0.5,
                },
                "weights": dict(self.trend_subfactor_weights),
                "metrics": {
                    "price_vs_ma20": 0.0,
                    "price_vs_ma60": 0.0,
                    "ma20_vs_ma60": 0.0,
                    "ma20_slope": 0.0,
                    "overextension_penalty": 0.0,
                    "ma20_above_ma60": False,
                },
            }
        ma20 = prices.rolling(20).mean().iloc[-1]
        ma60 = prices.rolling(60).mean().iloc[-1]
        current = prices.iloc[-1]
        score = 0.5 + (0.25 if current > ma20 else 0.0) + (0.25 if current > ma60 else 0.0)
        return {
            "score": float(min(1.0, score)),
            "details": {
                "price_vs_ma20": 1.0 if current > ma20 else 0.0,
                "price_vs_ma60": 1.0 if current > ma60 else 0.0,
                "ma20_vs_ma60": 0.5,
                "ma20_slope": 0.5,
            },
            "weights": dict(self.trend_subfactor_weights),
            "metrics": {
                "price_vs_ma20": float((current - ma20) / ma20) if ma20 else 0.0,
                "price_vs_ma60": float((current - ma60) / ma60) if ma60 else 0.0,
                "ma20_vs_ma60": float((ma20 - ma60) / ma60) if ma60 else 0.0,
                "ma20_slope": 0.0,
                "overextension_penalty": 0.0,
                "ma20_above_ma60": bool(ma20 > ma60),
            },
        }


class V1LinearScoringEngine(ScoringEngine):
    def calc_trend_score(self, prices: pd.Series):
        if len(prices) < 60:
            neutral = {key: round(float(weight), 4) for key, weight in self.trend_subfactor_weights.items()}
            return {
                "score": 0.5,
                "details": {key: 0.5 for key in neutral},
                "weights": neutral,
                "metrics": {
                    "price_vs_ma20": 0.0,
                    "price_vs_ma60": 0.0,
                    "ma20_vs_ma60": 0.0,
                    "ma20_slope": 0.0,
                    "overextension_penalty": 0.0,
                    "ma20_above_ma60": False,
                },
            }
        ma20_series = prices.rolling(20).mean()
        ma60_series = prices.rolling(60).mean()
        ma20 = ma20_series.iloc[-1]
        ma60 = ma60_series.iloc[-1]
        current = prices.iloc[-1]
        price_vs_ma20 = (current - ma20) / ma20 if ma20 else 0.0
        price_vs_ma60 = (current - ma60) / ma60 if ma60 else 0.0
        ma20_vs_ma60 = (ma20 - ma60) / ma60 if ma60 else 0.0
        ma20_slope = 0.0
        if len(prices) >= 70:
            ma20_prev = ma20_series.iloc[-11]
            if pd.notna(ma20_prev) and ma20_prev:
                ma20_slope = (ma20 - ma20_prev) / ma20_prev
        detail_scores = {
            "price_vs_ma20": round(self._clip_score(price_vs_ma20, 0.08), 4),
            "price_vs_ma60": round(self._clip_score(price_vs_ma60, 0.12), 4),
            "ma20_vs_ma60": round(self._clip_score(ma20_vs_ma60, 0.10), 4),
            "ma20_slope": round(self._clip_score(ma20_slope, 0.05), 4),
        }
        detail_weights = {key: round(float(weight), 4) for key, weight in self.trend_subfactor_weights.items()}
        score = sum(detail_scores[k] * detail_weights[k] for k in detail_scores) / sum(detail_weights.values())
        return {
            "score": float(score),
            "details": detail_scores,
            "weights": detail_weights,
            "metrics": {
                "price_vs_ma20": float(price_vs_ma20),
                "price_vs_ma60": float(price_vs_ma60),
                "ma20_vs_ma60": float(ma20_vs_ma60),
                "ma20_slope": float(ma20_slope),
                "overextension_penalty": 0.0,
                "ma20_above_ma60": bool(ma20 > ma60),
            },
        }


class RecommendedTrendScoringEngine(ScoringEngine):
    def calc_trend_score(self, prices: pd.Series):
        weights = {"price_vs_ma20": 0.4, "price_vs_ma60": 0.4, "ma20_vs_ma60": 0.2}
        if len(prices) < 60:
            return {
                "score": 0.5,
                "details": {k: 0.5 for k in weights},
                "weights": weights,
                "metrics": {
                    "price_vs_ma20": 0.0,
                    "price_vs_ma60": 0.0,
                    "ma20_vs_ma60": 0.0,
                    "ma20_slope": 0.0,
                    "overextension_penalty": 0.0,
                    "ma20_above_ma60": False,
                },
            }
        ma20 = prices.rolling(20).mean().iloc[-1]
        ma60 = prices.rolling(60).mean().iloc[-1]
        current = prices.iloc[-1]
        price_vs_ma20 = (current - ma20) / ma20 if ma20 else 0.0
        price_vs_ma60 = (current - ma60) / ma60 if ma60 else 0.0
        ma20_vs_ma60 = (ma20 - ma60) / ma60 if ma60 else 0.0
        detail_scores = {
            "price_vs_ma20": round(self._clip_score(price_vs_ma20, 0.10), 4),
            "price_vs_ma60": round(self._clip_score(price_vs_ma60, 0.15), 4),
            "ma20_vs_ma60": round(self._clip_score(ma20_vs_ma60, 0.10), 4),
        }
        score = sum(detail_scores[k] * weights[k] for k in detail_scores)
        return {
            "score": float(score),
            "details": detail_scores,
            "weights": weights,
            "metrics": {
                "price_vs_ma20": float(price_vs_ma20),
                "price_vs_ma60": float(price_vs_ma60),
                "ma20_vs_ma60": float(ma20_vs_ma60),
                "ma20_slope": 0.0,
                "overextension_penalty": 0.0,
                "ma20_above_ma60": bool(ma20 > ma60),
            },
        }


class MinimalTrendScoringEngine(ScoringEngine):
    def calc_trend_score(self, prices: pd.Series):
        weights = {"price_vs_ma60": 0.5, "ma20_vs_ma60": 0.5}
        if len(prices) < 60:
            return {
                "score": 0.5,
                "details": {k: 0.5 for k in weights},
                "weights": weights,
                "metrics": {
                    "price_vs_ma20": 0.0,
                    "price_vs_ma60": 0.0,
                    "ma20_vs_ma60": 0.0,
                    "ma20_slope": 0.0,
                    "overextension_penalty": 0.0,
                    "ma20_above_ma60": False,
                },
            }
        ma20 = prices.rolling(20).mean().iloc[-1]
        ma60 = prices.rolling(60).mean().iloc[-1]
        current = prices.iloc[-1]
        price_vs_ma60 = (current - ma60) / ma60 if ma60 else 0.0
        ma20_vs_ma60 = (ma20 - ma60) / ma60 if ma60 else 0.0
        detail_scores = {
            "price_vs_ma60": round(self._clip_score(price_vs_ma60, 0.15), 4),
            "ma20_vs_ma60": round(self._clip_score(ma20_vs_ma60, 0.10), 4),
        }
        score = sum(detail_scores[k] * weights[k] for k in detail_scores)
        return {
            "score": float(score),
            "details": detail_scores,
            "weights": weights,
            "metrics": {
                "price_vs_ma20": float((current - ma20) / ma20) if ma20 else 0.0,
                "price_vs_ma60": float(price_vs_ma60),
                "ma20_vs_ma60": float(ma20_vs_ma60),
                "ma20_slope": 0.0,
                "overextension_penalty": 0.0,
                "ma20_above_ma60": bool(ma20 > ma60),
            },
        }


def make_engine(config: dict, variant: str):
    mapping = {
        "legacy": LegacyTrendScoringEngine,
        "v1": V1LinearScoringEngine,
        "recommended": RecommendedTrendScoringEngine,
        "minimal": MinimalTrendScoringEngine,
    }
    return mapping[variant](config)


@dataclass
class RunResult:
    summary: dict
    trades: int


def run_period(start_date: str, end_date: str, variant: str) -> RunResult:
    config = copy.deepcopy(BASE_CONFIG)
    config.setdefault("backtest", {})["score_workers"] = int(os.environ.get("TREND_SCORE_WORKERS", "4"))
    fetcher = IndexDataFetcher()
    scorer = make_engine(config, variant)
    portfolio = create_portfolio(config, initial_capital=1_000_000)

    strategy = config.get("strategy", {})
    backtest = config.get("backtest", {})
    top_n = strategy.get("top_n", 5)
    buffer_n = strategy.get("buffer_n", 8)
    rebalance_freq = strategy.get("rebalance_frequency", "weekly")
    strict_weekly = bool(strategy.get("strict_weekly_execution", False))
    warmup = int(backtest.get("warmup_days", 370))
    workers = max(1, int(backtest.get("score_workers", 1)))
    indices = config.get("indices", [])
    code_to_name = {idx["code"]: idx["name"] for idx in indices}
    required_mode = str(config.get("data", {}).get("etf_price_mode", "continuous") or "")
    require_consistent = bool(config.get("data", {}).get("require_consistent_adjust", True))

    fetch_start = compute_fetch_start_date(start_date, warmup)
    etf_data = load_etf_history(
        fetcher,
        indices,
        fetch_start,
        force_refresh=False,
        allow_stale_cache=True,
    )
    issues = validate_etf_history_coverage(
        etf_data,
        indices,
        start_date,
        required_price_mode=required_mode if require_consistent and required_mode else None,
    )
    if issues:
        raise RuntimeError("; ".join(issues))

    benchmark = etf_data.get("000300.SH", pd.DataFrame())
    all_dates = list(etf_data.values())[0].index.tolist()
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    trade_dates = [d for d in all_dates if start_dt <= d <= end_dt]
    rebalance_dates = select_rebalance_dates(trade_dates, rebalance_freq)
    rebalance_set = set(rebalance_dates)
    last_rebalance = trade_dates[-6] if len(trade_dates) > 5 else trade_dates[-1]
    history_window = max(252, int(strategy.get("momentum_window", 126)) * 2)

    close_matrix = pd.DataFrame({code: df["close"].reindex(trade_dates) for code, df in etf_data.items()}, index=trade_dates)
    open_matrix = pd.DataFrame({code: df["open"].reindex(trade_dates) for code, df in etf_data.items()}, index=trade_dates)

    def score_candidate(item, date, benchmark_slice):
        code, df = item
        end_pos = df.index.searchsorted(date, side="right")
        hist_df = df.iloc[max(0, end_pos - history_window) : end_pos]
        if len(hist_df) < 20:
            return None
        return code, scorer.score_index(hist_df, benchmark_slice)

    pending = None
    daily_values = []
    executor = ThreadPoolExecutor(max_workers=workers) if workers > 1 else None
    try:
        for date in trade_dates:
            ds = date.strftime("%Y-%m-%d")
            open_prices = {code: float(price) for code, price in open_matrix.loc[date].dropna().items()}
            if pending and open_prices:
                portfolio.execute_signal(pending, open_prices, code_to_name, ds)
                pending = None

            prices = {code: float(price) for code, price in close_matrix.loc[date].dropna().items()}
            if prices and portfolio.positions and (not strict_weekly or date in rebalance_set):
                stop_loss_signals = portfolio.check_stop_loss(prices, ds)
                if any(stop_loss_signals.values()):
                    portfolio.execute_stop_loss(stop_loss_signals, prices, code_to_name, ds)

            if prices:
                portfolio.record_daily_value(ds, prices)
                daily_values.append({"date": ds, "value": portfolio.get_portfolio_value(prices)})

            if date in rebalance_set and date <= last_rebalance:
                scores_dict = {}
                benchmark_slice = benchmark
                if not benchmark.empty:
                    bench_end = benchmark.index.searchsorted(date, side="right")
                    benchmark_slice = benchmark.iloc[max(0, bench_end - history_window) : bench_end]
                iterator = (
                    executor.map(lambda item: score_candidate(item, date, benchmark_slice), etf_data.items())
                    if executor
                    else map(lambda item: score_candidate(item, date, benchmark_slice), etf_data.items())
                )
                for result in iterator:
                    if result is not None:
                        code, scores = result
                        scores_dict[code] = scores
                ranking = scorer.rank_indices(scores_dict)
                if ranking.empty:
                    continue
                signals = build_rebalance_signals(ranking, set(portfolio.positions.keys()), top_n, buffer_n)
                if signals["buy"] or signals["sell"]:
                    pending = signals
    finally:
        if executor:
            executor.shutdown(wait=True)
        fetcher.close()

    values_df = compute_backtest_metrics(pd.DataFrame(daily_values), 1_000_000)
    return RunResult(summary=values_df.attrs["summary"], trades=len(portfolio.trades))


def main():
    period_env = os.environ.get("TREND_PERIODS", "20240101-20260421")
    variant_env = os.environ.get("TREND_VARIANTS", "legacy,v1,recommended,minimal")
    periods = [
        tuple(period.split("-", 1))
        for period in period_env.split(",")
        if period.strip()
    ]
    variants = [variant.strip() for variant in variant_env.split(",") if variant.strip()]
    rows = []
    for start, end in periods:
        row = {"period": f"{start}-{end}"}
        for variant in variants:
            t0 = time.time()
            print(f"running {variant} {start}-{end}", file=sys.stderr, flush=True)
            result = run_period(start, end, variant)
            print(f"finished {variant} in {time.time() - t0:.1f}s", file=sys.stderr, flush=True)
            row[f"{variant}_return_pct"] = round(result.summary["total_return"] * 100, 2)
            row[f"{variant}_maxdd_pct"] = round(result.summary["max_drawdown"] * 100, 2)
            row[f"{variant}_sharpe"] = round(result.summary["sharpe"], 3)
            row[f"{variant}_trades"] = result.trades
            print(json.dumps(row, ensure_ascii=False), flush=True)
        rows.append(row)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
