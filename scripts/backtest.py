#!/usr/bin/env python3
"""
回测脚本 - 使用 VectorBT
"""
import sys
import yaml
import logging
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data_fetcher import IndexDataFetcher
from src.factor_engine import FactorEngine
from src.scoring import ScoringEngine

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """加载配置"""
    config_path = project_root / 'config' / 'config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def run_backtest(start_date: str = "2018-01-01", 
                 end_date: str = None,
                 initial_capital: float = 1_000_000,
                 rebalance_freq: str = 'weekly'):
    """
    运行回测
    
    Args:
        start_date: 开始日期
        end_date: 结束日期 (默认今天)
        initial_capital: 初始资金
        rebalance_freq: 调仓频率 ('weekly' or 'monthly')
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    logger.info(f"Running backtest from {start_date} to {end_date}")
    
    # 加载配置
    config = load_config()
    indices = config['indices']
    
    # 获取所有指数数据
    fetcher = IndexDataFetcher()
    factor_engine = FactorEngine()
    scorer = ScoringEngine(config.get('factor_weights'))
    
    # 获取基准
    benchmark_df = fetcher.fetch_index_history("000300.SH")
    benchmark_prices = benchmark_df['close'] if not benchmark_df.empty else None
    
    # 获取所有指数数据
    index_data = {}
    for index_info in indices:
        code = index_info['code']
        name = index_info['name']
        
        price_df = fetcher.fetch_index_history(code)
        pe_df = fetcher.fetch_index_pe_history(code)
        
        if price_df.empty:
            logger.warning(f"No data for {code}")
            continue
        
        index_data[code] = {
            'name': name,
            'price_df': price_df,
            'pe_df': pe_df
        }
    
    # 生成调仓日期
    all_dates = sorted(set.intersection(*[set(df.index) for df in index_data.values() if not df['price_df'].empty]))
    all_dates = [d for d in all_dates if start_date <= str(d.date()) <= end_date]
    
    if rebalance_freq == 'weekly':
        rebalance_dates = [d for i, d in enumerate(all_dates) if d.weekday() == 4]  # 每周五
    else:
        rebalance_dates = [d for i, d in enumerate(all_dates) if d.day <= 5 and d.day >= 1]  # 每月第一个交易日
    
    # 回测循环
    cash = initial_capital
    positions = {}
    portfolio_values = []
    benchmark_values = []
    trades = []
    
    benchmark_start_price = benchmark_prices.loc[all_dates[0]] if benchmark_prices is not None else 1
    
    for i, date in enumerate(all_dates):
        date_str = str(date.date())
        
        # 获取当前价格
        current_prices = {
            code: data['price_df'].loc[date, 'close']
            for code, data in index_data.items()
            if date in data['price_df'].index
        }
        
        # 计算组合价值
        stock_value = sum(
            pos['shares'] * current_prices.get(code, pos['avg_price'])
            for code, pos in positions.items()
        )
        total_value = cash + stock_value
        
        portfolio_values.append({
            'date': date_str,
            'value': total_value,
            'nav': total_value / initial_capital
        })
        
        # 计算基准价值
        if benchmark_prices is not None and date in benchmark_prices.index:
            bench_price = benchmark_prices.loc[date]
            bench_nav = bench_price / benchmark_start_price
            benchmark_values.append({
                'date': date_str,
                'nav': bench_nav
            })
        
        # 检查是否调仓日
        if date not in rebalance_dates:
            continue
        
        # 运行策略
        logger.info(f"Rebalancing on {date_str}")
        
        # 计算因子和得分
        all_factors = {}
        for code, data in index_data.items():
            if date not in data['price_df'].index:
                continue
            
            # 截取到当前日期的数据
            price_hist = data['price_df'].loc[:date]
            pe_hist = data['pe_df'].loc[:date] if not data['pe_df'].empty else pd.DataFrame()
            
            factors = factor_engine.calc_all_factors(price_hist, pe_hist, benchmark_prices.loc[:date])
            all_factors[code] = factors
        
        # 计算得分
        scores = {}
        for code, factors in all_factors.items():
            score, _ = scorer.calc_score(factors)
            scores[code] = score
        
        # 排序选股
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_n = config['strategy'].get('top_n', 5)
        buffer_n = config['strategy'].get('buffer_n', 8)
        
        top_picks = [x[0] for x in ranked[:top_n]]
        hold_range = [x[0] for x in ranked[:buffer_n]]
        
        # 生成交易信号
        current_holdings = list(positions.keys())
        
        to_sell = [code for code in current_holdings if code not in hold_range]
        to_buy = [code for code in top_picks if code not in current_holdings]
        
        # 执行卖出
        for code in to_sell:
            if code in positions:
                pos = positions[code]
                price = current_prices.get(code, pos['avg_price'])
                
                # 应用滑点
                exec_price = price * (1 - 0.001)
                
                amount = pos['shares'] * exec_price
                commission = amount * 0.0003
                
                cash += amount - commission
                
                trades.append({
                    'date': date_str,
                    'type': 'sell',
                    'code': code,
                    'shares': pos['shares'],
                    'price': exec_price
                })
                
                del positions[code]
                logger.info(f"  Sold {code}")
        
        # 执行买入
        if to_buy:
            available = cash * 0.95  # 留 5% 现金
            amount_per_stock = available / len(to_buy)
            
            for code in to_buy:
                price = current_prices.get(code)
                if price is None:
                    continue
                
                exec_price = price * (1 + 0.001)  # 滑点
                shares = int(amount_per_stock / exec_price)
                
                if shares > 0:
                    cost = shares * exec_price * (1 + 0.0003)
                    
                    if cost <= cash:
                        cash -= cost
                        positions[code] = {
                            'shares': shares,
                            'avg_price': exec_price
                        }
                        
                        trades.append({
                            'date': date_str,
                            'type': 'buy',
                            'code': code,
                            'shares': shares,
                            'price': exec_price
                        })
                        
                        logger.info(f"  Bought {code}")
    
    # 计算回测统计
    portfolio_df = pd.DataFrame(portfolio_values)
    benchmark_df_result = pd.DataFrame(benchmark_values)
    
    # 合并
    result_df = pd.merge(portfolio_df, benchmark_df_result, on='date', how='inner')
    result_df['portfolio_return'] = result_df['nav'] - 1
    result_df['benchmark_return'] = result_df['nav_y'] - 1 if 'nav_y' in result_df.columns else 0
    
    # 计算统计指标
    total_return = result_df['nav'].iloc[-1] - 1
    bench_return = result_df['nav_y'].iloc[-1] - 1 if 'nav_y' in result_df.columns else 0
    
    # 年化收益
    num_years = len(result_df) / 252
    annual_return = (1 + total_return) ** (1 / num_years) - 1 if num_years > 0 else 0
    
    # 波动率
    daily_returns = result_df['portfolio_return'].diff().dropna()
    volatility = daily_returns.std() * np.sqrt(252)
    
    # 夏普比率
    sharpe = annual_return / volatility if volatility > 0 else 0
    
    # 最大回撤
    rolling_max = result_df['nav'].cummax()
    drawdown = (result_df['nav'] - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    
    # 输出结果
    print("\n" + "=" * 60)
    print("回测结果")
    print("=" * 60)
    print(f"回测期间：{start_date} 至 {end_date}")
    print(f"初始资金：¥{initial_capital:,.0f}")
    print(f"最终资产：¥{result_df['value'].iloc[-1]:,.0f}")
    print(f"\n收益率:")
    print(f"  总收益：{total_return*100:.2f}%")
    print(f"  年化：{annual_return*100:.2f}%")
    print(f"  基准：{bench_return*100:.2f}%")
    print(f"\n风险指标:")
    print(f"  波动率：{volatility*100:.2f}%")
    print(f"  夏普比率：{sharpe:.2f}")
    print(f"  最大回撤：{max_drawdown*100:.2f}%")
    print(f"\n交易次数：{len(trades)}")
    print("=" * 60)
    
    # 保存结果
    output_dir = project_root / 'backtest_results'
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_df.to_csv(output_dir / f'backtest_{timestamp}.csv', index=False)
    
    with open(output_dir / f'summary_{timestamp}.txt', 'w', encoding='utf-8') as f:
        f.write(f"回测期间：{start_date} 至 {end_date}\n")
        f.write(f"初始资金：¥{initial_capital:,.0f}\n")
        f.write(f"最终资产：¥{result_df['value'].iloc[-1]:,.0f}\n")
        f.write(f"总收益：{total_return*100:.2f}%\n")
        f.write(f"年化收益：{annual_return*100:.2f}%\n")
        f.write(f"夏普比率：{sharpe:.2f}\n")
        f.write(f"最大回撤：{max_drawdown*100:.2f}%\n")
    
    logger.info(f"Results saved to {output_dir}")
    
    return {
        'result_df': result_df,
        'total_return': total_return,
        'annual_return': annual_return,
        'sharpe': sharpe,
        'max_drawdown': max_drawdown,
        'trades': trades
    }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_backtest(start_date="2018-01-01")
