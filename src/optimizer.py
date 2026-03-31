"""
参数优化模块 - 贝叶斯优化
使用贝叶斯优化自动搜索最优策略参数
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from skopt import gp_minimize
    from skopt.space import Real, Integer, Categorical
    from skopt.utils import use_named_args
    SKOPT_AVAILABLE = True
except ImportError:
    SKOPT_AVAILABLE = False
    logger.warning("scikit-optimize not installed. Install with: pip install scikit-optimize")


@dataclass
class OptimizationResult:
    """优化结果"""
    best_params: Dict[str, float]
    best_score: float
    all_trials: List[Dict]
    n_trials: int
    optimization_time: float
    metric: str

    def to_dataframe(self) -> pd.DataFrame:
        """将试验结果转为 DataFrame"""
        df = pd.DataFrame(self.all_trials)
        if 'params' in df.columns:
            params_df = pd.DataFrame(df['params'].tolist())
            df = pd.concat([params_df, df.drop(columns=['params'])], axis=1)
        return df

    def summary(self) -> str:
        """返回优化摘要"""
        lines = [
            "=" * 60,
            "贝叶斯优化结果",
            "=" * 60,
            f"优化指标：{self.metric}",
            f"试验次数：{self.n_trials}",
            f"优化时间：{self.optimization_time:.1f}秒",
            "",
            "最优参数:",
        ]
        for key, value in self.best_params.items():
            if isinstance(value, float):
                lines.append(f"  {key}: {value:.4f}")
            else:
                lines.append(f"  {key}: {value}")
        lines.append("")
        lines.append(f"最优得分：{self.best_score:.4f}")
        lines.append("=" * 60)
        return "\n".join(lines)


@dataclass
class ParameterSpace:
    """参数空间定义"""
    name: str
    param_type: str  # 'real', 'integer', 'categorical'
    low: Optional[float] = None
    high: Optional[float] = None
    categories: Optional[List] = None
    prior: str = 'uniform'  # 'uniform' or 'log-uniform'
    base: int = 10

    def to_skopt_space(self):
        """转换为 skopt 空间"""
        if not SKOPT_AVAILABLE:
            raise ImportError("scikit-optimize not installed")

        if self.param_type == 'real':
            return Real(self.low, self.high, prior=self.prior, name=self.name)
        elif self.param_type == 'integer':
            return Integer(int(self.low), int(self.high), name=self.name)
        elif self.param_type == 'categorical':
            return Categorical(self.categories, name=self.name)
        else:
            raise ValueError(f"Unknown param_type: {self.param_type}")


class BayesianOptimizer:
    """
    贝叶斯优化器

    用于自动搜索策略最优参数组合

    支持优化目标:
    - total_return: 总收益率
    - sharpe: 夏普比率
    - sortino: 索提诺比率
    - max_drawdown: 最大回撤 (最小化)
    - calmar: 卡玛比率 (收益/回撤)
    - custom: 自定义目标函数
    """

    def __init__(
        self,
        backtest_func: Callable[[Dict], Dict],
        param_space: List[ParameterSpace],
        n_trials: int = 50,
        random_state: int = 42,
        n_initial_points: int = 10,
        acquisition_func: str = 'gp_hedge'
    ):
        """
        初始化优化器

        Args:
            backtest_func: 回测函数，接收参数字典，返回包含性能指标的字典
            param_space: 参数空间定义
            n_trials: 优化迭代次数
            random_state: 随机种子
            n_initial_points: 初始随机采样点数
            acquisition_func: 采集函数类型 ('gp_hedge', 'EI', 'PI', 'LCB')
        """
        if not SKOPT_AVAILABLE:
            raise ImportError("scikit-optimize not installed. Install with: pip install scikit-optimize")

        self.backtest_func = backtest_func
        self.param_space = param_space
        self.n_trials = n_trials
        self.random_state = random_state
        self.n_initial_points = n_initial_points
        self.acquisition_func = acquisition_func

        self.space = [p.to_skopt_space() for p in param_space]
        self.dim_names = [p.name for p in param_space]

        self.trials = []
        self.best_params = None
        self.best_score = -np.inf

        logger.info(f"初始化贝叶斯优化器：{len(self.space)}个参数，{n_trials}次试验")

    def _extract_metrics(self, backtest_result: Dict) -> float:
        """
        从回测结果中提取优化指标

        Args:
            backtest_result: 回测结果字典

        Returns:
            优化目标值
        """
        # 默认使用夏普比率
        return backtest_result.get('sharpe', 0.0)

    def _run_single_trial(self, params: List) -> Tuple[float, Dict]:
        """
        运行单次试验

        Args:
            params: 参数列表 (按参数空间顺序)

        Returns:
            (负的目标值，试验详情)
            注意：返回负值是因为 skopt 做最小化
        """
        # 转换参数列表为字典
        param_dict = {}
        for i, value in enumerate(params):
            name = self.dim_names[i]
            # 处理整数参数
            if self.param_space[i].param_type == 'integer':
                param_dict[name] = int(value)
            else:
                param_dict[name] = value

        try:
            # 运行回测
            result = self.backtest_func(param_dict)

            # 提取指标
            score = self._extract_metrics(result)

            # 处理无效结果
            if not np.isfinite(score):
                score = -1e6  # 惩罚无效结果

            trial_info = {
                'params': param_dict.copy(),
                'params_list': params.copy(),
                'score': score,
                'timestamp': datetime.now().isoformat(),
                'backtest_result': {
                    k: v for k, v in result.items()
                    if k not in ['daily_values', 'trades']  # 省略大数据
                }
            }

            self.trials.append(trial_info)

            # 更新最优
            if score > self.best_score:
                self.best_score = score
                self.best_params = param_dict.copy()
                logger.info(f"新最优：{score:.4f} @ {param_dict}")

            # 返回负值 (skopt 最小化)
            return -score, trial_info

        except Exception as e:
            logger.error(f"试验失败：{e}")
            return 1e6, {  # 返回大的正值作为惩罚
                'params': param_dict,
                'score': -1e6,
                'error': str(e)
            }

    def optimize(self, verbose: bool = True) -> OptimizationResult:
        """
        执行贝叶斯优化

        Args:
            verbose: 是否输出进度

        Returns:
            OptimizationResult: 优化结果
        """
        logger.info(f"开始贝叶斯优化 ({self.n_trials} 次试验)...")
        start_time = datetime.now()

        # 使用装饰器包装目标函数
        @use_named_args(self.space)
        def objective(**kwargs):
            params = [kwargs[name] for name in self.dim_names]
            neg_score, _ = self._run_single_trial(params)
            return neg_score

        # 执行优化
        try:
            result = gp_minimize(
                func=objective,
                dimensions=self.space,
                n_calls=self.n_trials,
                n_initial_points=self.n_initial_points,
                acq_func=self.acquisition_func,
                random_state=self.random_state,
                verbose=verbose
            )

            # 解析结果
            best_params = {
                name: value
                for name, value in zip(self.dim_names, result.x)
            }

            # 处理整数参数
            for i, ps in enumerate(self.param_space):
                if ps.param_type == 'integer':
                    name = self.dim_names[i]
                    best_params[name] = int(best_params[name])

            elapsed = (datetime.now() - start_time).total_seconds()

            optimization_result = OptimizationResult(
                best_params=best_params,
                best_score=self.best_score,
                all_trials=self.trials,
                n_trials=len(self.trials),
                optimization_time=elapsed,
                metric='sharpe'
            )

            logger.info(f"优化完成：{len(self.trials)}次试验，耗时{elapsed:.1f}秒")
            logger.info(f"最优参数：{best_params}")
            logger.info(f"最优得分：{self.best_score:.4f}")

            return optimization_result

        except Exception as e:
            logger.error(f"优化失败：{e}")
            # 返回当前已找到的最优结果
            elapsed = (datetime.now() - start_time).total_seconds()
            return OptimizationResult(
                best_params=self.best_params or {},
                best_score=self.best_score if self.best_score != -np.inf else 0,
                all_trials=self.trials,
                n_trials=len(self.trials),
                optimization_time=elapsed,
                metric='sharpe'
            )

    def get_trial_history(self) -> pd.DataFrame:
        """获取试验历史"""
        return pd.DataFrame(self.trials)

    def plot_convergence(self, ax=None):
        """绘制收敛曲线"""
        try:
            from skopt.plots import plot_convergence
        except ImportError:
            logger.warning("matplotlib not installed")
            return None

        scores = [-t['score'] for t in self.trials]  # 取负因为 skopt 最小化

        if ax is None:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 6))

        ax.plot(scores, 'o-', markersize=4)
        ax.plot(np.maximum.accumulate(scores), 'r--', label='Best so far')
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Score (negative for minimization)')
        ax.set_title('Bayesian Optimization Convergence')
        ax.legend()
        ax.grid(True, alpha=0.3)

        return ax

    def plot_parameter_importance(self, ax=None):
        """绘制参数重要性"""
        try:
            from skopt.plots import plot_evaluations
        except ImportError:
            logger.warning("matplotlib not installed")
            return None

        if len(self.trials) < self.n_initial_points:
            logger.warning("试验次数不足，无法绘制参数重要性")
            return None

        # 准备数据
        X = np.array([t['params_list'] for t in self.trials])
        y = np.array([-t['score'] for t in self.trials])  # 取负

        if ax is None:
            import matplotlib.pyplot as plt
            fig, axes = plt.subplots(1, len(self.dim_names), figsize=(5 * len(self.dim_names), 4))
            if len(self.dim_names) == 1:
                axes = [axes]
        else:
            axes = [ax]

        for i, name in enumerate(self.dim_names):
            axes[i].scatter(X[:, i], y, alpha=0.5, s=20)
            axes[i].set_xlabel(name)
            axes[i].set_ylabel('Score')
            axes[i].set_title(f'{name} vs Score')
            axes[i].grid(True, alpha=0.3)

        plt.tight_layout()
        return axes


# ===== 预定义的参数空间 =====

def get_strategy_param_space() -> List[ParameterSpace]:
    """获取策略参数空间 (用于回测优化)"""
    return [
        # 策略参数
        ParameterSpace('top_n', 'integer', low=3, high=10),
        ParameterSpace('buffer_n', 'integer', low=5, high=15),
        ParameterSpace('momentum_window', 'integer', low=60, high=252),
        ParameterSpace('lookback_pe', 'integer', low=252, high=756),  # 1-3 年

        # 因子权重 (归一化后使用)
        ParameterSpace('value_weight', 'real', low=0.0, high=0.4),
        ParameterSpace('momentum_weight', 'real', low=0.0, high=0.4),
        ParameterSpace('trend_weight', 'real', low=0.0, high=0.4),
        ParameterSpace('flow_weight', 'real', low=0.0, high=0.4),
        ParameterSpace('volatility_weight', 'real', low=0.0, high=0.2),

        # 止损参数
        ParameterSpace('stop_loss_individual', 'real', low=0.10, high=0.25),
        ParameterSpace('stop_loss_trailing', 'real', low=0.05, high=0.15),
        ParameterSpace('stop_loss_portfolio', 'real', low=0.15, high=0.30),
        ParameterSpace('cooldown_days', 'integer', low=0, high=10),
    ]


def get_factor_weight_space() -> List[ParameterSpace]:
    """获取因子权重优化空间"""
    return [
        ParameterSpace('value_weight', 'real', low=0.0, high=0.4),
        ParameterSpace('momentum_weight', 'real', low=0.0, high=0.4),
        ParameterSpace('trend_weight', 'real', low=0.0, high=0.4),
        ParameterSpace('flow_weight', 'real', low=0.0, high=0.4),
        ParameterSpace('volatility_weight', 'real', low=0.0, high=0.2),
        ParameterSpace('fundamental_weight', 'real', low=0.0, high=0.2),
        ParameterSpace('sentiment_weight', 'real', low=0.0, high=0.2),
    ]


def get_stop_loss_param_space() -> List[ParameterSpace]:
    """获取止损参数优化空间"""
    return [
        ParameterSpace('stop_loss_individual', 'real', low=0.10, high=0.25),
        ParameterSpace('stop_loss_trailing', 'real', low=0.05, high=0.15),
        ParameterSpace('stop_loss_portfolio', 'real', low=0.15, high=0.30),
        ParameterSpace('cooldown_days', 'integer', low=0, high=15),
    ]


class MultiObjectiveOptimizer:
    """
    多目标贝叶斯优化器

    同时优化多个目标：
    - 夏普比率 (最大化)
    - 最大回撤 (最小化)
    - 总收益 (最大化)

    使用加权综合评分或 Pareto 前沿方法
    """

    def __init__(
        self,
        backtest_func: Callable[[Dict], Dict],
        param_space: List[ParameterSpace],
        n_trials: int = 50,
        random_state: int = 42,
        n_initial_points: int = 10,
        objective: str = 'composite',
        weights: Optional[Dict[str, float]] = None
    ):
        """
        初始化多目标优化器

        Args:
            backtest_func: 回测函数
            param_space: 参数空间定义
            n_trials: 优化迭代次数
            random_state: 随机种子
            n_initial_points: 初始随机采样点数
            objective: 优化目标类型
                - 'composite': 加权综合评分
                - 'sharpe': 仅夏普比率
                - 'drawdown': 仅最大回撤 (最小化)
                - 'return': 仅总收益
            weights: 各目标权重 (仅 composite 模式需要)
                默认：{'sharpe': 0.4, 'drawdown': 0.3, 'return': 0.3}
        """
        if not SKOPT_AVAILABLE:
            raise ImportError("scikit-optimize not installed")

        self.backtest_func = backtest_func
        self.param_space = param_space
        self.n_trials = n_trials
        self.random_state = random_state
        self.n_initial_points = n_initial_points
        self.objective = objective

        # 默认权重
        self.weights = weights or {
            'sharpe': 0.4,
            'drawdown': 0.3,
            'return': 0.3
        }

        self.space = [p.to_skopt_space() for p in param_space]
        self.dim_names = [p.name for p in param_space]

        self.trials = []
        self.best_params = None
        self.best_score = -np.inf
        self.pareto_front = []  # Pareto 前沿解

        logger.info(f"初始化多目标优化器：{len(self.space)}个参数，{n_trials}次试验")
        logger.info(f"优化目标：{objective}, 权重：{self.weights}")

    def _compute_composite_score(self, metrics: Dict) -> float:
        """
        计算加权综合评分

        评分公式：
        score = w1 * norm(sharpe) + w2 * norm(-drawdown) + w3 * norm(return)

        所有指标归一化到 0-1 范围
        """
        sharpe = metrics.get('sharpe', 0)
        drawdown = abs(metrics.get('max_drawdown', 0))
        total_return = metrics.get('total_return', 0)

        # 归一化 (基于合理范围)
        # Sharpe: 0-2 -> 0-1
        norm_sharpe = min(1, max(0, sharpe / 2))
        # Drawdown: 0-0.3 -> 0-1 (越小越好，所以取反)
        norm_drawdown = 1 - min(1, drawdown / 0.3)
        # Return: -0.5 to 1 -> 0-1
        norm_return = min(1, max(0, (total_return + 0.5) / 1.5))

        # 加权综合
        score = (
            self.weights['sharpe'] * norm_sharpe +
            self.weights['drawdown'] * norm_drawdown +
            self.weights['return'] * norm_return
        )

        return score

    def _extract_metrics(self, backtest_result: Dict) -> float:
        """提取优化指标"""
        if self.objective == 'sharpe':
            return backtest_result.get('sharpe', 0)
        elif self.objective == 'drawdown':
            # 返回负的回撤值 (因为 skopt 做最小化)
            return -abs(backtest_result.get('max_drawdown', 0))
        elif self.objective == 'return':
            return backtest_result.get('total_return', 0)
        else:  # composite
            return self._compute_composite_score(backtest_result)

    def _run_single_trial(self, params: List) -> Tuple[float, Dict]:
        """运行单次试验"""
        # 转换参数列表为字典
        param_dict = {}
        for i, value in enumerate(params):
            name = self.dim_names[i]
            if self.param_space[i].param_type == 'integer':
                param_dict[name] = int(value)
            else:
                param_dict[name] = value

        try:
            result = self.backtest_func(param_dict)
            score = self._extract_metrics(result)

            if not np.isfinite(score):
                score = -1e6

            # 保存完整指标
            trial_info = {
                'params': param_dict.copy(),
                'params_list': params.copy(),
                'score': score,
                'timestamp': datetime.now().isoformat(),
                'metrics': {
                    'sharpe': result.get('sharpe', 0),
                    'total_return': result.get('total_return', 0),
                    'max_drawdown': result.get('max_drawdown', 0),
                    'sortino': result.get('sortino', 0),
                    'calmar': result.get('calmar', 0)
                }
            }

            self.trials.append(trial_info)

            # 更新最优
            if score > self.best_score:
                self.best_score = score
                self.best_params = param_dict.copy()
                logger.info(f"新最优：{score:.4f} @ {param_dict}")

            # 更新 Pareto 前沿
            self._update_pareto_front(result, param_dict.copy())

            return -score, trial_info

        except Exception as e:
            logger.error(f"试验失败：{e}")
            return 1e6, {
                'params': param_dict,
                'score': -1e6,
                'error': str(e)
            }

    def _update_pareto_front(self, result: Dict, params: Dict):
        """更新 Pareto 前沿"""
        metrics = {
            'sharpe': result.get('sharpe', 0),
            'return': result.get('total_return', 0),
            'drawdown': abs(result.get('max_drawdown', 0))
        }

        # 检查是否被现有前沿支配
        is_dominated = False
        for front_item in self.pareto_front:
            front_metrics = front_item['metrics']
            # 如果现有点在所有目标上都不差于新点，则新点被支配
            if (front_metrics['sharpe'] >= metrics['sharpe'] and
                front_metrics['return'] >= metrics['return'] and
                front_metrics['drawdown'] <= metrics['drawdown']):
                is_dominated = True
                break

        if not is_dominated:
            # 移除被新点支配的点
            self.pareto_front = [
                item for item in self.pareto_front
                if not (
                    item['metrics']['sharpe'] <= metrics['sharpe'] and
                    item['metrics']['return'] <= metrics['return'] and
                    item['metrics']['drawdown'] >= metrics['drawdown']
                )
            ]
            self.pareto_front.append({
                'params': params,
                'metrics': metrics
            })

    def optimize(self, verbose: bool = True) -> OptimizationResult:
        """执行多目标优化"""
        logger.info(f"开始多目标优化 ({self.n_trials} 次试验)...")
        start_time = datetime.now()

        @use_named_args(self.space)
        def objective(**kwargs):
            params = [kwargs[name] for name in self.dim_names]
            neg_score, _ = self._run_single_trial(params)
            return neg_score

        try:
            result = gp_minimize(
                func=objective,
                dimensions=self.space,
                n_calls=self.n_trials,
                n_initial_points=self.n_initial_points,
                acq_func='gp_hedge',
                random_state=self.random_state,
                verbose=verbose
            )

            best_params = {
                name: value
                for name, value in zip(self.dim_names, result.x)
            }

            for i, ps in enumerate(self.param_space):
                if ps.param_type == 'integer':
                    name = self.dim_names[i]
                    best_params[name] = int(best_params[name])

            elapsed = (datetime.now() - start_time).total_seconds()

            return OptimizationResult(
                best_params=best_params,
                best_score=self.best_score,
                all_trials=self.trials,
                n_trials=len(self.trials),
                optimization_time=elapsed,
                metric=f'multi_{self.objective}'
            )

        except Exception as e:
            logger.error(f"优化失败：{e}")
            elapsed = (datetime.now() - start_time).total_seconds()
            return OptimizationResult(
                best_params=self.best_params or {},
                best_score=self.best_score if self.best_score != -np.inf else 0,
                all_trials=self.trials,
                n_trials=len(self.trials),
                optimization_time=elapsed,
                metric=f'multi_{self.objective}'
            )

    def get_pareto_front(self) -> List[Dict]:
        """获取 Pareto 前沿"""
        return self.pareto_front

    def get_trial_history(self) -> pd.DataFrame:
        """获取试验历史"""
        records = []
        for trial in self.trials:
            record = {
                'params': trial['params'],
                'score': trial['score'],
                'timestamp': trial['timestamp'],
                **trial['metrics']
            }
            records.append(record)
        return pd.DataFrame(records)
