"""
风险管理模块
支持 VaR/CVaR、仓位管理、动态止损等
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy import stats
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """风险指标"""
    var_95: float  # 95% VaR
    var_99: float  # 99% VaR
    cvar_95: float  # 95% CVaR
    cvar_99: float  # 99% CVaR
    max_drawdown: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float


class RiskManager:
    """
    风险管理器

    功能:
    - VaR / CVaR 计算
    - 波动率目标控制
    - 仓位管理 (Kelly/风险平价)
    - 动态止损
    - 风险预算
    """

    def __init__(
        self,
        var_confidence: float = 0.95,
        max_position_pct: float = 0.25,
        min_position_pct: float = 0.05,
        target_volatility: float = 0.15,
        use_kelly: bool = False
    ):
        self.var_confidence = var_confidence
        self.max_position_pct = max_position_pct
        self.min_position_pct = min_position_pct
        self.target_volatility = target_volatility
        self.use_kelly = use_kelly

        # 止损配置
        self.stop_loss_config = {
            'individual': 0.12,      # 个体止损 12%
            'trailing': 0.06,        # 移动止损 6%
            'portfolio': 0.15,       # 组合止损 15%
            'time_stop': 20          # 时间止损 20 天
        }

    def calc_var(self,
                 returns: pd.Series,
                 confidence: float = 0.95,
                 method: str = 'historical') -> float:
        """
        计算 VaR (Value at Risk)

        Args:
            returns: 收益率序列
            confidence: 置信水平
            method: 'historical', 'parametric', 'monte_carlo'

        Returns:
            VaR 值 (负数表示损失)
        """
        if returns.empty or len(returns) < 30:
            return 0.0

        if method == 'historical':
            # 历史法
            var = np.percentile(returns.dropna(), (1 - confidence) * 100)
            return float(var)

        elif method == 'parametric':
            # 参数法 (假设正态分布)
            mu = returns.mean()
            sigma = returns.std()
            var = mu - stats.norm.ppf(confidence) * sigma
            return float(var)

        elif method == 'monte_carlo':
            # 蒙特卡洛模拟
            n_simulations = 10000
            mu = returns.mean()
            sigma = returns.std()

            simulated_returns = np.random.normal(mu, sigma, n_simulations)
            var = np.percentile(simulated_returns, (1 - confidence) * 100)
            return float(var)

        else:
            logger.warning(f"Unknown VaR method: {method}")
            return float(np.percentile(returns.dropna(), (1 - confidence) * 100))

    def calc_cvar(self,
                  returns: pd.Series,
                  confidence: float = 0.95) -> float:
        """
        计算 CVaR (Conditional VaR, 预期损失)

        CVaR 是超过 VaR 的损失的期望值
        """
        if returns.empty or len(returns) < 30:
            return 0.0

        var = self.calc_var(returns, confidence, method='historical')
        cvar = returns[returns <= var].mean()

        if np.isnan(cvar):
            return var

        return float(cvar)

    def calc_max_drawdown(self, prices: pd.Series) -> float:
        """计算最大回撤"""
        if prices.empty:
            return 0.0

        rolling_max = prices.expanding().max()
        drawdowns = (prices - rolling_max) / rolling_max
        return float(drawdowns.min())

    def calc_sortino_ratio(self,
                           returns: pd.Series,
                           risk_free: float = 0.02) -> float:
        """
        计算 Sortino 比率 (只考虑下行波动)
        """
        if len(returns) < 30:
            return 0.0

        excess_return = returns.mean() * 252 - risk_free

        # 下行偏差
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return float('inf')

        downside_std = downside_returns.std() * np.sqrt(252)

        if downside_std == 0:
            return 0.0

        return float(excess_return / downside_std)

    def calc_calmar_ratio(self,
                          returns: pd.Series,
                          prices: pd.Series) -> float:
        """
        计算 Calmar 比率 (收益/最大回撤)
        """
        if len(returns) < 252:
            return 0.0

        annual_return = returns.mean() * 252
        max_dd = abs(self.calc_max_drawdown(prices))

        if max_dd == 0:
            return 0.0

        return float(annual_return / max_dd)

    def get_risk_metrics(self,
                         returns: pd.Series,
                         prices: pd.Series) -> RiskMetrics:
        """
        获取完整风险指标
        """
        # VaR / CVaR
        var_95 = self.calc_var(returns, 0.95)
        var_99 = self.calc_var(returns, 0.99)
        cvar_95 = self.calc_cvar(returns, 0.95)
        cvar_99 = self.calc_cvar(returns, 0.99)

        # 波动率
        volatility = float(returns.std() * np.sqrt(252))

        # 夏普比率
        excess_return = returns.mean() * 252 - 0.02
        sharpe = float(excess_return / volatility) if volatility > 0 else 0.0

        return RiskMetrics(
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            max_drawdown=self.calc_max_drawdown(prices),
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=self.calc_sortino_ratio(returns),
            calmar_ratio=self.calc_calmar_ratio(returns, prices)
        )

    def calc_kelly_fraction(self,
                            win_rate: float,
                            win_loss_ratio: float) -> float:
        """
        计算 Kelly 公式最优仓位

        f* = (p * b - q) / b
        p = 胜率，q = 败率，b = 盈亏比
        """
        if win_loss_ratio <= 0:
            return 0.0

        p = win_rate
        q = 1 - win_rate
        b = win_loss_ratio

        kelly = (p * b - q) / b

        # Kelly 通常过于激进，使用半凯利
        return max(0, min(kelly / 2, self.max_position_pct))

    def calc_risk_parity_weights(self,
                                  cov_matrix: pd.DataFrame,
                                  risk_budget: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """
        计算风险平价权重

        每个资产对组合风险的贡献相等
        """
        n_assets = cov_matrix.shape[0]

        # 默认等风险预算
        if risk_budget is None:
            risk_budget = {col: 1.0 / n_assets for col in cov_matrix.columns}

        try:
            # 逆波动率加权 (风险平价近似)
            volatilities = np.sqrt(np.diag(cov_matrix))
            inv_vol = 1.0 / volatilities

            weights = inv_vol / inv_vol.sum()

            return dict(zip(cov_matrix.columns, weights))

        except Exception as e:
            logger.error(f"Risk parity calculation failed: {e}")
            #  fallback 到等权重
            return {col: 1.0 / n_assets for col in cov_matrix.columns}

    def adjust_position_by_volatility(self,
                                       base_position: float,
                                       current_vol: float,
                                       target_vol: float = 0.15) -> float:
        """
        根据波动率调整仓位

        波动率高时降低仓位，波动率低时增加仓位
        """
        if current_vol <= 0:
            return base_position

        # 波动率调整因子
        vol_adjustment = target_vol / current_vol

        # 限制调整范围
        vol_adjustment = np.clip(vol_adjustment, 0.5, 2.0)

        adjusted_position = base_position * vol_adjustment

        # 应用仓位限制
        return np.clip(adjusted_position, self.min_position_pct, self.max_position_pct)

    def check_stop_loss(self,
                        entry_price: float,
                        current_price: float,
                        highest_price: float,
                        holding_days: int) -> Dict[str, bool]:
        """
        检查止损条件

        Returns:
            {'individual': bool, 'trailing': bool, 'time_stop': bool}
        """
        # 个体止损
        individual_dd = (current_price - entry_price) / entry_price
        individual_stop = individual_dd <= -self.stop_loss_config['individual']

        # 移动止损
        trailing_dd = (current_price - highest_price) / highest_price
        trailing_stop = trailing_dd <= -self.stop_loss_config['trailing']

        # 时间止损
        time_stop = holding_days >= self.stop_loss_config['time_stop'] and individual_dd < 0

        return {
            'individual': bool(individual_stop),
            'trailing': bool(trailing_stop),
            'time_stop': bool(time_stop)
        }

    def get_risk_report(self,
                        returns: pd.Series,
                        prices: pd.Series,
                        positions: Optional[Dict[str, float]] = None) -> str:
        """生成风险报告"""
        metrics = self.get_risk_metrics(returns, prices)

        report = f"""
===== 风险报告 =====
VaR(95%): {metrics.var_95:.2%}
VaR(99%): {metrics.var_95:.2%}
CVaR(95%): {metrics.cvar_95:.2%}
CVaR(99%): {metrics.cvar_99:.2%}

最大回撤：{abs(metrics.max_drawdown):.2%}
波动率：{metrics.volatility:.2%}
夏普比率：{metrics.sharpe_ratio:.2f}
Sortino 比率：{metrics.sortino_ratio:.2f}
Calmar 比率：{metrics.calmar_ratio:.2f}
===================
"""
        return report
