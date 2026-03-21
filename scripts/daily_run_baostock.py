#!/usr/bin/env python3
"""
每日运行脚本 - Baostock 版本
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import logging
from datetime import datetime
from src.strategy_baostock import RotationStrategy

def setup_logging():
    """配置日志"""
    log_dir = root_dir / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f'strategy_{datetime.now().strftime("%Y%m%d")}.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 50)
    logger.info("指数轮动策略 - 每日运行")
    logger.info("=" * 50)
    
    strategy = RotationStrategy()
    
    try:
        result = strategy.run()
        
        if 'error' in result:
            logger.error(f"策略运行失败：{result['error']}")
            return 1
        
        # 输出结果
        print("\n" + "=" * 50)
        print("策略运行完成")
        print("=" * 50)
        
        ranking = result.get('ranking')
        if ranking is not None and not ranking.empty:
            print("\n📊 指数排名:")
            for _, row in ranking.iterrows():
                print(f"  {int(row['rank'])}. {row['code']}: {row['total_score']:.4f}")
        
        portfolio = result.get('portfolio', {})
        print(f"\n💰 组合总值：{portfolio.get('total_value', 0):,.2f}")
        print(f"💵 现金：{portfolio.get('cash', 0):,.2f}")
        print(f"📈 持仓数：{portfolio.get('num_positions', 0)}")
        
        # 持仓详情
        positions = portfolio.get('positions', [])
        if positions:
            print("\n📋 持仓详情:")
            for pos in positions:
                weight = pos.get('weight', 0) * 100
                print(f"  {pos['code']} ({pos['name']}): {weight:.1f}%")
        
        # 交易信号
        signals = result.get('signals', [])
        if signals:
            print(f"\n🔔 交易信号：{len(signals)} 个")
            for sig in signals:
                action = "买入" if sig['action'] == 'buy' else "卖出"
                print(f"  {action} {sig['code']}")
        
        print("\n" + "=" * 50)
        
        return 0
        
    except Exception as e:
        logger.exception(f"策略运行异常：{e}")
        return 1
    
    finally:
        strategy.close()

if __name__ == "__main__":
    sys.exit(main())
