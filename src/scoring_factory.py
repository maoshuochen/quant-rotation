"""
评分引擎工厂。

统一回测、日跑和看板的数据口径。
"""
from __future__ import annotations

from src.scoring_baostock import ScoringEngine


def create_scoring_engine(config: dict) -> ScoringEngine:
    return ScoringEngine(config)
