import tempfile
import unittest
from pathlib import Path

from src.config_loader import load_app_config


class ConfigLoaderTests(unittest.TestCase):
    def test_split_config_overrides_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "config.yaml").write_text("strategy:\n  top_n: 3\nfactor_weights:\n  momentum: 0.2\n", encoding="utf-8")
            (config_dir / "strategy.yaml").write_text(
                "strategy:\n  top_n: 5\nfactor_model:\n  active_factors: [momentum, trend]\n",
                encoding="utf-8"
            )
            config = load_app_config(root)
            self.assertEqual(config["strategy"]["top_n"], 5)
            self.assertEqual(config["factor_model"]["active_factors"], ["momentum", "trend"])


if __name__ == "__main__":
    unittest.main()
