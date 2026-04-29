#!/usr/bin/env python3
"""
逐项回测超额收益优化实验。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scripts.backtest_baostock import _compute_benchmark_curves, run_backtest
from src.backtest_utils import load_strategy_config


START_DATE = "20240102"
END_DATE = "20260428"
INITIAL_CAPITAL = 1_000_000


def _set_nested(config: dict, path: tuple[str, ...], value) -> None:
    node = config
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value


def _alpha_metrics(values: pd.DataFrame) -> dict:
    chart, benchmarks = _compute_benchmark_curves(
        values.attrs["close_matrix"],
        INITIAL_CAPITAL,
        values,
    )
    frame = pd.DataFrame(chart)
    strategy = 1 + frame["strategy"]
    equal = 1 + frame["equal_weight_all"]
    hs300 = 1 + frame["hs300"]
    relative = strategy / equal
    relative_dd = relative / relative.cummax() - 1

    strategy_ret = strategy.pct_change().fillna(0)
    equal_ret = equal.pct_change().fillna(0)
    excess_ret = strategy_ret - equal_ret
    information_ratio = (
        excess_ret.mean() / excess_ret.std() * (252 ** 0.5)
        if excess_ret.std() > 0
        else 0.0
    )
    monthly = frame.assign(date=pd.to_datetime(frame["date"])).set_index("date")
    monthly = monthly.resample("ME").last().pct_change().dropna()
    win_months = int((monthly["strategy"] > monthly["equal_weight_all"]).sum())
    total_months = int(len(monthly))

    return {
        "total_return": float(values.attrs["summary"]["total_return"]),
        "annual_return": float(values.attrs["summary"]["annual_return"]),
        "max_drawdown": float(values.attrs["summary"]["max_drawdown"]),
        "sharpe": float(values.attrs["summary"]["sharpe"]),
        "excess_equal": float(strategy.iloc[-1] - equal.iloc[-1]),
        "excess_hs300": float(strategy.iloc[-1] - hs300.iloc[-1]),
        "relative_max_drawdown": float(relative_dd.min()),
        "information_ratio": float(information_ratio),
        "win_month_rate": win_months / total_months if total_months else 0.0,
        "equal_total_return": float(benchmarks["equal_weight_all"]["total_return"]),
        "hs300_total_return": float(benchmarks["hs300"]["total_return"]),
    }


def _run_variant(name: str, base_config: dict, changes: list[tuple[tuple[str, ...], object]]) -> dict:
    config = copy.deepcopy(base_config)
    for path, value in changes:
        _set_nested(config, path, value)
    print(f"\n\n### {name}")
    values = run_backtest(
        START_DATE,
        END_DATE,
        INITIAL_CAPITAL,
        config_override=config,
        write_outputs=False,
    )
    values.attrs["variant_name"] = name
    return {"name": name, **_alpha_metrics(values)}


def main() -> None:
    base = load_strategy_config(ROOT_DIR)
    variants = [
        ("baseline", []),
        (
            "01_rs_equal_weight_all",
            [(("alpha_optimization", "relative_strength_benchmark"), "equal_weight_all")],
        ),
        (
            "02_rs_equal_plus_overheat",
            [
                (("alpha_optimization", "relative_strength_benchmark"), "equal_weight_all"),
                (("alpha_optimization", "overheat_penalty", "enabled"), True),
            ],
        ),
        (
            "03_plus_conditional_flow",
            [
                (("alpha_optimization", "relative_strength_benchmark"), "equal_weight_all"),
                (("alpha_optimization", "overheat_penalty", "enabled"), True),
                (("alpha_optimization", "conditional_flow", "enabled"), True),
            ],
        ),
        (
            "04_plus_score_confidence_weighting",
            [
                (("alpha_optimization", "relative_strength_benchmark"), "equal_weight_all"),
                (("alpha_optimization", "overheat_penalty", "enabled"), True),
                (("alpha_optimization", "conditional_flow", "enabled"), True),
                (("alpha_optimization", "target_weighting", "mode"), "score_confidence"),
            ],
        ),
    ]

    rows = [_run_variant(name, base, changes) for name, changes in variants]
    result = pd.DataFrame(rows)
    result = result.sort_values(
        ["information_ratio", "excess_equal", "relative_max_drawdown"],
        ascending=[False, False, False],
    )
    output = ROOT_DIR / "reports" / "alpha_optimization_results.csv"
    result.to_csv(output, index=False)

    print("\n\n=== Alpha optimization summary ===")
    display_cols = [
        "name",
        "total_return",
        "excess_equal",
        "relative_max_drawdown",
        "information_ratio",
        "win_month_rate",
        "max_drawdown",
        "sharpe",
    ]
    print(result[display_cols].to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()
