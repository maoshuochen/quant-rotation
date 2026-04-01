"""
因子引擎测试
"""
import pytest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from factor_engine import FactorEngine


class TestFactorEngine:
    """因子引擎测试"""

    def test_pe_percentile(self):
        """测试 PE 分位数计算"""
        engine = FactorEngine()

        # 使用足够大的历史数据
        pe_history = pd.Series(list(range(10, 110)))  # 100 个数据点 10-109
        current_pe = 90

        percentile = engine.calc_pe_percentile(current_pe, pe_history)

        # 90 应该大于 80% 的历史值
        assert percentile >= 0.5

    def test_momentum(self):
        """测试动量计算"""
        engine = FactorEngine()

        prices = pd.Series([100, 105, 110, 115, 120, 125, 130])
        momentum = engine.calc_momentum(prices, window=3)

        # 动量应该是正数
        assert momentum > 0

    def test_volatility(self):
        """测试波动率计算"""
        engine = FactorEngine()

        returns = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
        volatility = engine.calc_volatility(returns, window=3)

        # 波动率应该是正数
        assert volatility > 0

    def test_calc_ic(self):
        """测试 IC 计算"""
        engine = FactorEngine()

        factor = pd.Series(np.random.randn(100))
        returns = pd.Series(np.random.randn(100))

        ic, ic_ir = engine.calc_ic(factor, returns)

        # IC 应该在 -1 到 1 之间
        assert -1 <= ic <= 1
