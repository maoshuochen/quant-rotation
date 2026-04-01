"""
风险管理测试
"""
import pytest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from risk_manager import RiskManager, RiskMetrics
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


@pytest.mark.skipif(not HAS_SCIPY, reason="scipy not installed")
class TestRiskManager:
    """风险管理器测试"""

    def test_var_calculation(self):
        """测试 VaR 计算"""
        manager = RiskManager()

        returns = pd.Series(np.random.randn(100) * 0.02)
        var_95 = manager.calc_var(returns, confidence=0.95)

        # VaR 应该是负数
        assert var_95 < 0

    def test_cvar_calculation(self):
        """测试 CVaR 计算"""
        manager = RiskManager()

        returns = pd.Series(np.random.randn(100) * 0.02)
        cvar_95 = manager.calc_cvar(returns, confidence=0.95)

        # CVaR 应该小于等于 VaR
        var_95 = manager.calc_var(returns, confidence=0.95)
        assert cvar_95 <= var_95

    def test_max_drawdown(self):
        """测试最大回撤计算"""
        manager = RiskManager()

        prices = pd.Series([100, 110, 120, 100, 90, 110, 130])
        max_dd = manager.calc_max_drawdown(prices)

        # 最大回撤应该是负数
        assert max_dd < 0
        # 从 120 到 90 的回撤约为 25%
        assert abs(max_dd - (-0.25)) < 0.01

    def test_kelly_fraction(self):
        """测试 Kelly 公式"""
        manager = RiskManager()

        # 胜率 60%, 盈亏比 2:1
        kelly = manager.calc_kelly_fraction(
            win_rate=0.6,
            win_loss_ratio=2.0
        )

        # 半凯利应该在 0-25% 之间
        assert 0 < kelly <= 0.25

    def test_stop_loss_check(self):
        """测试止损检查"""
        manager = RiskManager()

        # 个体止损触发
        result = manager.check_stop_loss(
            entry_price=100,
            current_price=85,  # -15%
            highest_price=100,
            holding_days=5
        )

        assert result['individual'] is True
