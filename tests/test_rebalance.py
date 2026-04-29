import pandas as pd

from src.backtest_utils import build_rebalance_targets
from src.portfolio import Position, SimulatedPortfolio


def test_build_rebalance_targets_keeps_buffer_holdings_after_top_n():
    ranking = pd.DataFrame(
        {
            "code": ["A", "B", "C", "D", "E"],
            "score": [5, 4, 3, 2, 1],
        }
    )

    targets = build_rebalance_targets(
        ranking,
        current_codes={"D", "E"},
        top_n=2,
        buffer_n=4,
    )

    assert targets == ["A", "B", "D"]


def test_execute_rebalance_reweights_existing_positions_to_targets():
    portfolio = SimulatedPortfolio(initial_capital=1_000, commission_rate=0.0, slippage=0.0)
    portfolio.cash = 0.0
    portfolio.positions = {
        "A": Position("A", "Alpha", 80, 10.0, "2024-01-01", 10.0),
        "B": Position("B", "Beta", 10, 10.0, "2024-01-01", 10.0),
        "C": Position("C", "Gamma", 10, 10.0, "2024-01-01", 10.0),
    }

    trades = portfolio.execute_rebalance(
        ["A", "B"],
        {"A": 10.0, "B": 10.0, "C": 10.0},
        {"A": "Alpha", "B": "Beta", "C": "Gamma"},
        "2024-01-08",
        min_trade_value=0.0,
    )

    assert [(trade.type, trade.code, trade.shares) for trade in trades] == [
        ("sell", "A", 30),
        ("sell", "C", 10),
        ("buy", "B", 40),
    ]
    assert portfolio.cash == 0.0
    assert portfolio.positions["A"].shares == 50
    assert portfolio.positions["B"].shares == 50
    assert "C" not in portfolio.positions
