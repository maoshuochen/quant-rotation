#!/usr/bin/env python3
"""
生成因子 IC/IR 跟踪报告
用于监控因子表现和检测因子衰减
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional
import pandas as pd
import numpy as np

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.data_fetcher_baostock import IndexDataFetcher
from src.scoring_baostock import ScoringEngine
from src.config_loader import load_app_config
from src.factor_analysis import FactorAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG = load_app_config(root_dir)


def calculate_factor_ic(
    etf_data_dict: Dict[str, pd.DataFrame],
    benchmark_data: pd.DataFrame,
    scorer: ScoringEngine,
    lookback_days: int = 252
) -> Dict[str, Dict]:
    """
    计算各因子的 IC 值 (Information Coefficient)

    IC = 因子值与未来收益率的相关系数
    """
    # 收集所有因子的历史得分
    factor_history = {factor: [] for factor in scorer.active_factors}
    forward_returns_5d = []
    forward_returns_10d = []
    forward_returns_20d = []
    dates = []

    # 获取所有交易日期
    all_dates = sorted(set.intersection(*[set(df.index) for df in etf_data_dict.values() if not df.empty]))
    all_dates = list(all_dates)

    logger.info(f"分析 {len(all_dates)} 个交易日期")

    # 对每个日期计算因子得分和未来收益
    for i, date in enumerate(all_dates):
        # 需要有未来 20 日数据才能计算 IC
        if i + 20 >= len(all_dates):
            continue

        # 找到日期索引
        date_idx = {code: df.index.get_loc(date) if date in df.index else None
                    for code, df in etf_data_dict.items()}

        # 计算当日各 ETF 的因子得分
        etf_scores = {}
        for code, df in etf_data_dict.items():
            if date not in df.index:
                continue

            idx = df.index.get_loc(date)
            if idx < 60:
                continue

            # 取历史数据进行评分
            hist_data = df.iloc[max(0, idx-lookback_days):idx+1]
            bench_hist = benchmark_data.loc[:date].tail(lookback_days) if not benchmark_data.empty else None

            if len(hist_data) < 60:
                continue

            scores = scorer.score_index(hist_data, benchmark_data=bench_hist)

            if scores and 'total_score' in scores:
                etf_scores[code] = scores

        if not etf_scores:
            continue

        # 计算未来收益 (简单平均所有 ETF 的未来收益)
        future_5d = []
        future_10d = []
        future_20d = []

        for code, df in etf_data_dict.items():
            if date not in df.index:
                continue
            idx = df.index.get_loc(date)

            if idx + 20 < len(df):
                ret_5d = df['close'].iloc[idx + 5] / df['close'].iloc[idx] - 1
                ret_10d = df['close'].iloc[idx + 10] / df['close'].iloc[idx] - 1
                ret_20d = df['close'].iloc[idx + 20] / df['close'].iloc[idx] - 1
                future_5d.append(ret_5d)
                future_10d.append(ret_10d)
                future_20d.append(ret_20d)

        if not future_5d:
            continue

        # 平均未来收益
        avg_future_5d = np.mean(future_5d)
        avg_future_10d = np.mean(future_10d) if future_10d else None
        avg_future_20d = np.mean(future_20d) if future_20d else None

        # 记录因子得分 (使用平均总分)
        avg_total_score = np.mean([s['total_score'] for s in etf_scores.values()])

        for factor in scorer.active_factors:
            factor_scores = [s.get(factor, 0.5) for s in etf_scores.values()]
            factor_history[factor].append(np.mean(factor_scores))

        forward_returns_5d.append(avg_future_5d)
        if avg_future_10d is not None:
            forward_returns_10d.append(avg_future_10d)
        if avg_future_20d is not None:
            forward_returns_20d.append(avg_future_20d)
        dates.append(date)

    # 计算 IC
    ic_results = {}

    for factor in scorer.active_factors:
        factor_values = factor_history[factor]

        if len(factor_values) < 30:
            ic_results[factor] = {
                'ic_5d': None,
                'sample_size': len(factor_values),
                'status': 'insufficient_data'
            }
            continue

        # 对齐数据
        min_len = min(len(factor_values), len(forward_returns_5d))
        factor_values = factor_values[:min_len]
        returns_5d = forward_returns_5d[:min_len]

        # 计算 IC (相关系数)
        try:
            ic_5d = np.corrcoef(factor_values, returns_5d)[0, 1]
        except Exception as e:
            logger.warning(f"IC 计算失败 {factor}: {e}")
            ic_5d = None

        # 计算 IR (IC/IC 标准差) - 这里简化处理
        ic_std = np.std(factor_values) if len(factor_values) > 0 else 0
        ir = ic_5d / ic_std if ic_5d is not None and ic_std > 0 else 0

        ic_results[factor] = {
            'ic_5d': round(ic_5d, 4) if ic_5d is not None else None,
            'ir': round(ir, 2),
            'sample_size': min_len,
            'status': 'ok'
        }

    return ic_results


def analyze_factor_trend(ic_results: Dict[str, Dict]) -> Dict[str, str]:
    """分析因子趋势"""
    trends = {}

    for factor, metrics in ic_results.items():
        if metrics['status'] == 'insufficient_data':
            trends[factor] = 'unknown'
            continue

        ic = metrics.get('ic_5d')
        ir = metrics.get('ir', 0)

        if ic is None:
            trends[factor] = 'unknown'
        elif ic > 0.1 and ir > 0.5:
            trends[factor] = 'strong'
        elif ic > 0.05 and ir > 0:
            trends[factor] = 'stable'
        elif ic > 0:
            trends[factor] = 'weak'
        else:
            trends[factor] = 'declining'

    return trends


def generate_report():
    """生成因子 IC/IR 报告"""
    logger.info("开始生成因子 IC/IR 报告...")

    fetcher = IndexDataFetcher()
    indices = CONFIG.get('indices', [])
    active_indices = [idx for idx in indices if idx.get('enabled', True)]

    # 加载基准数据
    logger.info("加载基准数据...")
    benchmark_df = fetcher.fetch_etf_history('510300', '20230101')

    # 加载所有 ETF 数据
    logger.info("加载 ETF 历史数据...")
    etf_data_dict = {}
    for idx in active_indices:
        etf = idx.get('etf')
        if etf:
            df = fetcher.fetch_etf_history(etf, '20230101')
            if not df.empty:
                etf_data_dict[idx['code']] = df

    # 初始化评分引擎
    scorer = ScoringEngine(CONFIG)

    # 计算 IC
    logger.info("计算因子 IC 值...")
    ic_results = calculate_factor_ic(etf_data_dict, benchmark_df, scorer)

    # 分析趋势
    trends = analyze_factor_trend(ic_results)

    # 生成报告
    report = {
        "agent": "strategy_agent",
        "timestamp": datetime.now().isoformat(),
        "report_type": "factor_ic_tracking",
        "factor_analysis": {},
        "summary": {
            "best_factor": None,
            "concerns": []
        }
    }

    best_ic = -1
    best_factor = None

    for factor in scorer.active_factors:
        if factor not in ic_results:
            continue

        metrics = ic_results[factor]
        trend = trends.get(factor, 'unknown')

        report["factor_analysis"][factor] = {
            "ic_5d": metrics.get('ic_5d'),
            "ir": metrics.get('ir'),
            "sample_size": metrics.get('sample_size'),
            "trend": trend,
            "current_weight": CONFIG.get('factor_weights', {}).get(factor, 0)
        }

        # 找出最佳因子
        ic_val = metrics.get('ic_5d')
        if ic_val is not None and ic_val > best_ic:
            best_ic = ic_val
            best_factor = factor

        # 检查是否有衰减迹象
        if trend in ['weak', 'declining']:
            report["summary"]["concerns"].append(f"{factor} 因子表现较弱 (IC={ic_val})")

    report["summary"]["best_factor"] = best_factor

    # 保存到文件
    output_dir = root_dir / 'reports' / 'agents'
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f'factor_ic_report_{datetime.now().strftime("%Y%m%d")}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"报告已保存至：{output_file}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("因子 IC/IR 跟踪报告摘要")
    print("=" * 60)

    for factor, data in report["factor_analysis"].items():
        print(f"\n{factor}:")
        print(f"  IC 5 日：{data['ic_5d']}")
        print(f"  IR: {data['ir']}")
        print(f"  趋势：{data['trend']}")
        print(f"  当前权重：{data['current_weight']}")

    print(f"\n最佳因子：{report['summary']['best_factor']}")
    if report['summary']['concerns']:
        print(f"关注事项：{', '.join(report['summary']['concerns'])}")

    print("=" * 60)

    fetcher.close()
    return report


if __name__ == "__main__":
    generate_report()
