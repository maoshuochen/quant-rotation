#!/usr/bin/env python3
"""
策略参数优化脚本 - 贝叶斯优化
"""
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import pandas as pd
import numpy as np
import yaml

from src.optimizer import (
    BayesianOptimizer,
    ParameterSpace,
    OptimizationResult,
    get_strategy_param_space,
    get_factor_weight_space,
    get_stop_loss_param_space
)
from src.data_fetcher_baostock import IndexDataFetcher
from src.scoring_baostock import ScoringEngine
from src.portfolio import SimulatedPortfolio

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)


class BacktestWrapper:
    """回测包装器 - 将回测逻辑封装为优化器可用的函数"""

    def __init__(
        self,
        config: Dict,
        start_date: str,
        end_date: str,
        fetcher: IndexDataFetcher,
        base_config_override: Optional[Dict] = None
    ):
        self.config = config
        self.start_date = start_date
        self.end_date = end_date
        self.fetcher = fetcher
        self.base_config_override = base_config_override or {}

        # 预加载数据 (避免每次回测都重新加载)
        self.etf_data = self._load_all_data()
        self.benchmark_data = self.etf_data.get('000300.SH', pd.DataFrame())

        logger.info(f"预加载数据完成：{len(self.etf_data)}个 ETF")

    def _load_all_data(self) -> Dict[str, pd.DataFrame]:
        """预加载所有 ETF 数据"""
        etf_data = {}
        indices = self.config.get('indices', [])

        # 从回测起始日前推 1 年获取数据
        start = "20240101" if self.start_date < "20250101" else self.start_date

        for idx in indices:
            etf = idx.get('etf')
            code = idx.get('code')
            if etf:
                df = self.fetcher.fetch_etf_history(etf, start, force_refresh=False)
                if not df.empty:
                    etf_data[code] = df

        return etf_data

    def _normalize_factor_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """归一化因子权重 (确保总和为 1)"""
        # 过滤掉零权重
        valid_weights = {k: v for k, v in weights.items() if v > 0}
        if not valid_weights:
            return self.config.get('factor_weights', {})

        total = sum(valid_weights.values())
        return {k: v / total for k, v in valid_weights.items()}

    def run_backtest(self, params: Dict) -> Dict:
        """
        运行单次回测

        Args:
            params: 参数字典

        Returns:
            回测结果字典 (包含 sharpe, total_return, max_drawdown 等)
        """
        # 构建临时配置
        temp_config = self.config.copy()

        # 更新策略参数
        if 'top_n' in params:
            temp_config.setdefault('strategy', {})['top_n'] = int(params['top_n'])
        if 'buffer_n' in params:
            temp_config.setdefault('strategy', {})['buffer_n'] = int(params['buffer_n'])
        if 'momentum_window' in params:
            temp_config.setdefault('strategy', {})['momentum_window'] = int(params['momentum_window'])
        if 'lookback_pe' in params:
            temp_config.setdefault('strategy', {})['lookback_pe'] = int(params['lookback_pe'])

        # 更新因子权重
        factor_weight_keys = [
            'value_weight', 'momentum_weight', 'trend_weight',
            'flow_weight', 'volatility_weight', 'fundamental_weight',
            'sentiment_weight'
        ]
        has_factor_weights = any(k in params for k in factor_weight_keys)
        if has_factor_weights:
            weights = {}
            for key in factor_weight_keys:
                if key in params:
                    # 去掉 _weight 后缀
                    factor_name = key.replace('_weight', '')
                    weights[factor_name] = params[key]

            # 归一化
            normalized_weights = self._normalize_factor_weights(weights)
            temp_config['factor_weights'] = normalized_weights
            logger.debug(f"因子权重：{normalized_weights}")

        # 更新止损参数
        stop_loss_keys = [
            'stop_loss_individual', 'stop_loss_trailing',
            'stop_loss_portfolio', 'cooldown_days'
        ]
        has_stop_loss = any(k in params for k in stop_loss_keys)
        if has_stop_loss:
            stop_loss = temp_config.get('stop_loss', {}).copy()
            for key in stop_loss_keys:
                if key in params:
                    stop_loss_name = key.replace('stop_loss_', '')
                    if key == 'cooldown_days':
                        stop_loss[stop_loss_name] = int(params[key])
                    else:
                        stop_loss[stop_loss_name] = params[key]
            temp_config['stop_loss'] = stop_loss
            logger.debug(f"止损参数：{stop_loss}")

        # 应用基础配置覆盖
        for key, value in self.base_config_override.items():
            temp_config[key] = value

        # 运行回测
        try:
            result = self._execute_backtest(temp_config)
            return result
        except Exception as e:
            logger.error(f"回测失败：{e}")
            return {
                'sharpe': -999,
                'total_return': -1.0,
                'max_drawdown': -1.0,
                'error': str(e)
            }

    def _execute_backtest(self, config: Dict) -> Dict:
        """执行回测逻辑"""
        scorer = ScoringEngine(config)

        strategy = config.get('strategy', {})
        top_n = strategy.get('top_n', 5)
        buffer_n = strategy.get('buffer_n', 8)
        rebalance_freq = strategy.get('rebalance_frequency', 'weekly')

        stop_loss_config = config.get('stop_loss', {})
        cooldown_days = stop_loss_config.get('cooldown_days', 5) if stop_loss_config else 5

        portfolio = SimulatedPortfolio(
            initial_capital=config.get('portfolio', {}).get('initial_capital', 1_000_000),
            commission_rate=config.get('portfolio', {}).get('commission', 0.0003),
            slippage=config.get('portfolio', {}).get('slippage', 0.001),
            stop_loss_config=stop_loss_config if stop_loss_config else None,
            cooldown_days=cooldown_days
        )

        # 生成交易日期
        first_df = list(self.etf_data.values())[0]
        all_dates = first_df.index.tolist()

        start_dt = pd.to_datetime(self.start_date)
        end_dt = pd.to_datetime(self.end_date)
        trade_dates = [d for d in all_dates if start_dt <= d <= end_dt]

        if not trade_dates:
            return {'sharpe': -999, 'total_return': -1.0}

        # 确定调仓日期
        rebalance_dates = []
        for i, date in enumerate(trade_dates):
            if rebalance_freq == 'weekly':
                if date.weekday() == 0:  # Monday
                    rebalance_dates.append(date)
            elif rebalance_freq == 'monthly':
                if date.day <= 5:
                    rebalance_dates.append(date)
            else:
                rebalance_dates.append(date)

        if not rebalance_dates:
            rebalance_dates = [trade_dates[0]]

        # 回测循环
        daily_values = []
        prices_cache = {}  # 价格缓存

        for idx, date in enumerate(trade_dates):
            date_str = date.strftime('%Y-%m-%d')

            # 获取当日价格 (使用缓存)
            if date not in prices_cache:
                prices_cache[date] = {}
            for code, df in self.etf_data.items():
                if date in df.index:
                    prices_cache[date][code] = df.loc[date, 'close']

            prices = prices_cache[date]

            # 检查止损
            if prices and portfolio.positions:
                stop_loss_signals = portfolio.check_stop_loss(prices, date_str)
                if any(stop_loss_signals.values()):
                    names = {idx['code']: idx['name'] for idx in config.get('indices', [])}
                    portfolio.execute_stop_loss(stop_loss_signals, prices, names, date_str)

            # 记录每日净值
            if prices:
                portfolio.record_daily_value(date_str, prices)
                value = portfolio.get_portfolio_value(prices)
                daily_values.append({'date': date_str, 'value': value})

            # 调仓日运行策略
            if date in rebalance_dates and len(trade_dates) - trade_dates.index(date) > 5:
                scores_dict = {}
                for code, df in self.etf_data.items():
                    hist_df = df[df.index <= date]
                    if len(hist_df) >= 20:
                        scores = scorer.score_index(hist_df, self.benchmark_data)
                        scores_dict[code] = scores

                ranking = scorer.rank_indices(scores_dict)

                if ranking.empty:
                    continue

                selected = ranking.head(top_n)['code'].tolist()
                hold_range = ranking.head(buffer_n)['code'].tolist()

                current_codes = set(portfolio.positions.keys())
                signals = {'buy': [], 'sell': []}

                for code in current_codes:
                    if code not in hold_range:
                        signals['sell'].append(code)

                for code in selected:
                    if code not in current_codes:
                        signals['buy'].append(code)

                if signals['buy'] or signals['sell']:
                    names = {idx['code']: idx['name'] for idx in config.get('indices', [])}
                    portfolio.execute_signal(signals, prices, names, date_str)

        # 计算指标
        if not daily_values:
            return {'sharpe': -999, 'total_return': -1.0}

        values_df = pd.DataFrame(daily_values)
        values_df['date'] = pd.to_datetime(values_df['date'])
        values_df['return'] = values_df['value'].pct_change()
        values_df['cum_return'] = (1 + values_df['return']).cumprod() - 1

        initial_capital = config.get('portfolio', {}).get('initial_capital', 1_000_000)
        final_value = values_df['value'].iloc[-1]
        total_return = (final_value - initial_capital) / initial_capital

        days = (values_df['date'].iloc[-1] - values_df['date'].iloc[0]).days
        years = days / 365
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return

        # 最大回撤
        values_df['rolling_max'] = values_df['value'].cummax()
        values_df['drawdown'] = (values_df['value'] - values_df['rolling_max']) / values_df['rolling_max']
        max_drawdown = values_df['drawdown'].min()

        # 夏普比率
        daily_returns = values_df['return'].dropna()
        if len(daily_returns) > 20 and daily_returns.std() > 0:
            sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252)
        else:
            sharpe = 0

        # 索提诺比率 (只考虑下行波动)
        downside_returns = daily_returns[daily_returns < 0]
        if len(downside_returns) > 10 and downside_returns.std() > 0:
            sortino = daily_returns.mean() / downside_returns.std() * np.sqrt(252)
        else:
            sortino = 0

        # 卡玛比率
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        return {
            'sharpe': sharpe,
            'sortino': sortino,
            'calmar': calmar,
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'final_value': final_value,
            'trading_days': len(values_df),
            'rebalance_count': len(rebalance_dates)
        }


