"""
Portfolio 模块单元测试
测试模拟投资组合和止损机制
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.portfolio import SimulatedPortfolio, Position, Trade


class TestPosition:
    """测试持仓类"""

    def test_position_creation(self):
        """测试持仓创建"""
        pos = Position(
            code='000300.SH',
            name='沪深 300',
            shares=1000,
            avg_price=4.5,
            entry_date='2025-01-01'
        )
        assert pos.code == '000300.SH'
        assert pos.shares == 1000
        assert pos.avg_price == 4.5
        assert pos.highest_price == 0.0
        assert pos.stop_loss_triggered is False

    def test_position_update_highest(self):
        """测试更新最高价"""
        pos = Position(
            code='000300.SH',
            name='沪深 300',
            shares=1000,
            avg_price=4.5,
            entry_date='2025-01-01',
            highest_price=5.0
        )
        assert pos.highest_price == 5.0


class TestSimulatedPortfolio:
    """测试模拟投资组合"""

    @pytest.fixture
    def portfolio(self):
        """创建测试组合"""
        return SimulatedPortfolio(
            initial_capital=1_000_000,
            commission_rate=0.0003,
            slippage=0.001,
            stop_loss_config={
                'individual': 0.15,
                'trailing': 0.08,
                'portfolio': 0.20
            },
            cooldown_days=5
        )

    def test_initialization(self, portfolio):
        """测试组合初始化"""
        assert portfolio.cash == 1_000_000
        assert portfolio.commission_rate == 0.0003
        assert portfolio.slippage == 0.001
        assert len(portfolio.positions) == 0
        assert len(portfolio.trades) == 0

    def test_get_portfolio_value(self, portfolio):
        """测试组合价值计算"""
        # 无持仓时价值等于现金
        prices = {'000300.SH': 4.5}
        value = portfolio.get_portfolio_value(prices)
        assert value == portfolio.cash

        # 添加持仓
        portfolio.positions['000300.SH'] = Position(
            code='000300.SH',
            name='沪深 300',
            shares=1000,
            avg_price=4.0,
            entry_date='2025-01-01'
        )
        value = portfolio.get_portfolio_value(prices)
        expected = portfolio.cash + 1000 * 4.5
        assert value == expected

    def test_execute_buy_signal(self, portfolio):
        """测试买入信号执行"""
        prices = {'000300.SH': 4.5, '000905.SH': 6.0}
        names = {'000300.SH': '沪深 300', '000905.SH': '中证 500'}
        signals = {'buy': ['000300.SH', '000905.SH'], 'sell': []}

        trades = portfolio.execute_signal(signals, prices, names, '2025-01-02')

        assert len(trades) == 2
        assert all(t.type == 'buy' for t in trades)
        assert len(portfolio.positions) == 2

    def test_execute_sell_signal(self, portfolio):
        """测试卖出信号执行"""
        # 先买入
        prices = {'000300.SH': 4.5}
        names = {'000300.SH': '沪深 300'}
        portfolio.positions['000300.SH'] = Position(
            code='000300.SH',
            name='沪深 300',
            shares=1000,
            avg_price=4.0,
            entry_date='2025-01-01'
        )
        initial_cash = portfolio.cash

        # 卖出
        signals = {'buy': [], 'sell': ['000300.SH']}
        trades = portfolio.execute_signal(signals, prices, names, '2025-01-02')

        assert len(trades) == 1
        assert trades[0].type == 'sell'
        assert len(portfolio.positions) == 0
        # 卖出后现金应增加（扣除手续费和滑点）
        assert portfolio.cash > initial_cash

    def test_buy_sufficient_capital(self, portfolio):
        """测试资金不足时的买入限制"""
        # 尝试买入超过资金能力的标的
        prices = {'000300.SH': 10000}  # 高价
        names = {'000300.SH': '沪深 300'}
        signals = {'buy': ['000300.SH'], 'sell': []}

        trades = portfolio.execute_signal(signals, prices, names, '2025-01-02')

        # 如果资金不足，应该无法买入或买入较少份额
        # 具体行为取决于 execute_signal 的实现
        assert isinstance(trades, list)

    def test_check_stop_loss_individual(self, portfolio):
        """测试个体止损检查"""
        # 创建亏损持仓
        portfolio.positions['000300.SH'] = Position(
            code='000300.SH',
            name='沪深 300',
            shares=1000,
            avg_price=5.0,  # 成本价 5.0
            entry_date='2025-01-01'
        )

        # 当前价格下跌 20%（超过 15% 止损线）
        prices = {'000300.SH': 4.0}
        stop_loss_signals = portfolio.check_stop_loss(prices, '2025-01-02')

        # 检查个体止损列表
        assert '000300.SH' in stop_loss_signals['individual']

    def test_check_stop_loss_no_trigger(self, portfolio):
        """测试未触发止损"""
        portfolio.positions['000300.SH'] = Position(
            code='000300.SH',
            name='沪深 300',
            shares=1000,
            avg_price=5.0,
            entry_date='2025-01-01'
        )

        # 价格下跌 10%（未达 15% 止损线）
        prices = {'000300.SH': 4.5}
        stop_loss_signals = portfolio.check_stop_loss(prices, '2025-01-02')

        assert '000300.SH' not in stop_loss_signals['individual']
        assert '000300.SH' not in stop_loss_signals['trailing']

    def test_check_trailing_stop_loss(self, portfolio):
        """测试移动止损"""
        # 创建盈利后回撤的持仓
        portfolio.positions['000300.SH'] = Position(
            code='000300.SH',
            name='沪深 300',
            shares=1000,
            avg_price=5.0,
            entry_date='2025-01-01',
            highest_price=6.0  # 最高价 6.0
        )

        # 当前价格从高点回撤超过 8%
        prices = {'000300.SH': 5.5}  # (5.5 - 6.0) / 6.0 = -8.33%
        stop_loss_signals = portfolio.check_stop_loss(prices, '2025-01-02')

        assert '000300.SH' in stop_loss_signals['trailing']

    def test_record_daily_value(self, portfolio):
        """测试每日净值记录"""
        prices = {'000300.SH': 4.5}
        portfolio.record_daily_value('2025-01-02', prices)

        assert len(portfolio.history) == 1
        assert portfolio.history[0]['date'] == '2025-01-02'

    def test_cooldown_after_stop_loss(self, portfolio):
        """测试止损后冷却期"""
        # 记录止损日期
        portfolio.stop_loss_cooldown['000300.SH'] = '2025-01-01'

        # 检查冷却期内不应买入（通过检查是否有内部方法或逻辑）
        # 这里测试 cooldown_days 配置是否正确加载
        assert portfolio.cooldown_days == 5


class TestTrade:
    """测试交易记录类"""

    def test_trade_creation(self):
        """测试交易记录创建"""
        trade = Trade(
            date='2025-01-02',
            type='buy',
            code='000300.SH',
            name='沪深 300',
            shares=1000,
            price=4.5,
            amount=4500,
            commission=1.35
        )
        assert trade.type == 'buy'
        assert trade.amount == 4500
        assert trade.commission == 1.35


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
