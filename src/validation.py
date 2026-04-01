"""
样本外验证模块
支持 OOS 测试、Walk-Forward 分析、参数敏感性测试
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class OOSResult:
    """样本外测试结果"""
    train_period: Tuple[str, str]
    oos_period: Tuple[str, str]
    train_sharpe: float
    oos_sharpe: float
    train_return: float
    oos_return: float
    train_max_dd: float
    oos_max_dd: float
    degradation_ratio: float
    is_robust: bool


@dataclass
class WalkForwardResult:
    """Walk-Forward 分析结果"""
    windows: List[Dict]
    avg_oos_return: float
    avg_oos_sharpe: float
    consistency_ratio: float
    is_robust: bool


class OutOfSampleValidator:
    """样本外验证器"""

    def __init__(self, oos_ratio: float = 0.3, min_train_days: int = 252, min_oos_days: int = 63):
        self.oos_ratio = oos_ratio
        self.min_train_days = min_train_days
        self.min_oos_days = min_oos_days

    def split_train_oos(self, data: pd.DataFrame, date_column: str = 'date') -> Tuple[pd.DataFrame, pd.DataFrame]:
        """分割训练集和样本外数据"""
        if date_column not in data.columns:
            if isinstance(data.index, pd.DatetimeIndex):
                data = data.reset_index()

        data = data.sort_values(date_column)
        n = len(data)
        train_size = max(int(n * (1 - self.oos_ratio)), self.min_train_days)
        oos_size = n - train_size

        if oos_size < self.min_oos_days:
            logger.warning(f"样本外数据不足 ({oos_size} < {self.min_oos_days})")
            return data, data.iloc[0:0]

        return data.iloc[:train_size].copy(), data.iloc[train_size:].copy()

    def _calculate_metrics(self, returns: pd.Series) -> Dict:
        """计算策略表现指标"""
        if returns.empty or len(returns) < 10:
            return {'sharpe': 0.0, 'total_return': 0.0, 'max_drawdown': 0.0, 'volatility': 0.0}

        nav = (1 + returns).cumprod()
        total_return = nav.iloc[-1] - 1
        daily_sharpe = returns.mean() / returns.std() if returns.std() > 0 else 0
        sharpe = daily_sharpe * np.sqrt(252)
        rolling_max = nav.cummax()
        drawdown = (nav - rolling_max) / rolling_max
        max_dd = drawdown.min()
        volatility = returns.std() * np.sqrt(252)

        return {'sharpe': float(sharpe), 'total_return': float(total_return), 
                'max_drawdown': float(max_dd), 'volatility': float(volatility)}

    def validate_strategy(self, strategy_func, data: pd.DataFrame, params: Dict = None,
                          date_column: str = 'date', return_column: str = 'return') -> OOSResult:
        """验证策略的样本外表现"""
        params = params or {}
        train_data, oos_data = self.split_train_oos(data, date_column)

        if oos_data.empty:
            return self._empty_result(train_data, date_column)

        train_returns = strategy_func(train_data, **params)
        train_metrics = self._calculate_metrics(train_returns)
        oos_returns = strategy_func(oos_data, **params)
        oos_metrics = self._calculate_metrics(oos_returns)

        degradation = 1 - (oos_metrics['sharpe'] / max(train_metrics['sharpe'], 0.01))
        is_robust = degradation < 0.3 and oos_metrics['sharpe'] > 0.5

        train_dates = train_data[date_column].iloc[[0, -1]]
        oos_dates = oos_data[date_column].iloc[[0, -1]]

        return OOSResult(
            train_period=(str(train_dates.iloc[0]), str(train_dates.iloc[1])),
            oos_period=(str(oos_dates.iloc[0]), str(oos_dates.iloc[1])),
            train_sharpe=train_metrics['sharpe'], oos_sharpe=oos_metrics['sharpe'],
            train_return=train_metrics['total_return'], oos_return=oos_metrics['total_return'],
            train_max_dd=train_metrics['max_drawdown'], oos_max_dd=oos_metrics['max_drawdown'],
            degradation_ratio=degradation, is_robust=is_robust
        )

    def walk_forward_analysis(self, strategy_func, data: pd.DataFrame, params: Dict = None,
                               window_size: int = 252, step_size: int = 21, oos_size: int = 63,
                               date_column: str = 'date') -> WalkForwardResult:
        """Walk-Forward 分析"""
        params = params or {}
        data = data.sort_values(date_column)
        n = len(data)

        if n < window_size + oos_size:
            return self._empty_wf_result()

        windows = []
        oos_returns = []
        oos_sharpes = []
        start_idx = 0

        while start_idx + window_size + oos_size <= n:
            train_end = start_idx + window_size
            oos_end = train_end + oos_size
            
            train_data = data.iloc[start_idx:train_end]
            oos_data = data.iloc[train_end:oos_end]

            train_metrics = self._calculate_metrics(strategy_func(train_data, **params))
            oos_metrics = self._calculate_metrics(strategy_func(oos_data, **params))

            windows.append({
                'window_id': len(windows) + 1,
                'train_start': str(train_data[date_column].iloc[0]),
                'train_end': str(train_data[date_column].iloc[-1]),
                'oos_start': str(oos_data[date_column].iloc[0]),
                'oos_end': str(oos_data[date_column].iloc[-1]),
                'train_sharpe': train_metrics['sharpe'],
                'oos_sharpe': oos_metrics['sharpe'],
                'oos_return': oos_metrics['total_return'],
                'oos_max_dd': oos_metrics['max_drawdown']
            })

            oos_returns.append(oos_metrics['total_return'])
            oos_sharpes.append(oos_metrics['sharpe'])
            start_idx += step_size

        if not windows:
            return self._empty_wf_result()

        return WalkForwardResult(
            windows=windows,
            avg_oos_return=np.mean(oos_returns),
            avg_oos_sharpe=np.mean(oos_sharpes),
            consistency_ratio=np.mean([r > 0 for r in oos_returns]),
            is_robust=np.mean(oos_sharpes) > 0.5 and np.mean([r > 0 for r in oos_returns]) > 0.6
        )

    def parameter_sensitivity(self, strategy_func, data: pd.DataFrame, param_name: str,
                               param_range: List, base_params: Dict = None,
                               date_column: str = 'date') -> pd.DataFrame:
        """参数敏感性分析"""
        results = []
        for param_value in param_range:
            params = {**(base_params or {}), param_name: param_value}
            result = self.validate_strategy(strategy_func, data, params, date_column)
            results.append({
                param_name: param_value,
                'oos_sharpe': result.oos_sharpe,
                'oos_return': result.oos_return,
                'oos_max_dd': result.oos_max_dd,
                'degradation': result.degradation_ratio,
                'is_robust': result.is_robust
            })
        return pd.DataFrame(results)

    def detect_overfitting(self, train_metrics: Dict, oos_metrics: Dict, threshold: float = 0.3) -> Dict:
        """检测过拟合"""
        sharpe_decay = 1 - (oos_metrics.get('sharpe', 0) / max(train_metrics.get('sharpe', 1), 0.01))
        return_decay = 1 - (oos_metrics.get('return', 0) / max(train_metrics.get('return', 0.01), 0.001))
        dd_increase = (oos_metrics.get('max_dd', 0) - train_metrics.get('max_dd', 0)) / max(abs(train_metrics.get('max_dd', 0.01)), 0.01)

        overfit_score = sum([sharpe_decay > threshold, return_decay > threshold, dd_increase > threshold])
        severity = 'high' if overfit_score >= 3 else 'medium' if overfit_score >= 2 else 'low' if overfit_score >= 1 else 'none'

        return {
            'is_overfitted': overfit_score >= 2,
            'severity': severity,
            'indicators': {'sharpe_decay': sharpe_decay, 'return_decay': return_decay, 
                          'dd_increase': dd_increase, 'overfit_score': overfit_score}
        }

    def _empty_result(self, train_data, date_column) -> OOSResult:
        train_dates = train_data[date_column].iloc[[0, -1]]
        return OOSResult(train_period=(str(train_dates.iloc[0]), str(train_dates.iloc[1])),
                         oos_period=('', ''), train_sharpe=0, oos_sharpe=0, train_return=0,
                         oos_return=0, train_max_dd=0, oos_max_dd=0, degradation_ratio=0, is_robust=False)

    def _empty_wf_result(self) -> WalkForwardResult:
        return WalkForwardResult(windows=[], avg_oos_return=0, avg_oos_sharpe=0, consistency_ratio=0, is_robust=False)


def create_oos_validator(oos_ratio: float = 0.3, min_train_days: int = 252) -> OutOfSampleValidator:
    """创建样本外验证器"""
    return OutOfSampleValidator(oos_ratio, min_train_days)
