"""
模拟投资组合
"""
from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """持仓"""
    code: str
    name: str
    shares: int
    avg_price: float
    entry_date: str


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
    """模拟投资组合"""
    
    def __init__(self, initial_capital: float = 1_000_000, 
                 commission_rate: float = 0.0003,
                 slippage: float = 0.001):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate  # 万三
        self.slippage = slippage  # 0.1% 滑点
        
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.history: List[dict] = []  # 每日净值记录
    
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
