#!/usr/bin/env python3
"""
运行主线健康检查。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config_loader import load_app_config

OUTPUTS_DIR = ROOT_DIR / "outputs" / "health"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    config = load_app_config(ROOT_DIR)
    ranking = read_json(ROOT_DIR / "outputs" / "frontend" / "ranking.json")
    if ranking is None:
        ranking = read_json(ROOT_DIR / "web" / "dist" / "ranking.json")

    backtest = read_json(ROOT_DIR / "outputs" / "frontend" / "backtest.json")
    if backtest is None:
        backtest = read_json(ROOT_DIR / "web" / "dist" / "backtest.json")

    report = {
      "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
      "config": {
        "indices": len(config.get("indices", [])),
        "active_factors": config.get("factor_model", {}).get("active_factors", []),
      },
      "artifacts": {
        "ranking_json": bool(ranking),
        "backtest_json": bool(backtest),
      },
      "health": ranking.get("health", {}) if ranking else {},
    }

    report["status"] = "ok" if all(report["artifacts"].values()) else "degraded"

    output_path = OUTPUTS_DIR / "latest.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
