"""
Optimizer 模块单元测试
测试贝叶斯优化和多目标优化功能
"""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import (
    ParameterSpace,
    BayesianOptimizer,
    MultiObjectiveOptimizer,
    get_factor_weight_space,
)


class TestParameterSpace:
    """测试参数空间定义"""

    def test_real_space(self):
        """测试实数参数空间"""
        space = ParameterSpace('weight', 'real', low=0.0, high=1.0)
        skopt_space = space.to_skopt_space()
        assert skopt_space.low == 0.0
        assert skopt_space.high == 1.0

    def test_integer_space(self):
        """测试整数参数空间"""
        space = ParameterSpace('top_n', 'integer', low=3, high=10)
        skopt_space = space.to_skopt_space()
        assert skopt_space.low == 3
        assert skopt_space.high == 10

    def test_categorical_space(self):
        """测试分类参数空间"""
        space = ParameterSpace('frequency', 'categorical', categories=['daily', 'weekly', 'monthly'])
        skopt_space = space.to_skopt_space()
        assert 'weekly' in skopt_space.categories


class MockBacktestResult:
    """模拟回测结果"""

    def __init__(self, base_sharpe=0.5, noise=0.1):
        self.base_sharpe = base_sharpe
        self.noise = noise

    def __call__(self, params):
        """模拟回测函数"""
        weight = params.get('value_weight', 0.5)
        # 模拟：权重越接近 0.5 表现越好
        score = self.base_sharpe - abs(weight - 0.5) + np.random.normal(0, self.noise)
        return {
            'sharpe': score,
            'total_return': score * 0.2,
            'max_drawdown': -abs(score * 0.1),
            'sortino': score * 1.2,
            'calmar': score * 1.5,
        }


class TestBayesianOptimizer:
    """测试贝叶斯优化器"""

    @pytest.fixture
    def mock_backtest(self):
        return MockBacktestResult(base_sharpe=0.5, noise=0.05)

    @pytest.fixture
    def param_space(self):
        return [
            ParameterSpace('value_weight', 'real', low=0.0, high=1.0),
            ParameterSpace('momentum_weight', 'real', low=0.0, high=1.0),
        ]

    def test_initialization(self, param_space):
        """测试优化器初始化"""
        optimizer = BayesianOptimizer(
            backtest_func=MockBacktestResult(),
            param_space=param_space,
            n_trials=10,
        )
        assert len(optimizer.space) == 2
        assert optimizer.n_trials == 10

    def test_optimize(self, mock_backtest, param_space):
        """测试优化执行"""
        optimizer = BayesianOptimizer(
            backtest_func=mock_backtest,
            param_space=param_space,
            n_trials=5,
            n_initial_points=2,
            random_state=42,
        )
        result = optimizer.optimize(verbose=False)

        assert result.best_params is not None
        assert 'value_weight' in result.best_params
        assert 'momentum_weight' in result.best_params
        assert isinstance(result.best_score, float)
        assert result.n_trials >= 5

    def test_get_trial_history(self, mock_backtest, param_space):
        """测试试验历史获取"""
        optimizer = BayesianOptimizer(
            backtest_func=mock_backtest,
            param_space=param_space,
            n_trials=15,  # 增加到 15 因为 skopt 要求至少 10 次
            n_initial_points=5,
            random_state=42,
        )
        optimizer.optimize(verbose=False)

        history = optimizer.get_trial_history()
        assert isinstance(history, pd.DataFrame)
        assert len(history) >= 10  # 至少应该有 10 次试验
        assert 'score' in history.columns


class TestMultiObjectiveOptimizer:
    """测试多目标优化器"""

    @pytest.fixture
    def mock_backtest(self):
        return MockBacktestResult(base_sharpe=0.8, noise=0.05)

    @pytest.fixture
    def param_space(self):
        return get_factor_weight_space()

    def test_initialization(self, param_space):
        """测试多目标优化器初始化"""
        optimizer = MultiObjectiveOptimizer(
            backtest_func=MockBacktestResult(),
            param_space=param_space,
            n_trials=10,
            objective='composite',
        )
        assert optimizer.objective == 'composite'
        assert optimizer.weights['sharpe'] == 0.4
        assert optimizer.weights['drawdown'] == 0.3
        assert optimizer.weights['return'] == 0.3

    def test_composite_score(self, param_space):
        """测试综合评分计算"""
        optimizer = MultiObjectiveOptimizer(
            backtest_func=MockBacktestResult(),
            param_space=param_space,
            n_trials=5,
        )

        # 测试完美指标
        perfect_metrics = {'sharpe': 2.0, 'max_drawdown': -0.1, 'total_return': 0.5}
        score = optimizer._compute_composite_score(perfect_metrics)
        assert 0 < score <= 1

        # 测试差指标
        poor_metrics = {'sharpe': 0, 'max_drawdown': -0.5, 'total_return': -0.3}
        score = optimizer._compute_composite_score(poor_metrics)
        assert 0 <= score < 0.5

    def test_optimize_composite(self, mock_backtest, param_space):
        """测试多目标优化（综合模式）"""
        optimizer = MultiObjectiveOptimizer(
            backtest_func=mock_backtest,
            param_space=param_space,
            n_trials=5,
            n_initial_points=2,
            objective='composite',
            random_state=42,
        )
        result = optimizer.optimize(verbose=False)

        assert result.best_params is not None
        assert result.best_score > 0

    def test_optimize_sharpe_only(self, mock_backtest, param_space):
        """测试仅优化夏普比率"""
        optimizer = MultiObjectiveOptimizer(
            backtest_func=mock_backtest,
            param_space=param_space,
            n_trials=5,
            n_initial_points=2,
            objective='sharpe',
            random_state=42,
        )
        result = optimizer.optimize(verbose=False)

        assert result.metric == 'multi_sharpe'

    def test_pareto_front(self, mock_backtest, param_space):
        """测试 Pareto 前沿"""
        optimizer = MultiObjectiveOptimizer(
            backtest_func=mock_backtest,
            param_space=param_space,
            n_trials=10,
            random_state=42,
        )
        optimizer.optimize(verbose=False)

        pareto = optimizer.get_pareto_front()
        assert isinstance(pareto, list)
        # Pareto 前沿应该有解
        if len(pareto) > 0:
            for item in pareto:
                assert 'params' in item
                assert 'metrics' in item
                assert 'sharpe' in item['metrics']
                assert 'return' in item['metrics']
                assert 'drawdown' in item['metrics']


class TestGetFactorWeightSpace:
    """测试因子权重空间获取"""

    def test_space_definition(self):
        """测试参数空间定义正确性"""
        space = get_factor_weight_space()

        assert len(space) == 7
        names = [p.name for p in space]
        expected = [
            'value_weight', 'momentum_weight', 'trend_weight',
            'flow_weight', 'volatility_weight', 'fundamental_weight',
            'sentiment_weight'
        ]
        assert names == expected

        # 检查权重范围
        for p in space:
            assert p.param_type == 'real'
            assert p.low >= 0
            assert p.high <= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
