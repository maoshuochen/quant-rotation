import unittest
from unittest.mock import patch

import pandas as pd

from src.strategy_baostock import RotationStrategy


class StrategyRecommendationTests(unittest.TestCase):
    def test_build_recommendation_outputs_holdings(self):
        with patch("src.strategy_baostock.IndexDataFetcher") as fetcher_cls:
            fetcher_cls.return_value.close.return_value = None
            strategy = RotationStrategy(config={
                "indices": [
                    {"code": "A", "name": "Alpha", "etf": "510001"},
                    {"code": "B", "name": "Beta", "etf": "510002"}
                ],
                "strategy": {"top_n": 1, "buffer_n": 2},
                "factor_model": {"active_factors": ["momentum", "trend"], "auxiliary_factors": ["flow"]},
                "factor_weights": {"momentum": 0.5, "trend": 0.5, "flow": 0.1},
                "portfolio": {}
            })
        ranking = pd.DataFrame([
            {"code": "A", "total_score": 0.8, "rank": 1, "momentum": 0.9, "trend": 0.7, "flow": 0.4},
            {"code": "B", "total_score": 0.5, "rank": 2, "momentum": 0.4, "trend": 0.6, "flow": 0.3},
        ])
        result = strategy.build_recommendation(ranking, [{"action": "buy", "code": "A"}])
        self.assertEqual(result["selected_codes"], ["A"])
        self.assertEqual(result["holdings"][0]["name"], "Alpha")
        self.assertEqual(result["signals"][0]["action"], "buy")
        strategy.close()


if __name__ == "__main__":
    unittest.main()
