"""
统一策略摘要层。

负责把 daily run、诊断产物和前端展示需要的结论收敛为同一份结构化摘要。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional


def _safe_float(value, fallback: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_csv_rows(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_diagnostics_bundle(root_dir: Path) -> dict:
    base = root_dir / "outputs" / "diagnostics"
    summary = _read_json(base / "summary.json") or {}
    oos_rows = _read_csv_rows(base / "oos.csv")
    universe_rows = _read_csv_rows(base / "universe.csv")
    cost_rows = _read_csv_rows(base / "cost.csv")
    return {
        "summary": summary,
        "oos_rows": oos_rows,
        "universe_rows": universe_rows,
        "cost_rows": cost_rows,
    }


def compute_data_health_summary(health: dict) -> dict:
    statuses = [
        health.get("price_data", {}).get("status"),
        health.get("northbound", {}).get("status"),
        health.get("etf_shares", {}).get("status"),
    ]
    if "missing" in statuses:
        overall = "missing"
    elif "degraded" in statuses:
        overall = "degraded"
    elif "snapshot" in statuses:
        overall = "snapshot"
    else:
        overall = "ok"

    copy = {
        "ok": "数据链完整，结果可正常参考",
        "degraded": "部分数据降级，结论需结合人工复核",
        "snapshot": "份额数据以快照为主，适合作辅助判断",
        "missing": "关键数据缺失，不建议直接执行",
        "unknown": "数据状态未评估",
    }
    warnings = []
    if health.get("price_data", {}).get("stale_codes"):
        warnings.append(f"价格数据存在滞后标的：{'、'.join(health['price_data']['stale_codes'])}")
    if health.get("etf_shares", {}).get("missing_codes"):
        warnings.append(f"ETF 份额缺失标的：{'、'.join(health['etf_shares']['missing_codes'])}")
    northbound = health.get("northbound", {})
    if northbound.get("status") == "degraded" and northbound.get("latest_valid_date"):
        warnings.append(
            f"北向资金历史最近有效日期 {northbound.get('latest_valid_date')}，最近连续窗口 {northbound.get('recent_rows', 0)} 日"
        )

    return {
        "status": overall,
        "label": copy.get(overall, copy["unknown"]),
        "warnings": warnings,
        "items": [
            {
                "label": "价格数据",
                "status": health.get("price_data", {}).get("status", "unknown"),
                "detail": f"{health.get('price_data', {}).get('available_count', 0)}/{health.get('price_data', {}).get('expected_count', 0)}",
            },
            {
                "label": "北向资金",
                "status": northbound.get("status", "unknown"),
                "detail": (
                    f"历史 {northbound.get('rows', 0)} 日，最近连续 {northbound.get('recent_rows', 0)} 日"
                    if northbound.get("latest_valid_date")
                    else f"{northbound.get('rows', 0)} rows"
                ),
            },
            {
                "label": "ETF 份额",
                "status": health.get("etf_shares", {}).get("status", "unknown"),
                "detail": f"历史 {health.get('etf_shares', {}).get('history_count', 0)} / 快照 {health.get('etf_shares', {}).get('snapshot_count', 0)}",
            },
        ],
    }


def compute_validation_summary(diagnostics_bundle: dict, backtest_summary: Optional[dict] = None) -> dict:
    summary = diagnostics_bundle.get("summary", {})
    baseline = summary.get("baseline", {})
    dynamic = summary.get("dynamic_vs_fixed", {})
    oos = dict(summary.get("oos", {}))

    if not oos.get("train_rebalance_count") and diagnostics_bundle.get("oos_rows"):
        best_name = oos.get("best_name")
        for row in diagnostics_bundle["oos_rows"]:
            if not best_name or row.get("name") == best_name:
                oos["train_rebalance_count"] = int(_safe_float(row.get("train_rebalance_count"), 0))
                oos["test_rebalance_count"] = int(_safe_float(row.get("test_rebalance_count"), 0))
                oos["test_return"] = _safe_float(row.get("test_return"), _safe_float(oos.get("test_return"), 0.0))
                break

    annual = _safe_float(baseline.get("annual_return"))
    drawdown = _safe_float(baseline.get("max_drawdown"))
    sharpe = _safe_float(baseline.get("sharpe"))
    test_rebalances = int(_safe_float(oos.get("test_rebalance_count"), 0))
    fixed_annual = _safe_float(dynamic.get("fixed_annual"), annual)
    dynamic_annual = _safe_float(dynamic.get("dynamic_annual"), annual)

    if not baseline and backtest_summary:
        annual = _safe_float(backtest_summary.get("annual_return"))
        drawdown = _safe_float(backtest_summary.get("max_drawdown"))
        sharpe = _safe_float(backtest_summary.get("sharpe_ratio"))

    if test_rebalances < 3:
        status = "insufficient"
        label = "验证不足"
        rating = "观察"
        action = "继续研究，不建议单独实盘"
    elif annual > 0.10 and sharpe > 0.6 and drawdown > -0.18:
        status = "pilot"
        label = "初步验证"
        rating = "可小仓位试运行"
        action = "冻结基线后做小仓位跟踪"
    elif annual > 0.05 and sharpe > 0.4 and drawdown > -0.22:
        status = "observing"
        label = "初步验证"
        rating = "观察"
        action = "缩小标的池并继续验证"
    else:
        status = "weak"
        label = "验证不足"
        rating = "弱"
        action = "先优化模型与标的池"

    warnings = []
    if test_rebalances < 3:
        warnings.append("OOS 测试窗口过短，当前样本外结论不具统计解释力")
    if annual <= 0:
        warnings.append("研究基线年化为非正，当前模型不适合直接执行")
    if drawdown <= -0.20:
        warnings.append("研究基线最大回撤超过 20%，风险约束仍偏弱")
    if dynamic_annual <= fixed_annual:
        warnings.append("动态权重未优于固定权重，不应将其解读为已验证的 regime 模型")

    return {
        "status": status,
        "label": label,
        "rating": rating,
        "action": action,
        "warnings": warnings,
        "metrics": {
            "research_annual_return": annual,
            "research_max_drawdown": drawdown,
            "research_sharpe": sharpe,
            "fixed_annual_return": fixed_annual,
            "dynamic_annual_return": dynamic_annual,
            "oos_best_name": oos.get("best_name", ""),
            "oos_train_return": _safe_float(oos.get("train_return")),
            "oos_test_return": _safe_float(oos.get("test_return")),
            "oos_train_rebalance_count": int(_safe_float(oos.get("train_rebalance_count"), 0)),
            "oos_test_rebalance_count": test_rebalances,
        },
    }


def compute_universe_summary(indices: Iterable[dict], inactive_indices: Iterable[dict], diagnostics_bundle: dict) -> dict:
    indices = list(indices)
    inactive_indices = list(inactive_indices)
    bucket_counts: Dict[str, int] = {}
    for idx in indices:
        bucket = idx.get("bucket", "unknown")
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    preferred_pool = ""
    pool_message = ""
    universe_rows = diagnostics_bundle.get("universe_rows", [])
    if len(universe_rows) >= 2:
        sorted_rows = sorted(universe_rows, key=lambda row: _safe_float(row.get("annual_return")), reverse=True)
        preferred_pool = sorted_rows[0].get("name", "")
        if preferred_pool and sorted_rows[0].get("name") != sorted_rows[-1].get("name"):
            pool_message = (
                f"{'核心池' if preferred_pool == 'core_pool' else preferred_pool} 当前优于 "
                f"{'扩展池' if sorted_rows[-1].get('name') == 'extended_pool' else sorted_rows[-1].get('name')}"
            )

    return {
        "active_count": len(indices),
        "inactive_count": len(inactive_indices),
        "core_count": bucket_counts.get("core", 0),
        "sector_count": bucket_counts.get("sector", 0),
        "satellite_count": bucket_counts.get("satellite", 0),
        "preferred_pool": preferred_pool,
        "pool_message": pool_message,
    }


def build_strategy_summary(
    *,
    root_dir: Path,
    indices: Iterable[dict],
    inactive_indices: Iterable[dict],
    recommendation: dict,
    health: dict,
    update_time: str,
    backtest_summary: Optional[dict] = None,
) -> dict:
    diagnostics_bundle = load_diagnostics_bundle(root_dir)
    data_health = compute_data_health_summary(health)
    validation = compute_validation_summary(diagnostics_bundle, backtest_summary)
    universe = compute_universe_summary(indices, inactive_indices, diagnostics_bundle)

    holdings = recommendation.get("holdings", [])
    signals = recommendation.get("signals", [])
    top_names = "、".join(item.get("name", item.get("code", "")) for item in holdings[:3])
    if signals:
        execution_message = f"当前建议执行 {len(signals)} 个动作，优先关注 {top_names or '头部候选'}。"
    else:
        execution_message = f"当前无新增调仓动作，继续跟踪 {top_names or '头部候选'}。"

    warnings = [*data_health.get("warnings", []), *validation.get("warnings", [])]
    if universe.get("pool_message"):
        warnings.append(universe["pool_message"])

    return {
        "updated_at": update_time,
        "decision": {
            "headline": f"本周主结论：{top_names or '等待新信号'} 为当前优先观察方向。",
            "execution_message": execution_message,
            "action": validation.get("action", ""),
        },
        "data_health": data_health,
        "validation": validation,
        "universe": universe,
        "performance": {
            "recent_backtest": backtest_summary or {},
            "research": validation.get("metrics", {}),
        },
        "warnings": warnings,
    }
