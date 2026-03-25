#!/usr/bin/env python3
"""
增强版回测脚本 - 使用混合数据源和增强因子体系

用法:
    python3 scripts/backtest_enhanced.py 20250101 [20260324]
"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
import yaml
from typing import Dict, List

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_fetcher_hybrid import HybridDataFetcher
from src.scoring_enhanced import EnhancedScoringEngine
from src.fundamental_data import FundamentalDataFetcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """加载配置"""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class EnhancedBacktester:
    """增强版回测引擎"""
    
    def __init__(self, config: dict, start_date: str, end_date: str = None):
        self.config = config
        self.start_date = start_date
        self.end_date = end_date or datetime.now().strftime('%Y%m%d')
        
        self.fetcher = HybridDataFetcher()
        self.fundamental_fetcher = FundamentalDataFetcher()
        self.scoring_engine = EnhancedScoringEngine(config)
        
        # 策略参数
        self.top_n = config.get('strategy', {}).get('top_n', 5)
        self.buffer_n = config.get('strategy', {}).get('buffer_n', 8)
        
        # 交易成本
        portfolio_config = config.get('portfolio', {})
        self.commission = portfolio_config.get('commission', 0.0003)  # 万三
        self.slippage = portfolio_config.get('slippage', 0.001)  # 0.1%
        
        # 账户状态
        self.initial_capital = portfolio_config.get('initial_capital', 1000000)
        self.cash = self.initial_capital
        self.positions = {}  # {etf_code: shares}
        
        # 历史记录
        self.equity_curve = []
        self.trades = []
        self.daily_scores = []
    
    def get_benchmark_data(self) -> pd.DataFrame:
        """获取基准数据 (沪深 300 ETF)"""
        return self.fetcher.fetch_etf_history("510300", self.start_date)
    
    def fetch_all_etf_data(self) -> Dict[str, pd.DataFrame]:
        """获取所有 ETF 数据"""
        etf_data = {}
        indices = self.config.get('indices', [])
        
        for idx in indices:
            etf_code = idx.get('etf', '')
            if etf_code:
                logger.info(f"Fetching {etf_code} ({idx.get('name', '')})...")
                df = self.fetcher.fetch_etf_history(etf_code, self.start_date)
                if not df.empty:
                    etf_data[etf_code] = df
        
        logger.info(f"Fetched {len(etf_data)} ETFs")
        return etf_data
    
    def calc_transaction_cost(self, amount: float) -> float:
        """计算交易成本 (手续费 + 滑点)"""
        return amount * (self.commission + self.slippage)
    
    def rebalance(self, date: str, scores_rank: pd.DataFrame, etf_data: Dict[str, pd.DataFrame]):
        """调仓逻辑"""
        if scores_rank.empty:
            return
        
        # 当前持仓
        current_holdings = set(self.positions.keys())
        
        # 目标持仓 (前 top_n)
        target_holdings = set(scores_rank.head(self.top_n)['code'].tolist())
        
        # 缓冲持仓 (前 buffer_n)
        buffer_holdings = set(scores_rank.head(self.buffer_n)['code'].tolist())
        
        # 卖出：跌出 buffer_n 的持仓
        to_sell = current_holdings - buffer_holdings
        for etf_code in to_sell:
            if etf_code in self.positions and self.positions[etf_code] > 0:
                shares = self.positions[etf_code]
                
                # 获取当日价格
                if etf_code in etf_data and date in etf_data[etf_code].index:
                    price = etf_data[etf_code].loc[date, 'close']
                    sell_amount = shares * price
                    
                    # 扣除交易成本
                    cost = self.calc_transaction_cost(sell_amount)
                    self.cash += sell_amount - cost
                    
                    # 记录交易
                    self.trades.append({
                        'date': date,
                        'etf_code': etf_code,
                        'action': 'sell',
                        'shares': shares,
                        'price': price,
                        'amount': sell_amount,
                        'cost': cost
                    })
                    
                    self.positions[etf_code] = 0
                    logger.debug(f"Sold {etf_code}: {shares} shares @ {price:.3f}")
        
        # 买入：新进入 top_n 的持仓
        to_buy = target_holdings - current_holdings
        
        if to_buy:
            # 计算可用资金 (等权重分配)
            cash_per_etf = self.cash / len(to_buy)
            
            for etf_code in to_buy:
                if etf_code in etf_data and date in etf_data[etf_code].index:
                    price = etf_data[etf_code].loc[date, 'close']
                    
                    # 计算可买份额 (考虑交易成本)
                    available_cash = cash_per_etf
                    cost_rate = self.commission + self.slippage
                    effective_cash = available_cash / (1 + cost_rate)
                    shares = int(effective_cash / price / 100) * 100  # 100 的整数倍
                    
                    if shares > 0:
                        buy_amount = shares * price
                        cost = self.calc_transaction_cost(buy_amount)
                        self.cash -= (buy_amount + cost)
                        
                        self.positions[etf_code] = self.positions.get(etf_code, 0) + shares
                        
                        self.trades.append({
                            'date': date,
                            'etf_code': etf_code,
                            'action': 'buy',
                            'shares': shares,
                            'price': price,
                            'amount': buy_amount,
                            'cost': cost
                        })
                        
                        logger.debug(f"Bought {etf_code}: {shares} shares @ {price:.3f}")
    
    def calc_portfolio_value(self, date: str, etf_data: Dict[str, pd.DataFrame]) -> float:
        """计算组合总市值"""
        # 现金
        total = self.cash
        
        # 持仓市值
        for etf_code, shares in self.positions.items():
            if shares > 0 and etf_code in etf_data:
                if date in etf_data[etf_code].index:
                    price = etf_data[etf_code].loc[date, 'close']
                    total += shares * price
        
        return total
    
    def run(self):
        """运行回测"""
        logger.info(f"Starting backtest: {self.start_date} to {self.end_date}")
        logger.info(f"Initial capital: {self.initial_capital:,.0f}")
        
        # 获取所有 ETF 数据
        etf_data = self.fetch_all_etf_data()
        
        if not etf_data:
            logger.error("No ETF data available")
            return
        
        # 获取基准数据
        benchmark_data = self.get_benchmark_data()
        
        # 获取北向资金数据
        northbound_df = self.fetcher.fetch_northbound_flow(self.start_date)
        
        # 获取所有日期
        all_dates = set()
        for df in etf_data.values():
            all_dates.update(df.index)
        all_dates = sorted(all_dates)
        
        # 过滤日期范围
        start_dt = pd.to_datetime(self.start_date)
        end_dt = pd.to_datetime(self.end_date)
        all_dates = [d for d in all_dates if start_dt <= d <= end_dt]
        
        logger.info(f"Backtest period: {len(all_dates)} trading days")
        
        # 逐日回测
        last_rebalance_date = None
        rebalance_frequency = self.config.get('strategy', {}).get('rebalance_frequency', 'weekly')
        
        for i, date in enumerate(all_dates):
            date_str = date.strftime('%Y-%m-%d')
            
            # 获取当日有数据的 ETF
            etf_data_today = {
                code: df.loc[:date] 
                for code, df in etf_data.items() 
                if date in df.index and len(df.loc[:date]) >= 60  # 至少 60 天数据
            }
            
            if len(etf_data_today) < 3:
                # 数据不足，跳过
                continue
            
            # 计算评分
            scores_dict = {}
            for etf_code, df in etf_data_today.items():
                # 获取北向资金指标
                nb_metrics = self.fetcher.calc_northbound_metrics(
                    northbound_df.loc[:date] if not northbound_df.empty else pd.DataFrame()
                )
                
                # 获取 ETF 份额指标
                etf_shares_df = self.fetcher.fetch_etf_shares(etf_code, self.start_date)
                etf_shares_metrics = self.fetcher.calc_etf_shares_metrics(
                    etf_shares_df.loc[:date] if not etf_shares_df.empty else pd.DataFrame()
                )
                
                # 查找对应的指数代码
                index_code = None
                for idx in self.config.get('indices', []):
                    if idx.get('etf') == etf_code:
                        index_code = idx.get('code')
                        break
                
                scores = self.scoring_engine.score_index(
                    df,
                    benchmark_data=benchmark_data.loc[:date] if not benchmark_data.empty else None,
                    northbound_metrics=nb_metrics,
                    etf_shares_metrics=etf_shares_metrics,
                    fundamental_fetcher=self.fundamental_fetcher,
                    index_code=index_code
                )
                
                scores_dict[etf_code] = scores
            
            # 排名
            rank_df = self.scoring_engine.rank_indices(scores_dict)
            
            # 记录每日评分
            if not rank_df.empty:
                self.daily_scores.append({
                    'date': date_str,
                    'top_5': rank_df.head(5)['code'].tolist(),
                    'top_scores': rank_df.head(5)['total_score'].tolist()
                })
            
            # 判断是否调仓
            should_rebalance = False
            
            if last_rebalance_date is None:
                should_rebalance = True
            else:
                if rebalance_frequency == 'weekly':
                    # 每周一调仓
                    if date.weekday() == 0 and (date - last_rebalance_date).days >= 5:
                        should_rebalance = True
                elif rebalance_frequency == 'monthly':
                    # 每月第一个交易日调仓
                    if date.day <= 5 and (date - last_rebalance_date).days >= 20:
                        should_rebalance = True
            
            if should_rebalance:
                logger.info(f"Rebalancing on {date_str}...")
                self.rebalance(date_str, rank_df, etf_data)
                last_rebalance_date = date
            
            # 计算组合价值
            portfolio_value = self.calc_portfolio_value(date, etf_data)
            self.equity_curve.append({
                'date': date_str,
                'equity': portfolio_value,
                'cash': self.cash,
                'positions_count': sum(1 for s in self.positions.values() if s > 0)
            })
        
        # 生成报告
        self.generate_report()
    
    def generate_report(self):
        """生成回测报告"""
        if not self.equity_curve:
            logger.warning("No equity curve data")
            return
        
        df = pd.DataFrame(self.equity_curve)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        # 计算收益指标
        initial = df['equity'].iloc[0]
        final = df['equity'].iloc[-1]
        total_return = (final - initial) / initial
        
        # 年化收益
        days = (df.index[-1] - df.index[0]).days
        annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0
        
        # 最大回撤
        df['cummax'] = df['equity'].cummax()
        df['drawdown'] = (df['equity'] - df['cummax']) / df['cummax']
        max_drawdown = df['drawdown'].min()
        
        # 夏普比率 (假设无风险利率 3%)
        df['daily_return'] = df['equity'].pct_change()
        sharpe = (df['daily_return'].mean() - 0.03/252) / df['daily_return'].std() * np.sqrt(252) if len(df) > 1 else 0
        
        # 交易统计
        trades_df = pd.DataFrame(self.trades)
        total_trades = len(trades_df)
        total_cost = trades_df['cost'].sum() if not trades_df.empty else 0
        
        print("\n" + "="*60)
        print("📊 增强版回测报告")
        print("="*60)
        print(f"回测期间：{df.index[0].date()} ~ {df.index[-1].date()} ({days} 天)")
        print(f"初始资金：{initial:,.0f}")
        print(f"最终价值：{final:,.0f}")
        print(f"总收益率：{total_return*100:.2f}%")
        print(f"年化收益：{annual_return*100:.2f}%")
        print(f"最大回撤：{max_drawdown*100:.2f}%")
        print(f"夏普比率：{sharpe:.2f}")
        print(f"交易次数：{total_trades}")
        print(f"交易成本：{total_cost:,.0f}")
        print(f"调仓频率：{self.config.get('strategy', {}).get('rebalance_frequency', 'weekly')}")
        print("="*60)
        
        # 保存报告
        report_path = Path(__file__).parent.parent / 'reports' / f'backtest_enhanced_{self.start_date}.csv'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(report_path)
        logger.info(f"Report saved to {report_path}")
        
        # 保存交易记录
        if self.trades:
            trades_path = Path(__file__).parent.parent / 'reports' / f'trades_enhanced_{self.start_date}.csv'
            trades_df = pd.DataFrame(self.trades)
            trades_df.to_csv(trades_path, index=False)
            logger.info(f"Trades saved to {trades_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/backtest_enhanced.py <start_date> [end_date]")
        print("Example: python3 scripts/backtest_enhanced.py 20250101 20260324")
        sys.exit(1)
    
    start_date = sys.argv[1]
    end_date = sys.argv[2] if len(sys.argv) > 2 else None
    
    config = load_config()
    backtester = EnhancedBacktester(config, start_date, end_date)
    backtester.run()
