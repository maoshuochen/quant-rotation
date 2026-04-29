#!/usr/bin/env python3
"""
校验后端回测结果、前端 public 数据和 site 发布产物是否一致。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.backtest_utils import compute_backtest_metrics, load_strategy_config
from src.provenance import build_strategy_signature


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"缺少文件：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_close(label: str, actual: float, expected: float, tol: float = 1e-4) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=tol):
        raise RuntimeError(f"{label} 不一致：actual={actual}, expected={expected}")


def _validate_payload(path: Path, expected_summary: dict, expected_metadata: dict) -> None:
    payload = _read_json(path)
    backtest = payload.get("backtest", payload)
    summary = backtest.get("summary", {})
    metadata = backtest.get("metadata") or payload.get("metadata", {}).get("backtest", {})

    if not summary:
        raise RuntimeError(f"{path} 缺少 backtest summary")
    if not metadata:
        raise RuntimeError(f"{path} 缺少 backtest metadata")

    _assert_close(f"{path} total_return", summary.get("total_return"), expected_summary["total_return"])
    _assert_close(f"{path} final_value", summary.get("final_value"), expected_summary["final_value"], tol=0.1)
    _assert_close(f"{path} max_drawdown", summary.get("max_drawdown"), expected_summary["max_drawdown"])

    if metadata.get("strategy_signature") != expected_metadata.get("strategy_signature"):
        raise RuntimeError(f"{path} strategy_signature 不一致")
    if metadata.get("scoring_mode") != expected_metadata.get("scoring_mode"):
        raise RuntimeError(f"{path} scoring_mode 不一致")
    if metadata.get("actual_period") != expected_metadata.get("actual_period"):
        raise RuntimeError(f"{path} actual_period 不一致")
    if int(metadata.get("trading_days", 0)) != int(expected_metadata.get("trading_days", 0)):
        raise RuntimeError(f"{path} trading_days 不一致")


def main() -> None:
    config = load_strategy_config(ROOT_DIR)
    expected_signature = build_strategy_signature(config)

    current_path = ROOT_DIR / "backtest_results" / "current.parquet"
    metadata_path = ROOT_DIR / "backtest_results" / "current.meta.json"
    benchmark_path = ROOT_DIR / "backtest_results" / "current.benchmarks.json"
    if not current_path.exists():
        raise RuntimeError("缺少 backtest_results/current.parquet")

    df = pd.read_parquet(current_path)
    values = compute_backtest_metrics(df, config.get("portfolio", {}).get("initial_capital", 1_000_000))
    summary = values.attrs["summary"]
    expected_summary = {
        "final_value": round(float(summary["final_value"]), 2),
        "total_return": round(float(summary["total_return"]), 4),
        "max_drawdown": round(float(summary["max_drawdown"]), 4),
    }

    metadata = _read_json(metadata_path)
    benchmarks = _read_json(benchmark_path)
    if metadata.get("strategy_signature") != expected_signature:
        raise RuntimeError("current.meta.json 与当前策略配置不一致")

    actual_period = {
        "start": values["date"].iloc[0].strftime("%Y-%m-%d"),
        "end": values["date"].iloc[-1].strftime("%Y-%m-%d"),
    }
    if metadata.get("actual_period") != actual_period:
        raise RuntimeError("current.meta.json 与 current.parquet 区间不一致")
    if int(metadata.get("trading_days", 0)) != len(values):
        raise RuntimeError("current.meta.json 与 current.parquet 交易日数量不一致")

    for path in [
        ROOT_DIR / "web" / "public" / "backtest.json",
        ROOT_DIR / "web" / "public" / "data.json",
        ROOT_DIR / "site" / "backtest.json",
        ROOT_DIR / "site" / "data.json",
    ]:
        _validate_payload(path, expected_summary, metadata)
        payload = _read_json(path)
        backtest = payload.get("backtest", payload)
        payload_benchmarks = backtest.get("benchmarks", {})
        if payload_benchmarks.get("summary") != benchmarks.get("summary"):
            raise RuntimeError(f"{path} benchmark summary 不一致")

    print("数据一致性校验通过")
    print(
        f"  total_return={expected_summary['total_return']:.2%}, "
        f"period={actual_period['start']}~{actual_period['end']}, "
        f"signature={expected_signature[:12]}"
    )


if __name__ == "__main__":
    main()
