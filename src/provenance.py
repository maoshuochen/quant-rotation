"""
数据口径与生成元数据。

前端展示的回测结果必须能追溯到当前策略配置和代码版本。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


PROVENANCE_SCHEMA_VERSION = 1
BACKTEST_EXECUTION_MODEL_VERSION = 2


def _run_git(root_dir: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_git_metadata(root_dir: Path) -> dict:
    status = _run_git(root_dir, ["status", "--short"])
    commit = _run_git(root_dir, ["rev-parse", "HEAD"])
    branch = _run_git(root_dir, ["branch", "--show-current"])
    return {
        "commit": commit,
        "commit_short": commit[:8] if commit else "",
        "branch": branch,
        "dirty": bool(status),
    }


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def strategy_signature_payload(config: dict) -> dict:
    strategy = config.get("strategy", {})
    factor_model = config.get("factor_model", {})
    portfolio = config.get("portfolio", {})
    stop_loss = config.get("stop_loss", {})
    data = config.get("data", {})
    return _normalize(
        {
            "strategy": {
                "top_n": strategy.get("top_n"),
                "buffer_n": strategy.get("buffer_n"),
                "rebalance_frequency": strategy.get("rebalance_frequency"),
                "strict_weekly_execution": strategy.get("strict_weekly_execution"),
                "momentum_window": strategy.get("momentum_window"),
            },
            "factor_model": {
                "baseline_name": factor_model.get("baseline_name"),
                "scoring_mode": factor_model.get("scoring_mode", "fixed"),
                "active_factors": factor_model.get("active_factors", []),
                "auxiliary_factors": factor_model.get("auxiliary_factors", []),
            },
            "factor_weights": config.get("factor_weights", {}),
            "price_strength_model": config.get("price_strength_model", {}),
            "trend_subfactor_weights": config.get("trend_subfactor_weights", {}),
            "flow_subfactor_weights": config.get("flow_subfactor_weights", {}),
            "flow_model": config.get("flow_model", {}),
            "alpha_optimization": config.get("alpha_optimization", {}),
            "portfolio": {
                "initial_capital": portfolio.get("initial_capital"),
                "commission": portfolio.get("commission"),
                "slippage": portfolio.get("slippage"),
            },
            "stop_loss": stop_loss,
            "execution": {
                "model_version": BACKTEST_EXECUTION_MODEL_VERSION,
                "rebalance": "next_open_equal_weight_with_buffer_targets",
                "stop_loss": "close_signal_next_open_execution",
                "benchmarks": ["hs300", "equal_weight_all"],
            },
            "data": {
                "etf_price_mode": data.get("etf_price_mode"),
                "require_consistent_adjust": data.get("require_consistent_adjust"),
                "history_start_date": data.get("history_start_date"),
            },
        }
    )


def build_strategy_signature(config: dict) -> str:
    payload = strategy_signature_payload(config)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_run_metadata(
    *,
    root_dir: Path,
    config: dict,
    source: str,
    requested_start: str,
    requested_end: str,
    actual_start: str,
    actual_end: str,
    trading_days: int,
    summary: dict,
) -> dict:
    factor_model = config.get("factor_model", {})
    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "source": source,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "git": get_git_metadata(root_dir),
        "strategy_signature": build_strategy_signature(config),
        "strategy_signature_payload": strategy_signature_payload(config),
        "scoring_mode": factor_model.get("scoring_mode", "fixed"),
        "requested_period": {
            "start": requested_start,
            "end": requested_end,
        },
        "actual_period": {
            "start": actual_start,
            "end": actual_end,
        },
        "trading_days": trading_days,
        "summary": summary,
    }
