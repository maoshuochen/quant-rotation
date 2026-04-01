"""
样本外验证测试
"""
import pytest
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, 'src')

from validation import OutOfSampleValidator, WalkForwardResult


class TestOutOfSampleValidator:
    """样本外验证器测试"""

    def test_train_test_split(self):
        """测试训练/测试分割"""
        validator = OutOfSampleValidator(train_ratio=0.7)

        data = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=500),
            'close': np.random.randn(500).cumsum()
        })
        data = data.set_index('date')

        train, test = validator.simple_train_test_split(data)

        assert len(train) == 350
        assert len(test) == 150

    def test_overfitting_detection(self):
        """测试过拟合检测"""
        validator = OutOfSampleValidator()

        # 过拟合场景
        result = validator.detect_overfitting(
            train_score=2.0,
            test_score=0.5,
            threshold=0.3
        )

        assert result['is_overfitting'] is True
        assert result['severity'] == 'medium'

        # 正常场景
        result = validator.detect_overfitting(
            train_score=1.0,
            test_score=0.9,
            threshold=0.3
        )

        assert result['is_overfitting'] is False

    def test_stability_test(self):
        """测试稳定性测试"""
        validator = OutOfSampleValidator()

        results = [
            {'sharpe': 1.5},
            {'sharpe': 1.6},
            {'sharpe': 1.4},
            {'sharpe': 1.55},
            {'sharpe': 1.45}
        ]

        stats = validator.stability_test(results)

        assert stats['mean'] == pytest.approx(1.5, abs=0.01)
        assert stats['cv'] < 0.1  # 变异系数应该很小
