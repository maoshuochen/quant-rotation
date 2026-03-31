#!/usr/bin/env python3
"""
多目标参数优化脚本
同时优化夏普比率、最大回撤和总收益
"""
import sys
import logging
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import pandas as pd
import yaml

from src.optimizer import (
    MultiObjectiveOptimizer,
    BayesianOptimizer,
    ParameterSpace,
    get_factor_weight_space
)
from src.data_fetcher_baostock import IndexDataFetcher
from src.scoring_baostock import ScoringEngine
from src.portfolio import SimulatedPortfolio

logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


class BacktestWrapper:
    """回测包装器 - 用于多目标优化"""

    def __init__(self, config: Dict, start_date: str, end_date: str, fetcher: IndexDataFetcher):
        self.config = config
        self.start_date = start_date
        self.end_date = end_date
        self.fetcher = fetcher
        self.etf_data = self._load_all_data()
        self.benchmark_data = self.etf_data.get('000300.SH', pd.DataFrame())

    def _load_all_data(self) -> Dict[str, pd.DataFrame]:
        """预加载所有 ETF 数据"""
        etf_data = {}
        indices = self.config.get('indices', [])
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
        """归一化因子权重"""
        valid_weights = {k: v for k, v in weights.items() if v > 0}
        if not valid_weights:
            return self.config.get('factor_weights', {})
        total = sum(valid_weights.values())
        return {k: v / total for k, v in valid_weights.items()}

    def run_backtest(self, params: Dict) -> Dict:
        """运行单次回测"""
        temp_config = self.config.copy()

        # 更新因子权重
        factor_weight_keys = [
            'value_weight', 'momentum_weight', 'trend_weight',
            'flow_weight', 'volatility_weight', 'fundamental_weight',
            'sentiment_weight'
        ]
        if any(k in params for k in factor_weight_keys):
            weights = {}
            for key in factor_weight_keys:
                if key in params:
                    factor_name = key.replace('_weight', '')
                    weights[factor_name] = params[key]
            normalized_weights = self._normalize_factor_weights(weights)
            temp_config['factor_weights'] = normalized_weights

        scorer = ScoringEngine(temp_config)
        strategy = temp_config.get('strategy', {})
        top_n = strategy.get('top_n', 5)
        buffer_n = strategy.get('buffer_n', 8)

        portfolio = SimulatedPortfolio(
            initial_capital=1_000_000,
            commission_rate=0.0003,
            slippage=0.001,
            stop_loss_config=temp_config.get('stop_loss', {}),
            cooldown_days=0
        )

        first_df = list(self.etf_data.values())[0]
        all_dates = first_df.index.tolist()
        trade_dates = [d for d in all_dates
                       if pd.to_datetime(self.start_date) <= d <= pd.to_datetime(self.end_date)]
        rebalance_dates = [d for d in trade_dates if d.weekday() == 0]

        daily_values = []

        for date in trade_dates:
            prices = {code: df.loc[date, 'close']
                      for code, df in self.etf_data.items() if date in df.index}

            if prices and portfolio.positions:
                stop_loss_signals = portfolio.check_stop_loss(prices, date.strftime('%Y-%m-%d'))
                if any(stop_loss_signals.values()):
                    names = {idx['code']: idx['name'] for idx in self.config.get('indices', [])}
                    portfolio.execute_stop_loss(stop_loss_signals, prices, names, date.strftime('%Y-%m-%d'))

            if prices:
                portfolio.record_daily_value(date.strftime('%Y-%m-%d'), prices)
                value = portfolio.get_portfolio_value(prices)
                daily_values.append({'date': date.strftime('%Y-%m-%d'), 'value': value})

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
                    names = {idx['code']: idx['name'] for idx in self.config.get('indices', [])}
                    portfolio.execute_signal(signals, prices, names, date.strftime('%Y-%m-%d'))

        if not daily_values:
            return {'sharpe': -999, 'total_return': -1.0, 'max_drawdown': -1.0}

        values_df = pd.DataFrame(daily_values)
        values_df['date'] = pd.to_datetime(values_df['date'])
        values_df['return'] = values_df['value'].pct_change()
        values_df['cum_return'] = (1 + values_df['return']).cumprod() - 1

        final_value = values_df['value'].iloc[-1]
        total_return = (final_value - 1_000_000) / 1_000_000

        values_df['rolling_max'] = values_df['value'].cummax()
        values_df['drawdown'] = (values_df['value'] - values_df['rolling_max']) / values_df['rolling_max']
        max_drawdown = values_df['drawdown'].min()

        daily_returns = values_df['return'].dropna()
        sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252) if len(daily_returns) > 20 and daily_returns.std() > 0 else 0

        downside_returns = daily_returns[daily_returns < 0]
        sortino = daily_returns.mean() / downside_returns.std() * np.sqrt(252) if len(downside_returns) > 10 and downside_returns.std() > 0 else 0

        calmar = total_return / abs(max_drawdown) if max_drawdown != 0 else 0

        return {
            'sharpe': sharpe,
            'sortino': sortino,
            'calmar': calmar,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'final_value': final_value,
            'trading_days': len(values_df)
        }


