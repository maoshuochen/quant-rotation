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
from src.market_regime import DynamicWeightScoringEngine
from src.portfolio import SimulatedPortfolio
from src.config_loader import load_app_config

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """加载配置"""
    return load_app_config(Path(__file__).parent.parent)


class RotationStrategy:
    """指数轮动策略"""
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_config()
        
        # 初始化组件
        self.fetcher = IndexDataFetcher()
        
        # 动态权重评分引擎
        self.scorer = DynamicWeightScoringEngine(self.config)
        
        # 策略参数
        self.strategy = self.config.get('strategy', {})
        self.top_n = self.strategy.get('top_n', 5)
        self.buffer_n = self.strategy.get('buffer_n', 8)
        
        # 指数列表
        self.indices = self.config.get('indices', [])
        self.inactive_indices = self.config.get('inactive_indices', [])
        
        # 模拟账户
        portfolio_config = self.config.get('portfolio', {})
        stop_loss_config = self.config.get('stop_loss', {})
        # 冷却期配置（从 stop_loss 配置中读取，默认 5 天）
        cooldown_days = stop_loss_config.get('cooldown_days', 5) if stop_loss_config else 5
        self.portfolio = SimulatedPortfolio(
            initial_capital=portfolio_config.get('initial_capital', 1000000),
            commission_rate=portfolio_config.get('commission', 0.0003),
            slippage=portfolio_config.get('slippage', 0.001),
            stop_loss_config=stop_loss_config if stop_loss_config else None,
            cooldown_days=cooldown_days
        )
        
        # 基准 (沪深 300 ETF)
        self.benchmark_code = "510300"
        self.benchmark_data = None
        self.factor_model = self.config.get('factor_model', {})
        self.data_health = {}
    
    def load_benchmark(self):
        """加载基准数据并更新市场状态"""
        logger.info(f"Loading benchmark: {self.benchmark_code}")
        self.benchmark_data = self.fetcher.fetch_etf_history(self.benchmark_code, "20230101")
        
        # 更新市场状态和动态权重
        if not self.benchmark_data.empty and 'close' in self.benchmark_data.columns:
            self.scorer.update_market_regime(self.benchmark_data['close'])
            logger.info(f"市场状态：{self.scorer.current_regime}")
            logger.info(f"动态权重：{self.scorer.current_weights}")
    
    def fetch_all_data(self) -> Dict[str, pd.DataFrame]:
        """获取所有 ETF 数据"""
        data_dict = {}
        
        # 获取至少 252 天数据（1 年）用于估值因子计算
        start_date = "20230101"
        
        for idx in self.indices:
            code = idx.get('code', '')
            etf = idx.get('etf', '')
            
            if etf:
                logger.info(f"Fetching ETF data: {etf} (since {start_date})")
                df = self.fetcher.fetch_etf_history(etf, start_date)
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
        etf_shares_health = {'ok': [], 'snapshot': [], 'missing': []}
        
        # 获取北向资金数据 (一次获取，复用)
        logger.info("Fetching northbound flow data...")
        nb_df = self.fetcher.fetch_northbound_flow("20240101")
        nb_snapshot_df = self.fetcher.fetch_northbound_snapshot()
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
                        if len(shares_df) >= 5:
                            etf_shares_health['ok'].append(code)
                        else:
                            etf_shares_health['snapshot'].append(code)
                    else:
                        etf_shares_health['missing'].append(code)
                except Exception as e:
                    logger.warning(f"Failed to fetch ETF shares for {etf_code}: {e}")
                    etf_shares_health['missing'].append(code)
            
            # 计算评分 (含北向资金 + ETF 份额 + 动态权重)
            scores = self.scorer.score_index(
                df, 
                self.benchmark_data,
                northbound_metrics=nb_metrics,
                etf_shares_metrics=etf_metrics,
                dynamic_weights=self.scorer.current_weights
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
        self.data_health = self._build_data_health(data_dict, nb_df, nb_snapshot_df, etf_shares_health)
        
        return ranking

    def _build_data_health(self, data_dict: Dict[str, pd.DataFrame], nb_df: pd.DataFrame, nb_snapshot_df: pd.DataFrame, etf_shares_health: Dict[str, List[str]]) -> Dict:
        latest_dates = []
        stale_codes = []
        for code, df in data_dict.items():
            if df.empty:
                stale_codes.append(code)
                continue
            latest = df.index.max()
            latest_dates.append(latest)
            if (pd.Timestamp(datetime.now().date()) - latest).days > 10:
                stale_codes.append(code)

        northbound_rows = len(nb_df) if nb_df is not None else 0
        northbound_latest = nb_df.index.max() if northbound_rows else None
        northbound_gap_days = (pd.Timestamp(datetime.now().date()) - northbound_latest).days if northbound_latest is not None else None
        northbound_snapshot_date = nb_snapshot_df.index.max() if nb_snapshot_df is not None and not nb_snapshot_df.empty else None
        recent_northbound_rows = 0
        if nb_df is not None and not nb_df.empty and northbound_latest is not None:
            recent_cutoff = northbound_latest - pd.Timedelta(days=30)
            recent_northbound_rows = len(nb_df[nb_df.index >= recent_cutoff])

        if recent_northbound_rows >= 20 and northbound_gap_days is not None and northbound_gap_days <= 30:
            northbound_status = 'ok'
        elif northbound_rows >= 20 or northbound_snapshot_date is not None:
            northbound_status = 'degraded'
        else:
            northbound_status = 'missing'

        if etf_shares_health['missing']:
            shares_status = 'degraded'
        elif etf_shares_health['snapshot']:
            shares_status = 'snapshot'
        else:
            shares_status = 'ok'

        return {
            'price_data': {
                'status': 'ok' if not stale_codes else 'degraded',
                'available_count': len(data_dict),
                'expected_count': len(self.indices),
                'stale_codes': stale_codes,
                'latest_trade_date': max(latest_dates).strftime('%Y-%m-%d') if latest_dates else ''
            },
            'northbound': {
                'status': northbound_status,
                'rows': northbound_rows,
                'recent_rows': recent_northbound_rows,
                'latest_valid_date': northbound_latest.strftime('%Y-%m-%d') if northbound_latest is not None else '',
                'gap_days': northbound_gap_days,
                'snapshot_date': northbound_snapshot_date.strftime('%Y-%m-%d') if northbound_snapshot_date is not None else '',
            },
            'etf_shares': {
                'status': shares_status,
                'history_count': len(etf_shares_health['ok']),
                'snapshot_count': len(etf_shares_health['snapshot']),
                'missing_count': len(etf_shares_health['missing']),
                'missing_codes': etf_shares_health['missing'],
            },
            'universe': {
                'active_count': len(self.indices),
                'inactive_count': len(self.inactive_indices),
                'inactive_codes': [idx.get('code') for idx in self.inactive_indices],
            },
        }

    def build_recommendation(self, ranking: pd.DataFrame, signals: List[Dict]) -> Dict:
        if ranking.empty:
            return {}

        selected = ranking.head(self.top_n)
        hold_range = ranking.head(self.buffer_n)
        holdings = []
        for _, row in selected.iterrows():
            strongest = []
            weakest = []
            factor_scores = {
                factor: row.get(factor, 0.5)
                for factor in self.scorer.active_factors + self.scorer.auxiliary_factors
                if factor in row
            }
            ordered = sorted(factor_scores.items(), key=lambda item: item[1], reverse=True)
            strongest = [factor for factor, _ in ordered[:2]]
            weakest = [factor for factor, _ in ordered[-1:]]
            holdings.append({
                'code': row['code'],
                'rank': int(row['rank']),
                'score': round(float(row['total_score']), 4),
                'name': next((idx.get('name') for idx in self.indices if idx.get('code') == row['code']), row['code']),
                'etf': next((idx.get('etf') for idx in self.indices if idx.get('code') == row['code']), ''),
                'strongest_factors': strongest,
                'weakest_factors': weakest,
            })

        return {
            'top_n': self.top_n,
            'buffer_n': self.buffer_n,
            'rebalance_frequency': self.strategy.get('rebalance_frequency', 'weekly'),
            'selected_codes': selected['code'].tolist(),
            'hold_range_codes': hold_range['code'].tolist(),
            'signals': signals,
            'holdings': holdings,
        }
    
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

        # 检查止损（在生成新信号之前）
        date_str = date if isinstance(date, str) else date.strftime('%Y-%m-%d')
        stop_loss_signals = self.portfolio.check_stop_loss(prices, date_str)

        # 执行止损（优先于正常信号）
        if any(stop_loss_signals.values()):
            logger.warning(f"执行止损：{stop_loss_signals}")
            names = {idx['code']: idx['name'] for idx in self.indices}
            self.portfolio.execute_stop_loss(stop_loss_signals, prices, names, date_str)

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
            'portfolio': snapshot,
            'health': self.data_health,
            'recommendation': self.build_recommendation(ranking, signals),
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
