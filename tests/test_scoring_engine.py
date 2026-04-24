import math

import numpy as np
import pandas as pd

from src.market_regime import MarketRegimeDetector
from src.scoring_baostock import ScoringEngine
from src.scoring_factory import create_scoring_engine, resolve_scoring_mode


def make_price_frame(periods: int = 160) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=periods, freq="B")
    close = pd.Series(np.linspace(100.0, 140.0, periods), index=dates)
    volume = pd.Series(np.linspace(1_000_000, 1_800_000, periods), index=dates)
    amount = close * volume
    return pd.DataFrame(
        {
            "close": close,
            "open": close * 0.998,
            "high": close * 1.002,
            "low": close * 0.996,
            "volume": volume,
            "amount": amount,
        },
        index=dates,
    )


def base_config(mode: str = "dynamic") -> dict:
    return {
        "factor_model": {
            "scoring_mode": mode,
            "active_factors": ["strength", "trend", "flow"],
        },
        "factor_weights": {
            "strength": 0.235,
            "trend": 0.18,
            "flow": 0.585,
        },
        "flow_subfactor_weights": {
            "volume_trend": 0.35,
            "price_volume_corr": 0.10,
            "amount_trend": 0.35,
            "flow_intensity": 0.20,
        },
        "strength_blend": {
            "momentum": 0.5,
            "relative_strength": 0.5,
        },
    }


def test_flow_breakdown_is_real_and_matches_total():
    engine = ScoringEngine(base_config(mode="fixed"))
    frame = make_price_frame()
    benchmark = make_price_frame()

    scores = engine.score_index(frame, benchmark)
    breakdown = scores["attribution"]["flow_breakdown"]
    weights = scores["attribution"]["flow_weights"]

    expected = sum(breakdown[key] * weights[key] for key in breakdown) / sum(weights.values())

    assert set(breakdown) == {
        "volume_trend",
        "price_volume_corr",
        "amount_trend",
        "flow_intensity",
    }
    assert math.isclose(sum(weights.values()), 1.0, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(scores["flow"], expected, rel_tol=0, abs_tol=1e-6)


def test_trend_breakdown_is_continuous_and_matches_total():
    engine = ScoringEngine(base_config(mode="fixed"))
    frame = make_price_frame()
    benchmark = make_price_frame()

    scores = engine.score_index(frame, benchmark)
    breakdown = scores["attribution"]["trend_breakdown"]
    weights = scores["attribution"]["trend_weights"]

    expected = sum(breakdown[key] * weights[key] for key in breakdown) / sum(weights.values())

    assert set(breakdown) == {
        "price_vs_ma20",
        "price_vs_ma60",
        "ma20_vs_ma60",
        "ma20_slope",
    }
    assert scores["attribution"]["trend_overextension_penalty"] == 0.0
    assert math.isclose(scores["trend"], expected, rel_tol=0, abs_tol=1e-6)
    assert scores["trend"] not in {0.5, 0.75, 1.0}


def test_trend_score_improves_when_structure_gets_stronger():
    engine = ScoringEngine(base_config(mode="fixed"))
    dates = pd.date_range("2024-01-01", periods=80, freq="B")

    weak_prices = pd.Series(np.linspace(100.0, 99.0, len(dates)), index=dates)
    strong_prices = pd.Series(np.linspace(100.0, 130.0, len(dates)), index=dates)

    weak_score = engine.calc_trend_score(weak_prices)["score"]
    strong_score = engine.calc_trend_score(strong_prices)["score"]

    assert strong_score > weak_score
    assert 0.0 <= weak_score <= 1.0
    assert 0.0 <= strong_score <= 1.0


def test_trend_keeps_overextended_price_action_capped_without_penalty():
    engine = ScoringEngine(base_config(mode="fixed"))
    dates = pd.date_range("2024-01-01", periods=80, freq="B")

    healthy_prices = pd.Series(np.linspace(100.0, 118.0, len(dates)), index=dates)
    overheated_prices = pd.Series(np.linspace(100.0, 118.0, len(dates)), index=dates)
    overheated_prices.iloc[-1] = overheated_prices.iloc[-2] * 1.12

    healthy = engine.calc_trend_score(healthy_prices)
    overheated = engine.calc_trend_score(overheated_prices)

    assert overheated["metrics"]["overextension_penalty"] == 0.0
    assert overheated["details"]["price_vs_ma20"] <= 1.0
    assert overheated["score"] >= healthy["score"]


def test_dynamic_weights_apply_to_strength_factor():
    detector = MarketRegimeDetector()
    dynamic_weights = detector.get_dynamic_weights(
        "bull",
        {
            "strength": 0.235,
            "trend": 0.18,
            "flow": 0.585,
        },
    )

    assert set(dynamic_weights) == {"strength", "trend", "flow"}
    assert math.isclose(sum(dynamic_weights.values()), 1.0, rel_tol=0, abs_tol=1e-9)
    assert dynamic_weights["strength"] > dynamic_weights["trend"] > 0


def test_scoring_factory_resolves_fixed_and_dynamic_modes():
    dynamic_config = base_config(mode="dynamic")
    fixed_config = base_config(mode="fixed")

    dynamic_engine = create_scoring_engine(dynamic_config)
    fixed_engine = create_scoring_engine(fixed_config)

    assert resolve_scoring_mode(dynamic_config) == "dynamic"
    assert resolve_scoring_mode(fixed_config) == "fixed"
    assert hasattr(dynamic_engine, "update_market_regime")
    assert not hasattr(fixed_engine, "update_market_regime")
