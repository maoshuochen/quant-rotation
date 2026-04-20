"""
评分引擎工厂。

统一回测、日跑和看板的数据口径与评分模式选择。
"""
from __future__ import annotations

from typing import Any, Dict

from src.market_regime import DynamicWeightScoringEngine
from src.scoring_baostock import ScoringEngine


DEFAULT_SCORING_MODE = "dynamic"


def resolve_scoring_mode(config: Dict[str, Any]) -> str:
    factor_model = config.get("factor_model", {})
    mode = str(factor_model.get("scoring_mode", DEFAULT_SCORING_MODE) or DEFAULT_SCORING_MODE).strip().lower()
    if mode not in {"fixed", "dynamic"}:
        return DEFAULT_SCORING_MODE
    return mode


def create_scoring_engine(config: Dict[str, Any]) -> ScoringEngine:
    mode = resolve_scoring_mode(config)
    if mode == "dynamic":
        return DynamicWeightScoringEngine(config)
    return ScoringEngine(config)

