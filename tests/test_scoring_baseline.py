import unittest

import pandas as pd

from src.scoring_baostock import ScoringEngine


class ScoringBaselineTests(unittest.TestCase):
    def test_total_score_uses_active_factors_only(self):
        config = {
            "factor_model": {
                "active_factors": ["momentum", "value"],
                "auxiliary_factors": ["flow"]
            },
            "factor_weights": {
                "momentum": 0.6,
                "value": 0.4,
                "flow": 1.0
            }
        }
        engine = ScoringEngine(config)
        data = pd.DataFrame({
            "close": [100 + i for i in range(260)],
            "volume": [1000 + i for i in range(260)],
            "amount": [100000 + i * 10 for i in range(260)]
        })
        scores = engine.score_index(data)
        expected = (
            scores["momentum"] * 0.6 +
            scores["value"] * 0.4
        ) / 1.0
        self.assertAlmostEqual(scores["total_score"], expected, places=6)


if __name__ == "__main__":
    unittest.main()
