#!/usr/bin/env python3
"""
每日运行脚本 - 指数轮动策略
"""
import sys
import yaml
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data_fetcher import IndexDataFetcher
from src.strategy import IndexRotationStrategy
from src.portfolio import SimulatedPortfolio
from src.notifier import get_notifier_from_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / 'logs' / 'strategy.log')
    ]
)

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """加载配置文件"""
    config_path = project_root / 'config' / 'config.yaml'
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 处理环境变量
    if 'telegram' in config:
        token = config['telegram'].get('bot_token', '')
        if token.startswith('${') and token.endswith('}'):
            import os
            env_var = token[2:-1]
            config['telegram']['bot_token'] = os.environ.get(env_var, '')
    
    return config


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("Starting daily strategy run")
    logger.info("=" * 50)
    
    # 加载配置
    config = load_config()
    logger.info("Configuration loaded")
    
    # 初始化组件
    strategy = IndexRotationStrategy(config)
    
    portfolio_config = config.get('portfolio', {})
    portfolio = SimulatedPortfolio(
        initial_capital=portfolio_config.get('initial_capital', 1_000_000),
        commission_rate=portfolio_config.get('commission', 0.0003),
        slippage=portfolio_config.get('slippage', 0.001)
    )
    
    notifier = get_notifier_from_config(config)
    
    # 获取当前日期
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 运行策略
    logger.info("Running strategy...")
    result = strategy.run(today)
    
    # 生成信号 (假设首次运行，空仓)
    current_holdings = []
    signals = strategy.generate_signals(result, current_holdings)
    
    # 获取当前价格
    current_prices = {
        code: data['current_price']
        for code, data in result['all_data'].items()
    }
    
    names = {
        code: data['name']
        for code, data in result['all_data'].items()
    }
    
    # 执行信号
    logger.info("Executing signals...")
    trades = portfolio.execute_signal(signals, current_prices, names, today)
    
    # 记录净值
    portfolio.record_daily_value(today, current_prices)
    
    # 获取组合摘要
    summary = portfolio.get_summary(current_prices)
    
    # 发送通知
    if notifier:
        logger.info("Sending notifications...")
        notifier.send_signal(result, signals)
        notifier.send_portfolio_summary(summary, today)
    
    # 输出结果
    print("\n" + "=" * 50)
    print(f"策略运行完成 - {today}")
    print("=" * 50)
    print(f"\n🏆 TOP 5 指数:")
    for i, (code, score) in enumerate(result['ranked'][:5], 1):
        name = result['all_data'].get(code, {}).get('name', code)
        print(f"  {i}. {name} ({code}): {score:.3f}")
    
    print(f"\n💡 调仓信号:")
    print(f"  买入：{signals['buy']}")
    print(f"  卖出：{signals['sell']}")
    print(f"  持有：{signals['hold']}")
    
    print(f"\n💼 组合摘要:")
    print(f"  总资产：¥{summary['total_value']:,.0f}")
    print(f"  收益率：{summary['return']*100:.2f}%")
    print(f"  持仓数：{summary['num_positions']}")
    
    print("\n" + "=" * 50)
    
    logger.info("Daily run completed")
    
    return {
        'result': result,
        'signals': signals,
        'summary': summary
    }


if __name__ == '__main__':
    main()
