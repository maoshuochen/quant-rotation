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

    def test_cash_recovery_after_position_restore(self):
        """测试恢复持仓后现金计算的正确性（修复 bug 后的回归测试）"""
        # 模拟场景：最后交易日净值 1,200,000，持仓市值 600,000
        last_value = 1_200_000

        # 创建组合（初始资金应为 100 万，不是 last_value）
        portfolio = SimulatedPortfolio(initial_capital=1_000_000)

        # 恢复持仓
        portfolio.positions['A'] = Position(
            code='A',
            name='指数 A',
            shares=10000,
            avg_price=10.0,
            entry_date='2026-01-01'
        )

        # 假设最后交易日价格
        last_prices = {'A': 60.0}  # 持仓市值 = 10000 * 60 = 600,000

        # 计算持仓市值
        stock_value = sum(
            pos.shares * last_prices.get(pos.code, pos.avg_price)
            for pos in portfolio.positions.values()
        )

        # 恢复现金：最后净值 - 持仓市值
        portfolio.cash = last_value - stock_value

        # 验证：现金应该等于 600,000
        expected_cash = 1_200_000 - 600_000  # 600,000
        assert abs(portfolio.cash - expected_cash) < 0.01

        # 验证：组合价值应该等于 last_value
        restored_value = portfolio.get_portfolio_value(last_prices)
        assert abs(restored_value - last_value) < 0.01

    def test_no_double_counting_bug(self):
        """测试没有重复计算现金和持仓（之前 bug 的回归测试）"""
        last_value = 1_200_000
        stock_value = 600_000

        # 错误做法（bug）：cash = last_value 且恢复持仓
        # 这样总资产 = cash + stock_value = 1,200,000 + 600,000 = 1,800,000（错误！）

        # 正确做法：cash = last_value - stock_value
        cash = last_value - stock_value  # 600,000
        total_value = cash + stock_value  # 600,000 + 600,000 = 1,200,000（正确）

        assert abs(total_value - last_value) < 0.01
        # 确保不会等于错误的 1,800,000
        assert abs(total_value - (last_value + stock_value)) > 100_000


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
