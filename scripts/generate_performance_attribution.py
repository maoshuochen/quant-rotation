#!/usr/bin/env python3
"""
业绩归因分析脚本
分析各持仓对总收益的贡献，以及因子暴露对收益的贡献
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.data_fetcher_baostock import IndexDataFetcher
from src.config_loader import load_app_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG = load_app_config(root_dir)


def analyze_position_contribution(
    positions: List[Dict],
    etf_data_dict: Dict[str, pd.DataFrame],
    start_date: str,
    end_date: str
) -> List[Dict]:
    """
    分析各持仓对总收益的贡献

    Args:
        positions: 持仓列表
        etf_data_dict: ETF 数据字典
        start_date: 起始日期
        end_date: 结束日期

    Returns:
        各持仓贡献度列表
    """
    contributions = []

    for pos in positions:
        code = pos['code']
        shares = pos['shares']
        avg_price = pos['avg_price']
        entry_date = pos['entry_date']

        # 获取 ETF 数据
        if code not in etf_data_dict:
            logger.warning(f"未找到 {code} 的数据")
            continue

        df = etf_data_dict[code]

        # 找到 entry_date 附近的价格
        if entry_date not in df.index:
            # 找最接近的日期
            available_dates = df.index[df.index <= entry_date]
            if len(available_dates) == 0:
                continue
            entry_date = available_dates[-1]

        # 计算持仓期间收益
        entry_price = df.loc[entry_date, 'close']

        # 找到 end_date 附近的价格
        available_dates = df.index[df.index <= end_date]
        if len(available_dates) == 0:
            continue
        actual_end_date = available_dates[-1]
        exit_price = df.loc[actual_end_date, 'close']

        # 持仓收益
        position_return = (exit_price - entry_price) * shares
        position_return_pct = (exit_price - entry_price) / entry_price

        # 持仓市值
        entry_value = entry_price * shares
        current_value = exit_price * shares

        contributions.append({
            'code': code,
            'name': pos.get('name', code),
            'shares': shares,
            'entry_date': str(entry_date)[:10] if hasattr(entry_date, 'strftime') else str(entry_date)[:10],
            'exit_date': str(actual_end_date)[:10] if hasattr(actual_end_date, 'strftime') else str(actual_end_date)[:10],
            'entry_price': round(float(entry_price), 4),
            'exit_price': round(float(exit_price), 4),
            'return_pct': round(float(position_return_pct), 4),
            'return_abs': round(float(position_return), 2),
            'entry_value': round(float(entry_value), 2),
            'current_value': round(float(current_value), 2),
            'contribution_to_portfolio': round(float(position_return), 2)
        })

    return contributions


def analyze_benchmark_comparison(
    portfolio_return: float,
    etf_data_dict: Dict[str, pd.DataFrame],
    start_date: str,
    end_date: str
) -> Dict:
    """
    分析相对于基准的收益
    """
    # 沪深 300 基准
    if '510300' in [idx.get('etf') for idx in CONFIG.get('indices', [])]:
        benchmark_code = '510300'
    else:
        benchmark_code = '000300.SH'

    # 获取基准数据
    benchmark_df = None
    for code, df in etf_data_dict.items():
        if benchmark_code in code or (benchmark_code == '510300' and '510300' in str(df)):
            benchmark_df = df
            break

    if benchmark_df is None:
        # 尝试直接获取
        for code, df in etf_data_dict.items():
            if '510300' in code:
                benchmark_df = df
                break

    if benchmark_df is not None:
        # 找到起始和结束日期
        available_dates = benchmark_df.index
        start_idx = available_dates.searchsorted(start_date)
        end_idx = available_dates.searchsorted(end_date)

        if start_idx < len(available_dates) and end_idx > 0:
            start_price = benchmark_df.iloc[start_idx]['close']
            end_price = benchmark_df.iloc[min(end_idx, len(available_dates)-1)]['close']
            benchmark_return = (end_price - start_price) / start_price

            return {
                'benchmark': '沪深 300',
                'benchmark_return': round(benchmark_return, 4),
                'portfolio_return': round(portfolio_return, 4),
                'excess_return': round(portfolio_return - benchmark_return, 4),
                'outperformance': portfolio_return > benchmark_return
            }

    return {
        'benchmark': 'N/A',
        'benchmark_return': None,
        'portfolio_return': round(portfolio_return, 4),
        'excess_return': None,
        'outperformance': None
    }


def calculate_portfolio_metrics(nav_series: pd.Series) -> Dict:
    """
    计算组合业绩指标
    """
    if len(nav_series) < 2:
        return {}

    returns = nav_series.pct_change().dropna()

    # 基础指标
    total_return = (nav_series.iloc[-1] - nav_series.iloc[0]) / nav_series.iloc[0]
    days = (nav_series.index[-1] - nav_series.index[0]).days if hasattr(nav_series.index[0], 'days') else len(nav_series)
    annual_return = (1 + total_return) ** (365 / max(days, 1)) - 1

    # 风险指标
    volatility = returns.std() * np.sqrt(252)
    downside_returns = returns[returns < 0]
    downside_vol = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else volatility

    # 夏普比率 (假设无风险利率 2%)
    rf = 0.02
    sharpe = (annual_return - rf) / volatility if volatility > 0 else 0

    # 卡玛比率
    max_drawdown = (nav_series / nav_series.cummax() - 1).min()
    calmar = (annual_return - rf) / abs(max_drawdown) if max_drawdown != 0 else 0

    # 最大回撤分析
    drawdown_series = nav_series / nav_series.cummax() - 1
    max_dd = drawdown_series.min()
    max_dd_date = drawdown_series.idxmin()

    return {
        'total_return': round(total_return, 4),
        'annual_return': round(annual_return, 4),
        'volatility': round(volatility, 4),
        'downside_volatility': round(downside_vol, 4),
        'sharpe_ratio': round(sharpe, 2),
        'calmar_ratio': round(calmar, 2),
        'max_drawdown': round(float(max_dd), 4),
        'max_drawdown_date': str(max_dd_date) if pd.notna(max_dd_date) else None,
        'trading_days': len(nav_series),
        'win_rate': round(float((returns > 0).mean()), 4) if len(returns) > 0 else None
    }


def generate_report():
    """生成业绩归因报告"""
    logger.info("开始生成业绩归因报告...")

    fetcher = IndexDataFetcher()
    indices = CONFIG.get('indices', [])
    active_indices = [idx for idx in indices if idx.get('enabled', True)]

    # 加载 ETF 数据
    logger.info("加载 ETF 历史数据...")
    etf_data_dict = {}
    for idx in active_indices:
        etf = idx.get('etf')
        if etf:
            df = fetcher.fetch_etf_history(etf, '20230101')
            if not df.empty:
                etf_data_dict[idx['code']] = df

    # 加载回测结果
    backtest_file = root_dir / 'backtest_results' / 'current.parquet'
    if not backtest_file.exists():
        logger.error("回测结果文件不存在")
        fetcher.close()
        return None

    nav_df = pd.read_parquet(backtest_file)
    nav_df['date'] = pd.to_datetime(nav_df['date'])
    nav_df = nav_df.set_index('date')

    # 加载持仓
    positions_file = root_dir / 'backtest_results' / 'current.positions.json'
    if not positions_file.exists():
        logger.warning("持仓文件不存在")
        positions = []
    else:
        with open(positions_file) as f:
            positions = json.load(f)

    # 计算组合指标
    logger.info("计算组合业绩指标...")
    metrics = calculate_portfolio_metrics(nav_df['value'])

    # 分析持仓贡献
    if positions and nav_df.index[0] is not None:
        logger.info("分析持仓贡献...")
        start_date = str(nav_df.index[0].strftime('%Y-%m-%d'))
        end_date = str(nav_df.index[-1].strftime('%Y-%m-%d'))

        contributions = analyze_position_contribution(
            positions, etf_data_dict, start_date, end_date
        )

        # 计算总贡献
        total_contribution = sum(c['return_abs'] for c in contributions)
        for c in contributions:
            c['contribution_pct'] = round(c['return_abs'] / total_contribution, 4) if total_contribution != 0 else 0
    else:
        contributions = []

    # 基准对比
    logger.info("分析基准对比...")
    initial_capital = nav_df['value'].iloc[0]
    final_value = nav_df['value'].iloc[-1]
    portfolio_return = (final_value - initial_capital) / initial_capital

    benchmark_comp = analyze_benchmark_comparison(
        portfolio_return, etf_data_dict,
        nav_df.index[0].strftime('%Y-%m-%d'),
        nav_df.index[-1].strftime('%Y-%m-%d')
    )

    # 生成报告
    report = {
        "agent": "backtest_agent",
        "timestamp": datetime.now().isoformat(),
        "report_type": "performance_attribution",
        "performance": metrics,
        "position_attribution": {
            "holdings": contributions,
            "total_contribution": round(total_contribution, 2) if contributions else 0
        },
        "benchmark_comparison": benchmark_comp,
        "summary": {
            "overall": "",
            "highlights": [],
            "concerns": []
        }
    }

    # 生成总结
    if metrics.get('sharpe_ratio', 0) > 1:
        report["summary"]["highlights"].append("夏普比率优秀")
    elif metrics.get('sharpe_ratio', 0) > 0.5:
        report["summary"]["highlights"].append("夏普比率良好")
    else:
        report["summary"]["concerns"].append("夏普比率有待提升")

    if benchmark_comp.get('excess_return') and benchmark_comp['excess_return'] > 0:
        report["summary"]["highlights"].append(f"跑赢基准 {benchmark_comp['excess_return']*100:.2f}%")
    elif benchmark_comp.get('excess_return'):
        report["summary"]["concerns"].append(f"跑输基准 {abs(benchmark_comp['excess_return'])*100:.2f}%")

    # 总体评价
    if len(report["summary"]["highlights"]) >= 2:
        report["summary"]["overall"] = "策略表现优秀"
    elif len(report["summary"]["highlights"]) >= 1:
        report["summary"]["overall"] = "策略表现良好"
    else:
        report["summary"]["overall"] = "策略表现一般，需要优化"

    # 保存到文件
    output_dir = root_dir / 'reports' / 'agents'
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f'backtest_attribution_{datetime.now().strftime("%Y%m%d")}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"报告已保存至：{output_file}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("业绩归因分析报告摘要")
    print("=" * 60)

    print(f"\n组合业绩指标:")
    print(f"  总收益率：{metrics.get('total_return', 0)*100:.2f}%")
    print(f"  年化收益：{metrics.get('annual_return', 0)*100:.2f}%")
    print(f"  夏普比率：{metrics.get('sharpe_ratio', 0):.2f}")
    print(f"  最大回撤：{metrics.get('max_drawdown', 0)*100:.2f}%")

    print(f"\n基准对比:")
    print(f"  基准：{benchmark_comp.get('benchmark', 'N/A')}")
    print(f"  基准收益：{benchmark_comp.get('benchmark_return', 0)}")
    print(f"  超额收益：{benchmark_comp.get('excess_return', 0)}")

    if contributions:
        print(f"\n持仓贡献分析:")
        sorted_contributions = sorted(contributions, key=lambda x: x['return_abs'], reverse=True)
        for c in sorted_contributions[:3]:
            print(f"  {c['name']}: {c['return_abs']:,.0f}元 ({c['return_pct']*100:.2f}%)")

    print(f"\n总体评价：{report['summary']['overall']}")
    if report['summary']['highlights']:
        print(f"亮点：{', '.join(report['summary']['highlights'])}")
    if report['summary']['concerns']:
        print(f"关注：{', '.join(report['summary']['concerns'])}")

    print("=" * 60)

    fetcher.close()
    return report


if __name__ == "__main__":
    generate_report()
