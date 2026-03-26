#!/usr/bin/env python3
"""
预加载所有指数数据 - 缓存到本地
"""
import sys
import yaml
import logging
from pathlib import Path
from datetime import datetime
import time

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data_fetcher import IndexDataFetcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """加载配置"""
    config_path = project_root / 'config' / 'config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main():
    logger.info("=" * 60)
    logger.info("开始预加载所有指数数据")
    logger.info("=" * 60)
    
    config = load_config()
    indices = config.get('indices', [])
    
    fetcher = IndexDataFetcher()
    
    results = {
        'success': [],
        'failed': []
    }
    
    for index_info in indices:
        code = index_info['code']
        name = index_info['name']
        
        logger.info(f"\n处理：{name} ({code})")
        
        # 获取行情数据
        try:
            price_df = fetcher.fetch_index_history(code, start_date="20180101")
            if not price_df.empty:
                logger.info(f"  ✅ 行情：{len(price_df)} 行")
                results['success'].append(code)
            else:
                logger.warning(f"  ⚠️ 行情：无数据")
                results['failed'].append(code)
        except Exception as e:
            logger.error(f"  ❌ 行情失败：{e}")
            results['failed'].append(code)
        
        # 获取估值数据
        try:
            pe_df = fetcher.fetch_index_pe_history(code)
            if not pe_df.empty:
                logger.info(f"  ✅ 估值：{len(pe_df)} 行")
            else:
                logger.warning(f"  ⚠️ 估值：无数据")
        except Exception as e:
            logger.error(f"  ❌ 估值失败：{e}")
        
        # 避免请求过快
        time.sleep(1)
    
    # 输出结果
    logger.info("\n" + "=" * 60)
    logger.info("数据加载完成")
    logger.info("=" * 60)
    logger.info(f"成功：{len(results['success'])} 个")
    logger.info(f"失败：{len(results['failed'])} 个")
    
    if results['failed']:
        logger.info(f"\n失败的指数：{results['failed']}")
    
    # 列出缓存文件
    cache_dir = project_root / 'data' / 'raw'
    if cache_dir.exists():
        cache_files = list(cache_dir.glob('*.parquet'))
        logger.info(f"\n缓存文件：{len(cache_files)} 个")
        for f in cache_files[:10]:
            logger.info(f"  - {f.name}")
        if len(cache_files) > 10:
            logger.info(f"  ... 还有 {len(cache_files) - 10} 个")
    
    return len(results['success']) > 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
