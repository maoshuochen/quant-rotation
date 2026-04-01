"""
样本外验证测试
"""
import pytest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from validation import OutOfSampleValidator


class TestOutOfSampleValidator:
    """样本外验证器测试"""

    def test_initialization(self):
        """测试初始化"""
        validator = OutOfSampleValidator()
        assert validator is not None

    def test_overfitting_detection(self):
        """测试过拟合检测"""
        validator = OutOfSampleValidator()

        # 过拟合场景：OOS 夏普比率远低于训练集
        train_metrics = {'sharpe': 2.0, 'return': 0.5, 'max_dd': -0.1}
        oos_metrics = {'sharpe': 0.5, 'return': 0.1, 'max_dd': -0.2}

        result = validator.detect_overfitting(train_metrics, oos_metrics)

        assert result['is_overfitted'] is True

        # 正常场景：OOS 与训练集接近
        train_metrics = {'sharpe': 1.0, 'return': 0.3, 'max_dd': -0.1}
        oos_metrics = {'sharpe': 0.9, 'return': 0.28, 'max_dd': -0.12}

        result = validator.detect_overfitting(train_metrics, oos_metrics)

        assert result['is_overfitted'] is False
