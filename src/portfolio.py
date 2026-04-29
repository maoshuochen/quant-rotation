"""
模拟投资组合（带止损机制）
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict
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
                 stop_loss_config: Optional[Dict[str, float]] = None,
                 cooldown_days: int = 5):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate  # 万三
        self.slippage = slippage  # 0.1% 滑点

        # 止损配置
        self.stop_loss_config = stop_loss_config or {
            'trailing': 0.08,
            'cooldown_days': cooldown_days,
        }

        # 冷却期配置（止损后多少天内不买入同一标的）
        self.cooldown_days = cooldown_days
        self.stop_loss_cooldown: Dict[str, str] = {}  # {code: last_stop_loss_date}

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
            # 可用资金：默认满仓建仓，仅受现金余额和手续费约束。
            available = self.cash
            amount_per_stock = available / num_buy

            for code in to_buy:
                # 检查冷却期（止损后 cooldown_days 天内不买入）
                if self.is_in_cooldown(code, date):
                    logger.info(f"Skip buy {code}: in cooldown (stop loss within {self.cooldown_days} days)")
                    continue

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

    def execute_rebalance(
        self,
        target_codes: List[str],
        prices: Dict[str, float],
        names: Dict[str, str],
        date: str,
        min_trade_value: float = 1000.0,
    ) -> List[Trade]:
        """按目标持仓集合做等权再平衡。"""
        executed_trades: List[Trade] = []
        eligible_targets = [
            code
            for code in target_codes
            if code in self.positions or not self.is_in_cooldown(code, date)
        ]
        eligible_targets = [code for code in eligible_targets if code in prices]
        if not eligible_targets and not self.positions:
            return executed_trades

        total_value = self.get_portfolio_value(prices)
        target_value = total_value / len(eligible_targets) if eligible_targets else 0.0
        target_set = set(eligible_targets)

        def sell_shares(code: str, shares: int) -> None:
            if shares <= 0 or code not in self.positions:
                return
            pos = self.positions[code]
            shares_to_sell = min(shares, pos.shares)
            price = prices.get(code, pos.avg_price)
            exec_price = price * (1 - self.slippage)
            amount = shares_to_sell * exec_price
            if amount < min_trade_value and shares_to_sell < pos.shares:
                return
            commission = amount * self.commission_rate
            self.cash += amount - commission
            trade = Trade(
                date=date,
                type='sell',
                code=code,
                name=pos.name,
                shares=shares_to_sell,
                price=exec_price,
                amount=amount,
                commission=commission,
            )
            executed_trades.append(trade)
            self.trades.append(trade)
            remaining = pos.shares - shares_to_sell
            if remaining <= 0:
                del self.positions[code]
            else:
                pos.shares = remaining
                self.positions[code] = pos

        def buy_value(code: str, desired_value: float) -> None:
            if desired_value < min_trade_value:
                return
            price = prices.get(code)
            if price is None:
                return
            exec_price = price * (1 + self.slippage)
            shares = int(desired_value / (exec_price * (1 + self.commission_rate)))
            if shares <= 0:
                return
            amount = shares * exec_price
            commission = amount * self.commission_rate
            total_cost = amount + commission
            if total_cost > self.cash:
                shares = int(self.cash / (exec_price * (1 + self.commission_rate)))
                if shares <= 0:
                    return
                amount = shares * exec_price
                commission = amount * self.commission_rate
                total_cost = amount + commission
            if amount < min_trade_value:
                return
            self.cash -= total_cost
            if code in self.positions:
                pos = self.positions[code]
                old_amount = pos.shares * pos.avg_price
                new_shares = pos.shares + shares
                pos.avg_price = (old_amount + amount) / new_shares
                pos.shares = new_shares
                pos.highest_price = max(pos.highest_price, price)
                self.positions[code] = pos
            else:
                self.positions[code] = Position(
                    code=code,
                    name=names.get(code, code),
                    shares=shares,
                    avg_price=exec_price,
                    entry_date=date,
                    highest_price=price,
                )
            trade = Trade(
                date=date,
                type='buy',
                code=code,
                name=names.get(code, code),
                shares=shares,
                price=exec_price,
                amount=amount,
                commission=commission,
            )
            executed_trades.append(trade)
            self.trades.append(trade)

        # 先卖出非目标和超配部分，释放现金。
        for code in list(self.positions.keys()):
            pos = self.positions[code]
            price = prices.get(code, pos.avg_price)
            current_value = pos.shares * price
            if code not in target_set:
                sell_shares(code, pos.shares)
                continue
            excess_value = current_value - target_value
            if excess_value > min_trade_value:
                sell_shares(code, int(excess_value / (price * (1 - self.slippage))))

        # 再买入低配或新增目标。
        for code in eligible_targets:
            current_value = 0.0
            if code in self.positions:
                current_value = self.positions[code].shares * prices.get(code, self.positions[code].avg_price)
            shortage = target_value - current_value
            if shortage > min_trade_value:
                buy_value(code, shortage)

        return executed_trades
    
    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """计算当前总资产"""
        stock_value = sum(
            pos.shares * current_prices.get(pos.code, pos.avg_price)
            for pos in self.positions.values()
        )
        total_value = self.cash + stock_value

        # 数据完整性检查：确保现金不为负数（除非有杠杆）
        if self.cash < -1e-6:
            logger.warning(f"现金为负数：cash={self.cash:.2f}, 日期可能有问题")

        # 确保总价值合理（至少应该接近初始资金的一部分）
        if total_value < 0:
            logger.error(f"总资产为负数！cash={self.cash:.2f}, stock_value={stock_value:.2f}")

        return total_value
    
    def get_return(self, current_prices: Dict[str, float]) -> float:
        """计算收益率"""
        value = self.get_portfolio_value(current_prices)
        return (value - self.initial_capital) / self.initial_capital

    def is_in_cooldown(self, code: str, date: str) -> bool:
        """
        检查标的是否在冷却期内

        Args:
            code: 标的代码
            date: 当前日期 (YYYY-MM-DD)

        Returns:
            True 如果在冷却期内，False 否则
        """
        if code not in self.stop_loss_cooldown:
            return False

        last_stop_date = self.stop_loss_cooldown[code]
        try:
            from datetime import datetime
            stop_dt = datetime.strptime(last_stop_date, '%Y-%m-%d')
            current_dt = datetime.strptime(date, '%Y-%m-%d')
            days_since_stop = (current_dt - stop_dt).days
            return days_since_stop < self.cooldown_days
        except Exception:
            return False

    def get_cooldown_status(self) -> Dict[str, int]:
        """
        获取所有冷却期状态

        Returns:
            {code: remaining_days}
        """
        status = {}
        from datetime import datetime
        today = datetime.now()
        for code, stop_date in self.stop_loss_cooldown.items():
            try:
                stop_dt = datetime.strptime(stop_date, '%Y-%m-%d')
                days_since = (today - stop_dt).days
                if days_since < self.cooldown_days:
                    status[code] = self.cooldown_days - days_since
            except Exception:
                continue
        return status
    
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
        portfolio_threshold = self.stop_loss_config.get('portfolio')
        individual_threshold = self.stop_loss_config.get('individual')
        trailing_threshold = self.stop_loss_config.get('trailing')

        # 1. 组合止损检查
        current_value = self.get_portfolio_value(current_prices)
        portfolio_drawdown = (self.peak_value - current_value) / self.peak_value

        if portfolio_threshold is not None and portfolio_drawdown >= portfolio_threshold:
            # 组合止损触发，清空所有持仓
            for code in list(self.positions.keys()):
                signals['portfolio'].append(code)
            logger.warning(
                f"组合止损触发！回撤={portfolio_drawdown:.1%}, "
                f"阈值={portfolio_threshold:.1%}"
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
            if individual_threshold is not None and individual_drawdown <= -individual_threshold:
                if code not in signals['portfolio']:  # 避免重复
                    signals['individual'].append(code)
                logger.warning(
                    f"个体止损触发：{code}, 回撤={individual_drawdown:.1%}, "
                    f"阈值={individual_threshold:.1%}"
                )

            # 移动止损（从最高价计算）
            if pos.highest_price > 0:
                trailing_drawdown = (current_price - pos.highest_price) / pos.highest_price
                if trailing_threshold is not None and trailing_drawdown <= -trailing_threshold:
                    if code not in signals['portfolio'] and code not in signals['individual']:
                        signals['trailing'].append(code)
                    logger.warning(
                        f"移动止损触发：{code}, 从高点回撤={trailing_drawdown:.1%}, "
                        f"阈值={trailing_threshold:.1%}"
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

            # 记录冷却期（止损后 cooldown_days 天内不买入）
            self.stop_loss_cooldown[code] = date

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

        # 数据验证：检查单日涨跌幅是否异常
        if self.history:
            prev_value = self.history[-1]['value']
            daily_return = (value - prev_value) / prev_value if prev_value > 0 else 0

            # 警告：单日涨跌幅超过 20%（阈值可配置）
            if abs(daily_return) > 0.20:
                logger.warning(
                    f"单日涨跌幅异常：{date}, 涨跌幅={daily_return*100:.2f}%, "
                    f"前一日={prev_value:,.2f}, 当日={value:,.2f}"
                )

            # 警告：单日涨跌幅超过 50% 视为严重错误
            if abs(daily_return) > 0.50:
                logger.error(
                    f"严重异常：单日涨跌幅超过 50%！{date}, "
                    f"涨跌幅={daily_return*100:.2f}%, cash={self.cash:.2f}, "
                    f"positions={len(self.positions)}"
                )

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

    def serialize_positions(self) -> List[dict]:
        """导出持仓状态，供回测断点续跑复用。"""
        return [asdict(pos) for pos in self.positions.values()]

    def restore_positions(self, positions_data: List[dict]):
        """恢复持仓状态。"""
        for pos_data in positions_data:
            self.positions[pos_data["code"]] = Position(**pos_data)
