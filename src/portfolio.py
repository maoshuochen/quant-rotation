"""
模拟投资组合（带止损机制）
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """持仓（支持止损跟踪）"""
    code: str
    name: str
    shares: int
    avg_price: float
    entry_date: str
    highest_price: float = 0.0  # 持仓期间最高价（用于移动止损）
    stop_loss_triggered: bool = False  # 是否已触发止损


@dataclass
class Trade:
    """交易记录"""
    date: str
    type: str  # 'buy' or 'sell'
    code: str
    name: str
    shares: int
    price: float
    amount: float
    commission: float


class SimulatedPortfolio:
    """模拟投资组合（支持止损）"""

    def __init__(self,
                 initial_capital: float = 1_000_000,
                 commission_rate: float = 0.0003,
                 slippage: float = 0.001,
                 stop_loss_config: Optional[Dict[str, float]] = None):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate  # 万三
        self.slippage = slippage  # 0.1% 滑点

        # 止损配置
        self.stop_loss_config = stop_loss_config or {
            'individual': 0.15,    # 个体止损 15%
            'trailing': 0.08,      # 移动止损 8%
            'portfolio': 0.10      # 组合止损 10%
        }

        # 组合峰值（用于组合止损）
        self.peak_value = initial_capital
        self.portfolio_stop_loss_triggered = False

        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.history: List[dict] = []  # 每日净值记录
        self.stop_loss_trades: List[Dict] = []  # 止损交易记录
    
    def execute_signal(self, 
                       signals: dict, 
                       prices: Dict[str, float],
                       names: Dict[str, str],
                       date: str) -> List[Trade]:
        """
        执行调仓信号
        
        Args:
            signals: 买卖信号
            prices: 当前价格
            names: 指数名称
            date: 交易日期
            
        Returns:
            交易列表
        """
        executed_trades = []
        
        # 1. 先卖出
        for code in signals.get('sell', []):
            if code in self.positions:
                pos = self.positions[code]
                price = prices.get(code, pos.avg_price)
                
                # 应用滑点 (卖出价格更低)
                exec_price = price * (1 - self.slippage)
                
                # 计算金额和手续费
                amount = pos.shares * exec_price
                commission = amount * self.commission_rate
                net_amount = amount - commission
                
                # 更新现金
                self.cash += net_amount
                
                # 记录交易
                trade = Trade(
                    date=date,
                    type='sell',
                    code=code,
                    name=pos.name,
                    shares=pos.shares,
                    price=exec_price,
                    amount=amount,
                    commission=commission
                )
                executed_trades.append(trade)
                self.trades.append(trade)
                
                # 删除持仓
                del self.positions[code]
                
                logger.info(f"Sold {pos.shares} shares of {code} @ {exec_price:.2f}")
        
        # 2. 再买入 (等权重)
        to_buy = signals.get('buy', [])
        num_buy = len(to_buy)
        
        if num_buy > 0:
            # 可用资金 (留 5% 现金)
            available = self.cash * 0.95
            amount_per_stock = available / num_buy
            
            for code in to_buy:
                price = prices.get(code)
                if price is None:
                    logger.warning(f"No price for {code}, skipping")
                    continue
                
                # 应用滑点 (买入价格更高)
                exec_price = price * (1 + self.slippage)
                
                # 计算股数
                shares = int(amount_per_stock / exec_price)
                if shares == 0:
                    continue
                
                # 计算金额和手续费
                amount = shares * exec_price
                commission = amount * self.commission_rate
                total_cost = amount + commission
                
                # 检查现金是否足够
                if total_cost > self.cash:
                    logger.warning(f"Insufficient cash for {code}")
                    continue
                
                # 更新现金
                self.cash -= total_cost
                
                # 更新持仓
                self.positions[code] = Position(
                    code=code,
                    name=names.get(code, code),
                    shares=shares,
                    avg_price=exec_price,
                    entry_date=date
                )
                
                # 记录交易
                trade = Trade(
                    date=date,
                    type='buy',
                    code=code,
                    name=names.get(code, code),
                    shares=shares,
                    price=exec_price,
                    amount=amount,
                    commission=commission
                )
                executed_trades.append(trade)
                self.trades.append(trade)
                
                logger.info(f"Bought {shares} shares of {code} @ {exec_price:.2f}")
        
        return executed_trades
    
    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """计算当前总资产"""
        stock_value = sum(
            pos.shares * current_prices.get(pos.code, pos.avg_price)
            for pos in self.positions.values()
        )
        return self.cash + stock_value
    
    def get_return(self, current_prices: Dict[str, float]) -> float:
        """计算收益率"""
        value = self.get_portfolio_value(current_prices)
        return (value - self.initial_capital) / self.initial_capital
    
    def check_stop_loss(self, current_prices: Dict[str, float], date: str) -> Dict[str, List[str]]:
        """
        检查止损条件

        Args:
            current_prices: 当前价格
            date: 检查日期

        Returns:
            {'individual': [...], 'trailing': [...], 'portfolio': [...]}
        """
        signals = {
            'individual': [],  # 个体止损
            'trailing': [],    # 移动止损
            'portfolio': []    # 组合止损
        }

        # 1. 组合止损检查
        current_value = self.get_portfolio_value(current_prices)
        portfolio_drawdown = (self.peak_value - current_value) / self.peak_value

        if portfolio_drawdown >= self.stop_loss_config['portfolio']:
            # 组合止损触发，清空所有持仓
            for code in list(self.positions.keys()):
                signals['portfolio'].append(code)
            logger.warning(
                f"组合止损触发！回撤={portfolio_drawdown:.1%}, "
                f"阈值={self.stop_loss_config['portfolio']:.1%}"
            )
            self.portfolio_stop_loss_triggered = True

        # 2. 个体持仓止损检查
        for code, pos in self.positions.items():
            current_price = current_prices.get(code, pos.avg_price)

            # 更新最高价
            if current_price > pos.highest_price:
                pos.highest_price = current_price
                self.positions[code] = pos  # 更新持仓

            # 个体止损（从成本价计算）
            individual_drawdown = (current_price - pos.avg_price) / pos.avg_price
            if individual_drawdown <= -self.stop_loss_config['individual']:
                if code not in signals['portfolio']:  # 避免重复
                    signals['individual'].append(code)
                logger.warning(
                    f"个体止损触发：{code}, 回撤={individual_drawdown:.1%}, "
                    f"阈值={self.stop_loss_config['individual']:.1%}"
                )

            # 移动止损（从最高价计算）
            if pos.highest_price > 0:
                trailing_drawdown = (current_price - pos.highest_price) / pos.highest_price
                if trailing_drawdown <= -self.stop_loss_config['trailing']:
                    if code not in signals['portfolio'] and code not in signals['individual']:
                        signals['trailing'].append(code)
                    logger.warning(
                        f"移动止损触发：{code}, 从高点回撤={trailing_drawdown:.1%}, "
                        f"阈值={self.stop_loss_config['trailing']:.1%}"
                    )

        return signals

    def execute_stop_loss(self,
                          signals: Dict[str, List[str]],
                          prices: Dict[str, float],
                          names: Dict[str, str],
                          date: str) -> List[Trade]:
        """
        执行止损交易

        Args:
            signals: 止损信号（来自 check_stop_loss）
            prices: 当前价格
            names: 指数名称
            date: 交易日期

        Returns:
            交易列表
        """
        executed_trades = []
        all_sell_codes = set()

        # 收集所有需要卖出的代码
        for signal_type in ['portfolio', 'individual', 'trailing']:
            all_sell_codes.update(signals.get(signal_type, []))

        if not all_sell_codes:
            return executed_trades

        # 执行卖出
        for code in all_sell_codes:
            if code not in self.positions:
                continue

            pos = self.positions[code]
            price = prices.get(code, pos.avg_price)

            # 应用滑点（卖出价格更低）
            exec_price = price * (1 - self.slippage)

            # 计算金额和手续费
            amount = pos.shares * exec_price
            commission = amount * self.commission_rate
            net_amount = amount - commission

            # 更新现金
            self.cash += net_amount

            # 确定止损类型
            if code in signals['portfolio']:
                stop_type = 'portfolio'
            elif code in signals['individual']:
                stop_type = 'individual'
            else:
                stop_type = 'trailing'

            # 记录交易
            trade = Trade(
                date=date,
                type='sell',
                code=code,
                name=pos.name,
                shares=pos.shares,
                price=exec_price,
                amount=amount,
                commission=commission
            )
            executed_trades.append(trade)
            self.trades.append(trade)

            # 记录止损交易
            self.stop_loss_trades.append({
                'date': date,
                'code': code,
                'type': stop_type,
                'shares': pos.shares,
                'price': exec_price,
                'loss_pct': (exec_price - pos.avg_price) / pos.avg_price
            })

            # 删除持仓
            del self.positions[code]

            logger.info(
                f"止损卖出 {pos.shares} 股 {code} @ {exec_price:.2f} "
                f"({stop_type}止损，亏损{(exec_price - pos.avg_price) / pos.avg_price:.1%})"
            )

        return executed_trades

    def update_peak_value(self, current_prices: Dict[str, float]):
        """
        更新组合峰值（用于组合止损）

        Args:
            current_prices: 当前价格
        """
        current_value = self.get_portfolio_value(current_prices)
        if current_value > self.peak_value:
            self.peak_value = current_value
            # 重置组合止损标志
            self.portfolio_stop_loss_triggered = False

    def get_position_weights(self, current_prices: Dict[str, float]) -> Dict[str, float]:
        """计算各持仓权重"""
        total_value = self.get_portfolio_value(current_prices)
        if total_value == 0:
            return {}

        weights = {}
        for code, pos in self.positions.items():
            value = pos.shares * current_prices.get(code, pos.avg_price)
            weights[code] = value / total_value

        return weights

    def record_daily_value(self, date: str, current_prices: Dict[str, float]):
        """记录每日净值"""
        # 先更新峰值
        self.update_peak_value(current_prices)

        value = self.get_portfolio_value(current_prices)
        nav = value / self.initial_capital  # 单位净值
        return_pct = self.get_return(current_prices)
        
        record = {
            'date': date,
            'value': value,
            'nav': nav,
            'return': return_pct,
            'cash': self.cash,
            'num_positions': len(self.positions)
        }
        
        self.history.append(record)
        return record
    
    def get_summary(self, current_prices: Dict[str, float]) -> dict:
        """获取组合摘要"""
        value = self.get_portfolio_value(current_prices)
        return_pct = self.get_return(current_prices)
        weights = self.get_position_weights(current_prices)
        
        return {
            'total_value': value,
            'cash': self.cash,
            'return': return_pct,
            'num_positions': len(self.positions),
            'weights': weights,
            'positions': [
                {
                    'code': pos.code,
                    'name': pos.name,
                    'shares': pos.shares,
                    'avg_price': pos.avg_price,
                    'current_price': current_prices.get(pos.code, pos.avg_price),
                    'weight': weights.get(pos.code, 0)
                }
                for pos in self.positions.values()
            ]
        }
