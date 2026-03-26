import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from src.data_fetcher_baostock import IndexDataFetcher


class NorthboundFlowTests(unittest.TestCase):
    def test_fetch_northbound_flow_uses_cache_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            fetcher = IndexDataFetcher(cache_dir=tmp)
            dates = pd.date_range("2026-03-20", periods=3, freq="D")
            fresh_df = pd.DataFrame(
                {
                    "net_flow": [10.0, 12.0, 8.0],
                    "buy_amount": [100.0, 110.0, 90.0],
                    "sell_amount": [90.0, 98.0, 82.0],
                },
                index=dates,
            )
            fetcher.baostock_fetcher.fetch_northbound_flow = MagicMock(return_value=fresh_df)

            first = fetcher.fetch_northbound_flow("20260320")
            self.assertEqual(len(first), 3)

            fetcher.baostock_fetcher.fetch_northbound_flow = MagicMock(side_effect=RuntimeError("boom"))
            second = fetcher.fetch_northbound_flow("20260320")
            self.assertEqual(len(second), 3)
            self.assertListEqual(second["net_flow"].tolist(), [10.0, 12.0, 8.0])


if __name__ == "__main__":
    unittest.main()
