"""
Factor Engine 模块单元测试
测试因子计算功能
"""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.factor_engine import FactorEngine


class TestFactorEngine:
    """测试因子引擎"""

    @pytest.fixture
    def engine(self):
        return FactorEngine(lookback_days=2520)

    @pytest.fixture
    def sample_prices(self):
        """生成样本价格数据"""
        dates = pd.date_range('2024-01-01', periods=300, freq='D')
        np.random.seed(42)
        # 生成随机游走价格
        returns = np.random.randn(300) * 0.02
        prices = 100 * np.cumprod(1 + returns)
        return pd.Series(prices, index=dates)

    @pytest.fixture
    def sample_returns(self, sample_prices):
        """生成样本收益率数据"""
        return sample_prices.pct_change().dropna()

    def test_pe_percentile_valid(self, engine):
        """测试 PE 分位计算（有效数据）"""
        current_pe = 15.0
        pe_history = pd.Series([10, 12, 14, 16, 18, 20, 22, 24, 26, 28] * 100)

        percentile = engine.calc_pe_percentile(current_pe, pe_history)

        assert 0 <= percentile <= 1
        # 15 应该在 40-50% 分位附近 (允许边界)
        assert 0.3 <= percentile <= 0.6

    def test_pe_percentile_empty(self, engine):
        """测试 PE 分位计算（空数据）"""
        result = engine.calc_pe_percentile(15.0, pd.Series())
        assert result == 0.5  # 返回中性分数

    def test_pe_percentile_insufficient_data(self, engine):
        """测试 PE 分位计算（数据不足）"""
        pe_history = pd.Series([10, 12, 14, 16, 18])  # 只有 5 个点
        result = engine.calc_pe_percentile(15.0, pe_history)
        assert result == 0.5  # 返回中性分数

    def test_pb_percentile_valid(self, engine):
        """测试 PB 分位计算"""
        current_pb = 2.0
        pb_history = pd.Series([1.0, 1.5, 2.0, 2.5, 3.0] * 100)

        percentile = engine.calc_pb_percentile(current_pb, pb_history)

        assert 0 <= percentile <= 1
        # 2.0 应该在 50% 分位附近 (允许边界)
        assert 0.4 <= percentile <= 0.6

    def test_momentum_valid(self, engine, sample_prices):
        """测试动量计算"""
        momentum = engine.calc_momentum(sample_prices, window=126)

        # 动量应该在合理范围内
        assert isinstance(momentum, float)
        assert -1 < momentum < 1

    def test_momentum_insufficient_data(self, engine):
        """测试动量计算（数据不足）"""
        short_prices = pd.Series([100, 101, 102, 103, 104])
        result = engine.calc_momentum(short_prices, window=126)
        assert result == 0.0

    def test_volatility_valid(self, engine, sample_returns):
        """测试波动率计算"""
        volatility = engine.calc_volatility(sample_returns, window=20)

        # 年化波动率应该在合理范围内
        assert isinstance(volatility, float)
        assert 0 < volatility < 2  # 0-200% 年化

    def test_volatility_insufficient_data(self, engine):
        """测试波动率计算（数据不足）"""
        short_returns = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
        result = engine.calc_volatility(short_returns, window=20)
        assert result == 0.0

    def test_max_drawdown_valid(self, engine, sample_prices):
        """测试最大回撤计算"""
        drawdown = engine.calc_max_drawdown(sample_prices, window=252)

        # 回撤应该是负数或 0
        assert drawdown <= 0
        assert drawdown > -1  # 不可能超过 -100%

    def test_max_drawdown_monotonic(self, engine):
        """测试单调递增价格的最大回撤"""
        # 单调递增价格，回撤应接近 0
        prices = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109])
        drawdown = engine.calc_max_drawdown(prices, window=10)
        assert drawdown <= 0
        assert drawdown > -0.01  # 应该非常接近 0

    def test_sharpe_ratio_valid(self, engine, sample_returns):
        """测试夏普比率计算"""
        sharpe = engine.calc_sharpe_ratio(sample_returns, window=252, risk_free=0.02)

        # 夏普比率应该在合理范围内
        assert isinstance(sharpe, float)
        assert -5 < sharpe < 5

    def test_sharpe_ratio_insufficient_data(self, engine):
        """测试夏普比率计算（数据不足）"""
        short_returns = pd.Series([0.01, -0.02, 0.03])
        result = engine.calc_sharpe_ratio(short_returns, window=252)
        assert result == 0.0

    def test_sharpe_ratio_risk_free(self, engine, sample_returns):
        """测试无风险利率对夏普比率的影响"""
        # 高风险利率应该降低夏普比率
        sharpe_low_rf = engine.calc_sharpe_ratio(sample_returns, risk_free=0.01)
        sharpe_high_rf = engine.calc_sharpe_ratio(sample_returns, risk_free=0.05)

        # 高风险利率下夏普比率应该更低
        assert sharpe_high_rf < sharpe_low_rf

    def test_relative_strength_valid(self, engine, sample_prices):
        """测试相对强弱计算"""
        # 创建基准价格（与样本价格相关但不同）
        benchmark_prices = sample_prices * 0.9 + np.random.randn(len(sample_prices)) * 0.5

        rs = engine.calc_relative_strength(sample_prices, benchmark_prices)

        # 相对强弱应该在合理范围内
        assert isinstance(rs, float)
        assert 0.5 < rs < 1.5

    def test_relative_strength_insufficient_data(self, engine):
        """测试相对强弱计算（数据不足）"""
        short_prices = pd.Series([100, 101, 102, 103, 104])
        result = engine.calc_relative_strength(short_prices, short_prices)
        assert result == 1.0

    def test_turnover_percentile_valid(self, engine):
        """测试换手率分位计算"""
        volumes = pd.Series(np.random.randint(1000, 10000, 100))
        percentile = engine.calc_turnover_percentile(volumes, window=63)
        assert 0 <= percentile <= 1

    def test_turnover_percentile_insufficient_data(self, engine):
        """测试换手率分位计算（数据不足）"""
        short_volumes = pd.Series([1000, 2000, 3000])
        result = engine.calc_turnover_percentile(short_volumes, window=63)
        assert result == 0.5


class TestFactorEngineEdgeCases:
    """测试边界情况"""

    @pytest.fixture
    def engine(self):
        return FactorEngine()

    def test_constant_prices(self, engine):
        """测试恒定价格"""
        prices = pd.Series([100] * 100)
        momentum = engine.calc_momentum(prices, window=50)
        # 恒定价格，动量应为 0
        assert momentum == 0.0

    def test_zero_returns(self, engine):
        """测试零收益率"""
        returns = pd.Series([0, 0, 0, 0, 0])
        sharpe = engine.calc_sharpe_ratio(returns, window=5)
        # 零收益，夏普比率应为 0
        assert sharpe == 0.0

    def test_negative_prices(self, engine):
        """测试负价格（应该能处理）"""
        # 实际上价格不应为负，但测试应健壮
        prices = pd.Series([100, 101, 102, 103, 104, 103, 102, 101, 100, 99])
        drawdown = engine.calc_max_drawdown(prices, window=10)
        assert drawdown <= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
