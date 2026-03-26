#!/usr/bin/env python3
"""
测试脚本 - 使用模拟数据验证流程
"""
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.factor_engine import FactorEngine
from src.scoring import ScoringEngine
from src.strategy import IndexRotationStrategy
from src.portfolio import SimulatedPortfolio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_mock_data(code: str, name: str, start_date: str = "2018-01-01", 
                       days: int = 2000) -> dict:
    """生成模拟数据"""
    dates = pd.date_range(start=start_date, periods=days, freq='B')  # 工作日
    
    # 随机游走价格
    np.random.seed(hash(code) % 2**32)
    returns = np.random.normal(0.0005, 0.02, days)  # 日均收益 0.05%，波动 2%
    price_series = 1000 * np.cumprod(1 + returns)
    
    price_df = pd.DataFrame({
        'close': price_series,
        'open': price_series * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': price_series * (1 + np.random.uniform(0, 0.02, days)),
        'low': price_series * (1 - np.random.uniform(0, 0.02, days)),
        'volume': np.random.uniform(1e8, 1e9, days)
    }, index=dates)
    
    # PE 数据 (均值回归)
    pe_base = np.random.uniform(15, 30)
    pe_series = pe_base + np.random.normal(0, 3, days)
    pe_series = np.clip(pe_series, 5, 80)
    
    pe_df = pd.DataFrame({
        'pe': pe_series,
        'pb': pe_series * 0.3,
        'ps': pe_series * 0.1,
        'dividend_yield': np.random.uniform(1, 4, days)
    }, index=dates)
    
    return {
        'code': code,
        'name': name,
        'price_df': price_df,
        'pe_df': pe_df
    }


def main():
    logger.info("=" * 50)
    logger.info("使用模拟数据测试策略流程")
    logger.info("=" * 50)
    
    # 生成模拟指数数据
    indices = [
        ("000300.SH", "沪深 300"),
        ("000905.SH", "中证 500"),
        ("000852.SH", "中证 1000"),
        ("399006.SZ", "创业板指"),
        ("000688.SH", "科创 50"),
    ]
    
    mock_data = {}
    for code, name in indices:
        mock_data[code] = generate_mock_data(code, name)
        logger.info(f"Generated mock data for {name}: {len(mock_data[code]['price_df'])} days")
    
    # 初始化组件
    factor_engine = FactorEngine()
    scorer = ScoringEngine()
    
    # 计算因子和得分
    logger.info("\n计算因子得分...")
    all_scores = {}
    all_factors = {}
    
    benchmark_prices = mock_data["000300.SH"]['price_df']['close']
    
    for code, data in mock_data.items():
        factors = factor_engine.calc_all_factors(
            data['price_df'],
            data['pe_df'],
            benchmark_prices
        )
        all_factors[code] = factors
        
        score, breakdown = scorer.calc_score(factors)
        all_scores[code] = score
        
        logger.info(f"{data['name']}: {score:.3f} (估值:{breakdown['value']:.2f}, 动量:{breakdown['momentum']:.2f})")
    
    # 排序
    ranked = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
    
    logger.info("\n" + "=" * 50)
    logger.info("策略结果")
    logger.info("=" * 50)
    
    for i, (code, score) in enumerate(ranked, 1):
        name = mock_data[code]['name']
        logger.info(f"{i}. {name} ({code}): {score:.3f}")
    
    # 模拟调仓
    top_n = 3
    top_picks = [x[0] for x in ranked[:top_n]]
    
    logger.info(f"\n选股：前{top_n}名")
    logger.info(f"买入：{top_picks}")
    
    # 模拟组合
    portfolio = SimulatedPortfolio(initial_capital=1_000_000)
    
    # 获取当前价格
    current_prices = {code: data['price_df']['close'].iloc[-1] for code, data in mock_data.items()}
    names = {code: data['name'] for code, data in mock_data.items()}
    
    # 执行买入
    signals = {'buy': top_picks, 'sell': [], 'hold': []}
    today = datetime.now().strftime('%Y-%m-%d')
    
    trades = portfolio.execute_signal(signals, current_prices, names, today)
    
    logger.info(f"\n执行交易：{len(trades)} 笔")
    for trade in trades:
        logger.info(f"  {trade.type.upper()} {trade.name}: {trade.shares}股 @ ¥{trade.price:.2f}")
    
    # 组合摘要
    summary = portfolio.get_summary(current_prices)
    
    logger.info("\n" + "=" * 50)
    logger.info("组合摘要")
    logger.info("=" * 50)
    logger.info(f"总资产：¥{summary['total_value']:,.0f}")
    logger.info(f"现金：¥{summary['cash']:,.0f}")
    logger.info(f"持仓数：{summary['num_positions']}")
    
    for pos in summary['positions']:
        logger.info(f"  {pos['name']}: {pos['weight']*100:.1f}%")
    
    logger.info("\n" + "=" * 50)
    logger.info("测试完成！流程正常 ✅")
    logger.info("=" * 50)
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
