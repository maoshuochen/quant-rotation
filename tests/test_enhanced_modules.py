"""
测试验证模块
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from src.validation import OutOfSampleValidator, create_oos_validator
from src.risk_manager import RiskManager, create_risk_manager
from src.factor_engine_enhanced import EnhancedFactorEngine, create_factor_engine
from src.data_sources.cache_manager import CacheManager
from src.data_quality import DataQualityChecker, create_quality_checker


class TestOutOfSampleValidator:
    """测试样本外验证器"""

    def setup_method(self):
        self.validator = create_oos_validator(oos_ratio=0.3)

        # 生成模拟数据
        np.random.seed(42)
        n_days = 500
        dates = pd.date_range('2024-01-01', periods=n_days, freq='D')
        returns = pd.Series(np.random.randn(n_days) * 0.02 + 0.0005, index=dates, name='return')

        self.data = pd.DataFrame({'date': dates, 'return': returns.values})

    def test_split_train_oos(self):
        train, oos = self.validator.split_train_oos(self.data)
        assert len(train) > 0
        assert len(oos) > 0
        assert len(train) + len(oos) == len(self.data)

    def test_validate_strategy(self):
        def dummy_strategy(data, **params):
            return data['return'] if 'return' in data.columns else pd.Series()

        result = self.validator.validate_strategy(dummy_strategy, self.data)
        assert hasattr(result, 'train_sharpe')
        assert hasattr(result, 'oos_sharpe')
        assert hasattr(result, 'is_robust')

    def test_walk_forward(self):
        def dummy_strategy(data, **params):
            return data['return']

        wf_result = self.validator.walk_forward_analysis(
            dummy_strategy, self.data, window_size=200, step_size=50, oos_size=50
        )
        assert len(wf_result.windows) > 0
        assert hasattr(wf_result, 'avg_oos_sharpe')
        assert hasattr(wf_result, 'consistency_ratio')


class TestRiskManager:
    """测试风险管理器"""

    def setup_method(self):
        self.risk_manager = create_risk_manager()
        np.random.seed(42)
        self.returns = pd.Series(np.random.randn(252) * 0.02, name='return')

    def test_calculate_var(self):
        var_95 = self.risk_manager.calculate_var(self.returns, 'historical', 0.95)
        assert isinstance(var_95, float)
        assert var_95 < 0  # VaR 应该是负数 (损失)

    def test_calculate_cvar(self):
        cvar_95 = self.risk_manager.calculate_cvar(self.returns, 0.95)
        assert isinstance(cvar_95, float)
        assert cvar_95 <= self.risk_manager.calculate_var(self.returns, 'historical', 0.95)

    def test_risk_parity_weights(self):
        np.random.seed(42)
        returns_matrix = pd.DataFrame({
            'A': np.random.randn(252) * 0.02,
            'B': np.random.randn(252) * 0.02,
            'C': np.random.randn(252) * 0.02
        })
        weights = self.risk_manager.risk_parity_weights(returns_matrix)
        assert len(weights) == 3
        assert abs(sum(weights.values()) - 1.0) < 0.01


class TestEnhancedFactorEngine:
    """测试增强因子引擎"""

    def setup_method(self):
        self.engine = create_factor_engine(winsorize_method='mad', normalize_method='robust')
        np.random.seed(42)
        self.factor = pd.Series(np.random.randn(252) * 10 + 50, name='factor')

    def test_winsorize(self):
        winsorized = self.engine.winsorize(self.factor)
        assert len(winsorized) == len(self.factor)
        # 去极值后应该没有极端值
        assert abs(winsorized.max() - winsorized.median()) < abs(self.factor.max() - self.factor.median())

    def test_normalize(self):
        normalized = self.engine.normalize(self.factor)
        assert len(normalized) == len(self.factor)
        # RobustScaler 归一化后中位数应该接近 0
        assert abs(normalized.median()) < 0.1

    def test_full_process(self):
        processed = self.engine.process(self.factor)
        assert len(processed) == len(self.factor)


class TestDataQualityChecker:
    """测试数据质量检查器"""

    def setup_method(self):
        self.checker = create_quality_checker()

        # 正常数据
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        self.good_data = pd.DataFrame({
            'date': dates,
            'close': 100 + np.cumsum(np.random.randn(252) * 0.02),
            'volume': np.random.randint(1000, 10000, 252)
        })

    def test_check_missing_values(self):
        result = self.checker.check_missing_values(self.good_data)
        assert 'column_info' in result
        assert result['overall_ok'] == True

    def test_check_continuity(self):
        result = self.checker.check_continuity(self.good_data, 'date')
        assert 'is_continuous' in result
        assert result['is_continuous'] == True

    def test_full_check(self):
        result = self.checker.full_check(self.good_data)
        assert 'overall_quality' in result
        assert result['overall_quality'] in ['PASS', 'NEEDS_REVIEW']


class TestCacheManager:
    """测试缓存管理器"""

    def setup_method(self, tmp_path):
        self.cache = CacheManager(
            parquet_dir=str(tmp_path / "parquet"),
            sqlite_path=str(tmp_path / "metadata.db"),
            default_ttl_hours=24
        )

    def test_write_and_read(self, tmp_path):
        df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        self.cache.write("test_key", df)

        cached = self.cache.read("test_key")
        assert cached is not None
        assert len(cached) == 3

    def test_invalidate(self, tmp_path):
        df = pd.DataFrame({'a': [1, 2, 3]})
        self.cache.write("test_key", df)
        self.cache.invalidate("test_key")

        cached = self.cache.read("test_key")
        assert cached is None

    def test_get_stats(self, tmp_path):
        stats = self.cache.get_stats()
        assert 'total_keys' in stats
        assert 'total_size_mb' in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