def run_optimization(
    start_date: str = "20250101",
    end_date: str = "20260331",
    n_trials: int = 50,
    optimization_type: str = "strategy",
    save_results: bool = True
):
    """
    运行参数优化

    Args:
        start_date: 回测开始日期
        end_date: 回测结束日期
        n_trials: 优化试验次数
        optimization_type: 优化类型 ('strategy', 'factor_weights', 'stop_loss')
        save_results: 是否保存结果
    """
    print("=" * 70)
    print("策略参数优化 - 贝叶斯优化")
    print("=" * 70)
    print(f"回测期间：{start_date} ~ {end_date}")
    print(f"试验次数：{n_trials}")
    print(f"优化类型：{optimization_type}")
    print()

    # 加载配置
    with open(root_dir / 'config' / 'config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # 初始化数据获取器
    fetcher = IndexDataFetcher()

    try:
        # 创建回测包装器
        wrapper = BacktestWrapper(config, start_date, end_date, fetcher)

        # 选择参数空间
        if optimization_type == "strategy":
            param_space = get_strategy_param_space()
        elif optimization_type == "factor_weights":
            param_space = get_factor_weight_space()
        elif optimization_type == "stop_loss":
            param_space = get_stop_loss_param_space()
        else:
            raise ValueError(f"Unknown optimization_type: {optimization_type}")

        # 创建优化器
        optimizer = BayesianOptimizer(
            backtest_func=wrapper.run_backtest,
            param_space=param_space,
            n_trials=n_trials,
            random_state=42,
            n_initial_points=min(10, n_trials // 5)
        )

        # 执行优化
        result = optimizer.optimize(verbose=True)

        # 输出结果
        print()
        print(result.summary())

        # 保存结果
        if save_results:
            results_dir = root_dir / 'optimization_results'
            results_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # 保存最优参数
            best_params_file = results_dir / f'best_params_{optimization_type}_{timestamp}.yaml'
            with open(best_params_file, 'w') as f:
                yaml.dump({
                    'best_params': result.best_params,
                    'best_score': result.best_score,
                    'n_trials': result.n_trials,
                    'optimization_time': result.optimization_time,
                    'period': f'{start_date} ~ {end_date}'
                }, f, allow_unicode=True)
            print(f"\n最优参数已保存：{best_params_file}")

            # 保存试验历史
            trial_history_file = results_dir / f'trial_history_{optimization_type}_{timestamp}.csv'
            result.to_dataframe().to_csv(trial_history_file, index=False)
            print(f"试验历史已保存：{trial_history_file}")

        return result

    finally:
        fetcher.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='策略参数优化')
    parser.add_argument('--start', type=str, default='20250101', help='开始日期')
    parser.add_argument('--end', type=str, default='20260331', help='结束日期')
    parser.add_argument('--trials', type=int, default=50, help='试验次数')
    parser.add_argument('--type', type=str, default='strategy',
                        choices=['strategy', 'factor_weights', 'stop_loss'],
                        help='优化类型')

    args = parser.parse_args()

    result = run_optimization(
        start_date=args.start,
        end_date=args.end,
        n_trials=args.trials,
        optimization_type=args.type
    )
