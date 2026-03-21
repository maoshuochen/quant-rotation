"""
指数轮动策略主逻辑
"""
from typing import Dict, List, Tuple
from datetime import datetime
import logging

from .data_fetcher import IndexDataFetcher
from .factor_engine import FactorEngine
from .scoring import ScoringEngine

logger = logging.getLogger(__name__)


class IndexRotationStrategy:
    """指数轮动策略"""
    
    def __init__(self, config: dict):
        self.config = config
        self.indices = config['indices']
        self.strategy_params = config.get('strategy', {})
        
        self.data_fetcher = IndexDataFetcher()
        self.factor_engine = FactorEngine()
        self.scorer = ScoringEngine(config.get('factor_weights'))
        
        # 缓存基准数据 (沪深 300)
        self.benchmark_prices = None
    
    def _load_benchmark(self):
        """加载基准指数 (沪深 300)"""
        if self.benchmark_prices is None:
            df = self.data_fetcher.fetch_index_history("000300.SH")
            if not df.empty:
                self.benchmark_prices = df['close']
    
    def run(self, date: str = None) -> dict:
        """
        运行策略
        
        Args:
            date: 日期 (默认今天)
            
        Returns:
            策略结果字典
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"Running strategy for {date}")
        
        # 加载基准
        self._load_benchmark()
        
        # 1. 获取所有指数数据并计算因子
        all_factors = {}
        all_data = {}
        
        for index_info in self.indices:
            code = index_info['code']
            name = index_info['name']
            
            logger.info(f"Processing {name} ({code})")
            
            # 获取数据
            price_df = self.data_fetcher.fetch_index_history(code)
            pe_df = self.data_fetcher.fetch_index_pe_history(code)
            
            if price_df.empty:
                logger.warning(f"No price data for {code}")
                continue
            
            # 计算因子
            factors = self.factor_engine.calc_all_factors(
                price_df, 
                pe_df, 
                self.benchmark_prices
            )
            
            all_factors[code] = factors
            all_data[code] = {
                'name': name,
                'price_df': price_df,
                'pe_df': pe_df,
                'current_price': price_df['close'].iloc[-1],
                'current_pe': pe_df['pe'].iloc[-1] if not pe_df.empty else None,
                'current_pb': pe_df['pb'].iloc[-1] if not pe_df.empty else None,
            }
        
        # 2. 计算得分
        scores = {}
        score_breakdowns = {}
        
        for code, factors in all_factors.items():
            total_score, breakdown = self.scorer.calc_score(factors)
            scores[code] = total_score
            score_breakdowns[code] = breakdown
        
        # 3. 排序
        ranked = self.scorer.rank_indices(scores)
        
        # 4. 选股
        top_n = self.strategy_params.get('top_n', 5)
        buffer_n = self.strategy_params.get('buffer_n', 8)
        
        top_picks = ranked[:top_n]
        hold_range = ranked[:buffer_n]  # 持有范围
        
        # 5. 生成信号
        result = {
            'date': date,
            'all_scores': scores,
            'score_breakdowns': score_breakdowns,
            'ranked': ranked,
            'top_picks': top_picks,
            'hold_range': hold_range,
            'all_data': all_data,
        }
        
        logger.info(f"Strategy complete. Top picks: {[x[0] for x in top_picks]}")
        
        return result
    
    def generate_signals(self, result: dict, current_holdings: List[str]) -> dict:
        """
        生成调仓信号
        
        Args:
            result: 策略运行结果
            current_holdings: 当前持仓列表
            
        Returns:
            买卖信号字典
        """
        top_codes = [x[0] for x in result['top_picks']]
        hold_codes = [x[0] for x in result['hold_range']]
        
        # 买入：新进入前 N
        to_buy = [code for code in top_codes if code not in current_holdings]
        
        # 卖出：跌出缓冲范围
        to_sell = [code for code in current_holdings if code not in hold_codes]
        
        # 持有：在缓冲范围内
        to_hold = [code for code in current_holdings if code in hold_codes]
        
        signals = {
            'buy': to_buy,
            'sell': to_sell,
            'hold': to_hold,
        }
        
        logger.info(f"Signals - Buy: {to_buy}, Sell: {to_sell}, Hold: {to_hold}")
        
        return signals
