#!/usr/bin/env python3
"""
风险指标计算脚本
计算 VaR、Expected Shortfall、波动率等风险指标
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from scipy import stats

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.data_fetcher_baostock import IndexDataFetcher
from src.config_loader import load_app_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG = load_app_config(root_dir)


def calculate_var(returns: pd.Series, confidence_level: float = 0.95) -> float:
    """
    计算 Value at Risk (VaR)

    Args:
        returns: 收益率序列
        confidence_level: 置信水平 (0.95 或 0.99)

    Returns:
        VaR 值 (负值表示损失)
    """
    # 历史模拟法
    var = np.percentile(returns.dropna(), (1 - confidence_level) * 100)
    return float(var)


def calculate_expected_shortfall(returns: pd.Series, confidence_level: float = 0.95) -> float:
    """
    计算 Expected Shortfall (CVaR)

    Args:
        returns: 收益率序列
        confidence_level: 置信水平

    Returns:
        Expected Shortfall 值
    """
    var = calculate_var(returns, confidence_level)
    es = returns[returns <= var].mean()
    return float(es) if not pd.isna(es) else var


def calculate_portfolio_volatility(returns: pd.Series) -> float:
    """
    计算组合波动率 (年化)
    """
    daily_vol = returns.std()
    annual_vol = daily_vol * np.sqrt(252)
    return float(annual_vol)


def calculate_beta(portfolio_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """
    计算 Beta 系数 (相对于基准)
    """
    # 对齐数据
    common_idx = portfolio_returns.index.intersection(benchmark_returns.index)
    if len(common_idx) < 30:
        return 1.0

    port_ret = portfolio_returns.loc[common_idx]
    bench_ret = benchmark_returns.loc[common_idx]

    # 计算协方差和方差
    covariance = np.cov(port_ret, bench_ret)[0, 1]
    benchmark_variance = np.var(bench_ret)

    if benchmark_variance == 0:
        return 1.0

    beta = covariance / benchmark_variance
    return float(beta)


def calculate_position_risk(positions: List[Dict], etf_data_dict: Dict[str, pd.DataFrame]) -> Dict:
    """
    计算持仓风险分析
    """
    if not positions:
        return {}

    # 持仓集中度 (HHI 指数)
    total_value = 0
    values = []

    for pos in positions:
        code = pos['code']
        shares = pos['shares']

        if code in etf_data_dict:
            df = etf_data_dict[code]
            current_price = df['close'].iloc[-1]
            value = shares * current_price
            values.append(value)
            total_value += value

    if total_value == 0:
        return {}

    # HHI 指数 (集中度越高，值越大)
    weights = [v / total_value for v in values]
    hhi = sum(w ** 2 for w in weights)

    # 前 N 大持仓占比
    top5_weight = sum(sorted(weights, reverse=True)[:5]) if len(weights) >= 5 else sum(weights)

    return {
        'concentration_hhi': round(hhi, 4),
        'top5_weight': round(top5_weight, 4),
        'num_holdings': len(positions),
        'total_value': round(total_value, 2)
    }


def calculate_correlation_risk(etf_data_dict: Dict[str, pd.DataFrame]) -> str:
    """
    评估相关性风险
    """
    if len(etf_data_dict) < 2:
        return 'low'

    # 计算收益率相关性
    returns_dict = {}
    for code, df in etf_data_dict.items():
        if len(df) >= 60:
            returns_dict[code] = df['close'].pct_change().dropna()

    if len(returns_dict) < 2:
        return 'low'

    # 计算平均相关性
    correlations = []
    codes = list(returns_dict.keys())
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            code1, code2 = codes[i], codes[j]
            common_idx = returns_dict[code1].index.intersection(returns_dict[code2].index)
            if len(common_idx) >= 30:
                corr = returns_dict[code1].loc[common_idx].corr(returns_dict[code2].loc[common_idx])
                correlations.append(corr)

    if not correlations:
        return 'low'

    avg_corr = np.mean(correlations)

    if avg_corr > 0.8:
        return 'high'
    elif avg_corr > 0.5:
        return 'medium'
    else:
        return 'low'


def stress_test(nav_series: pd.Series) -> Dict:
    """
    简单压力测试
    """
    if len(nav_series) < 60:
        return {}

    returns = nav_series.pct_change().dropna()

    # 历史最坏情况
    worst_daily = returns.min()
    worst_weekly = returns.rolling(5).sum().min()
    worst_monthly = returns.rolling(21).sum().min()

    # 模拟压力情景
    # 1. 2015 股灾情景 (-30% 在短期内)
    scenario_2015 = -0.30

    # 2. 2020 疫情情景 (-20% 快速下跌)
    scenario_2020 = -0.20

    # 3. 历史最大回撤延续
    max_drawdown = (nav_series / nav_series.cummax() - 1).min()
    stress_scenario = max(max_drawdown * 1.5, -0.40)  # 假设最坏情况是当前回撤的 1.5 倍

    return {
        'worst_daily': round(worst_daily, 4),
        'worst_weekly': round(worst_weekly, 4),
        'worst_monthly': round(worst_monthly, 4),
        'scenario_2015_proxy': round(scenario_2015, 4),
        'scenario_2020_proxy': round(scenario_2020, 4),
        'estimated_stress_loss': round(stress_scenario, 4)
    }


def generate_report():
    """生成风险报告"""
    logger.info("开始生成风险报告...")

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

    # 计算收益率
    returns = nav_df['value'].pct_change().dropna()

    # 风险指标
    logger.info("计算风险指标...")

    # VaR
    var_95 = calculate_var(returns, 0.95)
    var_99 = calculate_var(returns, 0.99)

    # Expected Shortfall
    es_95 = calculate_expected_shortfall(returns, 0.95)
    es_99 = calculate_expected_shortfall(returns, 0.99)

    # 波动率
    portfolio_vol = calculate_portfolio_volatility(returns)

    # Beta (相对于沪深 300)
    benchmark_df = etf_data_dict.get('510300.SH', None)
    if benchmark_df is None:
        # 尝试其他代码格式
        for code, df in etf_data_dict.items():
            if '510300' in code:
                benchmark_df = df
                break

    if benchmark_df is not None and len(benchmark_df) >= 60:
        benchmark_returns = benchmark_df['close'].pct_change().dropna()
        beta = calculate_beta(returns, benchmark_returns)
    else:
        beta = 1.0
        benchmark_returns = None

    # 持仓风险
    logger.info("分析持仓风险...")
    positions_file = root_dir / 'backtest_results' / 'current.positions.json'
    if positions_file.exists():
        with open(positions_file) as f:
            positions = json.load(f)
    else:
        positions = []

    position_risk = calculate_position_risk(positions, etf_data_dict)
    correlation_risk = calculate_correlation_risk(etf_data_dict)

    # 压力测试
    logger.info("执行压力测试...")
    stress_results = stress_test(nav_df['value'])

    # 市场状态判断
    # 基于近期波动率判断
    recent_vol = returns.tail(21).std() * np.sqrt(252)
    if recent_vol > 0.4:
        volatility_regime = 'extreme'
    elif recent_vol > 0.25:
        volatility_regime = 'elevated'
    else:
        volatility_regime = 'normal'

    # 生成警报
    alerts = []

    if var_95 < -0.03:
        alerts.append({
            'level': 'warning',
            'type': 'var',
            'message': f'VaR(95%) 超过阈值：{var_95*100:.2f}%'
        })

    if portfolio_vol > 0.3:
        alerts.append({
            'level': 'warning',
            'type': 'volatility',
            'message': f'组合波动率过高：{portfolio_vol*100:.2f}%'
        })

    if position_risk.get('concentration_hhi', 0) > 0.5:
        alerts.append({
            'level': 'info',
            'type': 'concentration',
            'message': f'持仓集中度较高 (HHI={position_risk["concentration_hhi"]:.2f})'
        })

    # 整体风险评级
    risk_score = 0
    if abs(var_95) > 0.03:
        risk_score += 1
    if portfolio_vol > 0.25:
        risk_score += 1
    if stress_results.get('estimated_stress_loss', 0) < -0.25:
        risk_score += 1
    if position_risk.get('concentration_hhi', 0) > 0.4:
        risk_score += 1

    if risk_score >= 3:
        overall_risk = 'high'
    elif risk_score >= 2:
        overall_risk = 'medium'
    else:
        overall_risk = 'low'

    # 生成报告
    report = {
        "agent": "risk_agent",
        "timestamp": datetime.now().isoformat(),
        "report_type": "risk_assessment",
        "risk_metrics": {
            "var_95": round(var_95, 4),
            "var_99": round(var_99, 4),
            "expected_shortfall_95": round(es_95, 4),
            "expected_shortfall_99": round(es_99, 4),
            "portfolio_volatility": round(portfolio_vol, 4),
            "beta": round(beta, 2)
        },
        "position_risk": position_risk,
        "market_conditions": {
            "volatility_regime": volatility_regime,
            "correlation_risk": correlation_risk,
            "warnings": [a['message'] for a in alerts if a['level'] in ['warning', 'critical']]
        },
        "stress_test": stress_results,
        "alerts": alerts,
        "overall_risk": overall_risk
    }

    # 保存到文件
    output_dir = root_dir / 'reports' / 'agents'
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f'risk_report_{datetime.now().strftime("%Y%m%d")}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"报告已保存至：{output_file}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("风险评估报告摘要")
    print("=" * 60)

    print(f"\n风险指标:")
    print(f"  VaR(95%): {var_95*100:.2f}%")
    print(f"  VaR(99%): {var_99*100:.2f}%")
    print(f"  预期短缺 (95%): {es_95*100:.2f}%")
    print(f"  组合波动率：{portfolio_vol*100:.2f}%")
    print(f"  Beta 系数：{beta:.2f}")

    print(f"\n持仓风险:")
    print(f"  持仓数量：{position_risk.get('num_holdings', 0)}")
    print(f"  集中度 (HHI): {position_risk.get('concentration_hhi', 0):.4f}")
    print(f"  相关性风险：{correlation_risk}")

    print(f"\n压力测试:")
    print(f"  历史最坏日收益：{stress_results.get('worst_daily', 0)*100:.2f}%")
    print(f"  历史最坏周收益：{stress_results.get('worst_weekly', 0)*100:.2f}%")
    print(f"  压力情景估计：{stress_results.get('estimated_stress_loss', 0)*100:.2f}%")

    print(f"\n市场状态：{volatility_regime}")
    print(f"  整体风险评级：{overall_risk}")

    if alerts:
        print(f"\n警报:")
        for alert in alerts:
            print(f"  [{alert['level'].upper()}] {alert['message']}")

    print("=" * 60)

    fetcher.close()
    return report


if __name__ == "__main__":
    generate_report()
