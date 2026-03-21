"""
策略主逻辑 - 适配 Baostock
"""
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, List, Optional
import yaml

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_fetcher_baostock import IndexDataFetcher
from src.scoring_baostock import ScoringEngine
from src.portfolio import SimulatedPortfolio

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """加载配置"""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


class RotationStrategy:
    """指数轮动策略"""
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_config()
        
        # 初始化组件
        self.fetcher = IndexDataFetcher()
        self.scorer = ScoringEngine(self.config)
        
        # 策略参数
        self.strategy = self.config.get('strategy', {})
        self.top_n = self.strategy.get('top_n', 5)
        self.buffer_n = self.strategy.get('buffer_n', 8)
        
        # 指数列表
        self.indices = self.config.get('indices', [])
        
        # 模拟账户
        portfolio_config = self.config.get('portfolio', {})
        self.portfolio = SimulatedPortfolio(
            initial_capital=portfolio_config.get('initial_capital', 1000000),
            commission_rate=portfolio_config.get('commission', 0.0003),
            slippage=portfolio_config.get('slippage', 0.001)
        )
        
        # 基准 (沪深 300 ETF)
        self.benchmark_code = "510300"
        self.benchmark_data = None
    
    def load_benchmark(self):
        """加载基准数据"""
        logger.info(f"Loading benchmark: {self.benchmark_code}")
        self.benchmark_data = self.fetcher.fetch_etf_history(self.benchmark_code, "20250101")
    
    def fetch_all_data(self) -> Dict[str, pd.DataFrame]:
        """获取所有 ETF 数据"""
        data_dict = {}
        
        for idx in self.indices:
            code = idx.get('code', '')
            etf = idx.get('etf', '')
            
            if etf:
                logger.info(f"Fetching ETF data: {etf}")
                df = self.fetcher.fetch_etf_history(etf, "20250101")
                if not df.empty:
                    data_dict[code] = df
                    logger.info(f"  -> {len(df)} rows")
                else:
                    logger.warning(f"  -> No data for {etf}")
        
        return data_dict
    
    def run_scoring(self, data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """运行评分系统 (含扩展资金流因子)"""
        scores_dict = {}
        flow_details = {}
        
        # 获取北向资金数据 (一次获取，复用)
        logger.info("Fetching northbound flow data...")
        nb_df = self.fetcher.fetch_northbound_flow("20260101")
        nb_metrics = self.fetcher.calc_northbound_metrics(nb_df) if not nb_df.empty else None
        
        for code, df in data_dict.items():
            logger.info(f"Scoring {code}...")
            
            # 获取 ETF 代码
            etf_code = None
            for idx in self.indices:
                if idx.get('code') == code:
                    etf_code = idx.get('etf', '')
                    break
            
            # 获取 ETF 份额数据
            etf_metrics = None
            if etf_code:
                try:
                    shares_df = self.fetcher.fetch_etf_shares(etf_code, "20260101")
                    if not shares_df.empty:
                        etf_metrics = self.fetcher.calc_etf_shares_metrics(shares_df)
                except Exception as e:
                    logger.warning(f"Failed to fetch ETF shares for {etf_code}: {e}")
            
            # 计算评分 (含北向资金 + ETF 份额)
            scores = self.scorer.score_index(
                df, 
                self.benchmark_data,
                northbound_metrics=nb_metrics,
                etf_shares_metrics=etf_metrics
            )
            scores_dict[code] = scores
            
            # 保存资金流详情
            flow_detail = {}
            if scores.get('flow') is not None:
                # 近似子因子得分
                flow_score = scores.get('flow', 0.5)
                flow_detail['volume_trend'] = round(flow_score * (0.8 + 0.4 * (flow_score - 0.5)), 4)
                flow_detail['price_volume_corr'] = round(flow_score * (0.9 + 0.2 * (flow_score - 0.5)), 4)
                flow_detail['amount_trend'] = round(flow_score * (0.85 + 0.3 * (flow_score - 0.5)), 4)
                flow_detail['flow_intensity'] = round(flow_score * (0.9 + 0.2 * (flow_score - 0.5)), 4)
                
                if nb_metrics:
                    flow_detail['northbound'] = round(0.5 + nb_metrics.get('net_flow_20d_sum', 0) / 200, 4)
                    flow_detail['northbound_metrics'] = nb_metrics
                else:
                    flow_detail['northbound'] = 0.5
                    flow_detail['northbound_metrics'] = {}
                
                if etf_metrics:
                    flow_detail['etf_shares'] = round(0.5 + etf_metrics.get('shares_change_20d', 0) / 0.4, 4)
                    flow_detail['etf_shares_metrics'] = etf_metrics
                else:
                    flow_detail['etf_shares'] = 0.5
                    flow_detail['etf_shares_metrics'] = {}
            
            flow_details[code] = flow_detail
        
        # 排名
        ranking = self.scorer.rank_indices(scores_dict)
        
        # 保存 flow_details 到 scorer 对象 (供外部访问)
        self.flow_details = flow_details
        
        return ranking
    
    def generate_signals(self, ranking: pd.DataFrame) -> List[Dict]:
        """
        生成交易信号
        
        Returns:
            信号列表 [{action: 'buy'/'sell', code: str, weight: float}]
        """
        signals = []
        
        if ranking.empty:
            return signals
        
        # 当前持仓
        current_codes = set(self.portfolio.positions.keys())
        
        # 选前 top_n
        selected = ranking.head(self.top_n)['code'].tolist()
        
        # 缓冲：跌出前 buffer_n 才卖出
        hold_range = ranking.head(self.buffer_n)['code'].tolist()
        
        logger.info(f"Selected (top {self.top_n}): {selected}")
        logger.info(f"Hold range (top {self.buffer_n}): {hold_range}")
        
        # 卖出信号
        for code in current_codes:
            if code not in hold_range:
                signals.append({
                    'action': 'sell',
                    'code': code,
                    'weight': 0.0
                })
                logger.info(f"Sell signal: {code} (dropped out of top {self.buffer_n})")
        
        # 买入信号
        for code in selected:
            if code not in current_codes:
                signals.append({
                    'action': 'buy',
                    'code': code,
                    'weight': 1.0 / len(selected)  # 等权重
                })
                logger.info(f"Buy signal: {code}")
        
        return signals
    
    def execute_signals(self, signals: List[Dict], prices: Dict[str, float], date: str):
        """执行交易信号"""
        # 构建信号字典
        buy_list = []
        sell_list = []
        names = {}
        
        for signal in signals:
            code = signal['code']
            action = signal['action']
            
            # 获取名称
            for idx in self.indices:
                if idx.get('code') == code:
                    names[code] = idx.get('name', code)
                    break
            
            if action == 'buy':
                buy_list.append(code)
            elif action == 'sell':
                sell_list.append(code)
        
        signals_dict = {'buy': buy_list, 'sell': sell_list}
        
        # 执行
        if buy_list or sell_list:
            trades = self.portfolio.execute_signal(signals_dict, prices, names, date)
            for trade in trades:
                logger.info(f"{trade.type.upper()} {trade.code}: {trade.shares} @ {trade.price:.3f}")
    
    def run(self, date: Optional[str] = None) -> Dict:
        """
        运行策略
        
        Returns:
            运行结果
        """
        date = date or datetime.now().strftime('%Y-%m-%d')
        logger.info(f"Running strategy for {date}")
        
        # 加载基准
        self.load_benchmark()
        
        # 获取数据
        data_dict = self.fetch_all_data()
        
        if not data_dict:
            logger.error("No data fetched!")
            return {'error': 'No data'}
        
        # 评分排名
        ranking = self.run_scoring(data_dict)
        print("\n=== 指数排名 ===")
        print(ranking[['code', 'total_score', 'rank']].to_string(index=False))
        
        # 生成信号
        signals = self.generate_signals(ranking)
        
        # 获取当前价格
        prices = {}
        for code, df in data_dict.items():
            prices[code] = df['close'].iloc[-1]
        
        # 执行交易
        if signals:
            self.execute_signals(signals, prices, date)
        
        # 组合快照
        snapshot = self.portfolio.get_summary(prices)
        
        # 结果
        result = {
            'date': date,
            'ranking': ranking,
            'signals': signals,
            'portfolio': snapshot
        }
        
        logger.info(f"Strategy completed. Portfolio value: {snapshot['total_value']:.2f}")
        
        return result
    
    def close(self):
        """关闭资源"""
        self.fetcher.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s'
    )
    
    strategy = RotationStrategy()
    
    try:
        result = strategy.run()
        
        print("\n=== 组合快照 ===")
        print(f"现金：{result['portfolio']['cash']:.2f}")
        print(f"持仓：{result['portfolio']['positions']}")
        print(f"总值：{result['portfolio']['total_value']:.2f}")
        
    finally:
        strategy.close()
