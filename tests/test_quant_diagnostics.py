import tempfile
import unittest
from pathlib import Path

import pandas as pd

import scripts.run_quant_diagnostics as diagnostics


class QuantDiagnosticsTests(unittest.TestCase):
    def test_compute_ic_table_returns_empty_schema_for_empty_factor_df(self):
        result = diagnostics.compute_ic_table(pd.DataFrame(), ["momentum"], [5, 20])
        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns), diagnostics.IC_COLUMNS)

    def test_run_strategy_backtest_raises_when_benchmark_missing(self):
        with self.assertRaisesRegex(ValueError, "Benchmark 000300.SH not available"):
            diagnostics.run_strategy_backtest(
                name="missing_benchmark",
                config={"portfolio": {}, "strategy": {}, "factor_model": {}, "factor_weights": {}},
                etf_data={},
                indices=[],
                start_date="20240101",
                end_date="20240131",
                universe_codes=[],
                top_n=1,
                buffer_n=1,
                rebalance_frequency="weekly",
                commission_rate=0.0,
                slippage=0.0,
            )

    def test_get_rebalance_dates_uses_first_trading_day_when_monday_missing(self):
        trade_dates = [
            pd.Timestamp("2024-01-02"),
            pd.Timestamp("2024-01-03"),
            pd.Timestamp("2024-01-09"),
            pd.Timestamp("2024-01-16"),
            pd.Timestamp("2024-01-23"),
        ]
        weekly = diagnostics.get_rebalance_dates(trade_dates, "weekly")
        biweekly = diagnostics.get_rebalance_dates(trade_dates, "biweekly")
        self.assertEqual(weekly, [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-09"), pd.Timestamp("2024-01-16"), pd.Timestamp("2024-01-23")])
        self.assertEqual(biweekly, [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-16")])

    def test_write_report_includes_required_sections(self):
        report_data = {
            "ic": pd.DataFrame([{"factor": "momentum", "horizon": 5, "ic_mean": 0.1, "ic_std": 0.2, "ic_ir": 0.5, "positive_ratio": 0.6, "observations": 10}]),
            "quantiles": pd.DataFrame([{"factor": "momentum", "quantile": 1, "avg_forward_return": 0.01, "median_forward_return": 0.01, "count": 10}]),
            "factor_redundancy": pd.DataFrame([[1.0]], index=["momentum"], columns=["momentum"]),
            "ablation": pd.DataFrame([{"name": "ablation_full_model", "annual_return": 0.02}]),
            "parameter_sweep": pd.DataFrame([{"name": "param", "annual_return": 0.03}]),
            "oos": pd.DataFrame([{"name": "t5_b8_weekly", "train_return": 0.1, "test_return": 0.0, "train_sharpe": 1.0, "test_sharpe": 0.0, "train_rebalance_count": 8, "test_rebalance_count": 0}]),
            "universe": pd.DataFrame([{"name": "core_pool", "annual_return": 0.05}, {"name": "extended_pool", "annual_return": 0.02}]),
            "cost": pd.DataFrame([{"cost_bps": 20, "annual_return": 0.01}]),
            "rolling": pd.DataFrame([{"window_start": "2024-01-01", "window_end": "2024-06-30", "annual_return": 0.02}]),
            "regime": pd.DataFrame([{"regime": "sideways", "days": 20, "avg_daily_return": 0.0, "volatility": 0.1, "sharpe": 0.2, "total_return": 0.01}]),
        }
        summary_blob = {
            "baseline": {"annual_return": 0.02, "max_drawdown": -0.1, "sharpe": 0.3, "turnover_mean": 0.1, "avg_positions": 5, "avg_max_single_weight": 0.25, "avg_max_bucket_weight": 0.6, "stress_alpha_vs_benchmark": -0.01},
            "dynamic_vs_fixed": {"fixed_annual": 0.02, "dynamic_annual": 0.03},
            "oos": {"best_name": "t5_b8_weekly", "train_return": 0.1, "test_return": 0.0, "train_rebalance_count": 8, "test_rebalance_count": 0},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            original_path = diagnostics.REPORT_PATH
            diagnostics.REPORT_PATH = Path(tmpdir) / "report.md"
            try:
                diagnostics.write_report(report_data, summary_blob)
                content = diagnostics.REPORT_PATH.read_text(encoding="utf-8")
            finally:
                diagnostics.REPORT_PATH = original_path

        self.assertIn("## 最重要发现", content)
        self.assertIn("## OOS 明细", content)
        self.assertIn("## 因子冗余", content)
        self.assertIn("OOS 验证暂不成立", content)


if __name__ == "__main__":
    unittest.main()