def run_multi_objective_optimization(
    start_date: str = "20250101",
    end_date: str = "20260331",
    n_trials: int = 50,
    objective: str = 'composite',
    weights: Optional[Dict[str, float]] = None,
    save_results: bool = True
):
    """运行多目标优化"""
    print("=" * 70)
    print("多目标参数优化")
    print("=" * 70)
    print(f"回测期间：{start_date} ~ {end_date}")
    print(f"试验次数：{n_trials}")
    print(f"优化目标：{objective}")
    if weights:
        print(f"权重配置：{weights}")
    print()

    with open(root_dir / 'config' / 'config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    fetcher = IndexDataFetcher()

    try:
        wrapper = BacktestWrapper(config, start_date, end_date, fetcher)
        param_space = get_factor_weight_space()

        optimizer = MultiObjectiveOptimizer(
            backtest_func=wrapper.run_backtest,
            param_space=param_space,
            n_trials=n_trials,
            random_state=42,
            n_initial_points=min(10, n_trials // 5),
            objective=objective,
            weights=weights
        )

        result = optimizer.optimize(verbose=True)

        print()
        print(result.summary())

        # 输出 Pareto 前沿
        pareto_front = optimizer.get_pareto_front()
        if pareto_front:
            print("\n" + "=" * 70)
            print(f"Pareto 前沿 ({len(pareto_front)}个解)")
            print("=" * 70)
            print(f"{'Sharpe':>8} {'Return':>10} {'Drawdown':>10} {'Calmar':>8}")
            print("-" * 40)
            for item in sorted(pareto_front, key=lambda x: -x['metrics']['sharpe']):
                m = item['metrics']
                print(f"{m['sharpe']:8.3f} {m['return']:10.1%} {m['drawdown']:10.1%} {m['return']/m['drawdown']:8.2f}")

        if save_results:
            results_dir = root_dir / 'optimization_results'
            results_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # 保存最优参数
            best_params_file = results_dir / f'multi_obj_best_{objective}_{timestamp}.yaml'
            with open(best_params_file, 'w') as f:
                yaml.dump({
                    'best_params': result.best_params,
                    'best_score': result.best_score,
                    'objective': objective,
                    'weights': weights,
                    'n_trials': result.n_trials,
                    'optimization_time': result.optimization_time,
                    'period': f'{start_date} ~ {end_date}',
                    'pareto_front_size': len(pareto_front)
                }, f, allow_unicode=True, default_flow_style=False)
            print(f"\n最优参数已保存：{best_params_file}")

            # 保存试验历史
            trial_df = optimizer.get_trial_history()
            trial_file = results_dir / f'multi_obj_history_{objective}_{timestamp}.csv'
            trial_df.to_csv(trial_file, index=False)
            print(f"试验历史已保存：{trial_file}")

        return result, optimizer

    finally:
        fetcher.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='多目标参数优化')
    parser.add_argument('--start', type=str, default='20250101', help='开始日期')
    parser.add_argument('--end', type=str, default='20260331', help='结束日期')
    parser.add_argument('--trials', type=int, default=50, help='试验次数')
    parser.add_argument('--objective', type=str, default='composite',
                        choices=['composite', 'sharpe', 'drawdown', 'return'],
                        help='优化目标')
    parser.add_argument('--sharpe-weight', type=float, default=0.4, help='Sharpe 权重')
    parser.add_argument('--drawdown-weight', type=float, default=0.3, help='回撤权重')
    parser.add_argument('--return-weight', type=float, default=0.3, help='收益权重')

    args = parser.parse_args()

    weights = {
        'sharpe': args.sharpe_weight,
        'drawdown': args.drawdown_weight,
        'return': args.return_weight
    }

    result, optimizer = run_multi_objective_optimization(
        start_date=args.start,
        end_date=args.end,
        n_trials=args.trials,
        objective=args.objective,
        weights=weights if args.objective == 'composite' else None
    )
