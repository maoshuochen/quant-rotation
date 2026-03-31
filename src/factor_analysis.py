"""
因子分析模块 - IC 分析与分层回测
用于评估因子有效性和稳定性
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ICResult:
    """IC 分析结果"""
    factor_name: str
    ic_mean: float
    ic_std: float
    ic_ir: float  # IC 信息比率 = ic_mean / ic_std
    t_stat: float
    p_value: float
    ic_count: int
    positive_ratio: float  # IC>0 的比例
    ic_time_series: pd.Series = field(default_factory=pd.Series)


@dataclass
class QuantileResult:
    """分层回测结果"""
    factor_name: str
    quantiles: int
    returns: Dict[int, pd.Series]  # 每组的收益曲线
    cumulative_returns: Dict[int, pd.Series]  # 累计收益
    final_returns: Dict[int, float]  # 最终收益
    sharpe_ratios: Dict[int, float]  # 每组夏普比率


class FactorAnalyzer:
    """
    因子分析器

    功能:
    1. IC 分析 - 因子值与下期收益的相关性
    2. 分层回测 - 按因子值分组测试收益
    3. 因子稳定性分析 - 滚动窗口 IC
    4. 因子相关性分析 - 多因子间相关性
    """

    def __init__(self, data_fetcher, config: dict):
        """
        初始化因子分析器

        Args:
            data_fetcher: 数据获取器 (IndexDataFetcher)
            config: 配置字典
        """
        self.fetcher = data_fetcher
        self.config = config
        self.indices = config.get('indices', [])
        self.index_codes = [idx['code'] for idx in self.indices if idx.get('etf')]

    def prepare_factor_data(self, factor_name: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        准备因子数据

        Returns:
            DataFrame with columns: date, code, factor_value, next_return
        """
        # 获取所有 ETF 数据
        etf_data = {}
        for idx in self.indices:
            etf = idx.get('etf')
            code = idx.get('code')
            if etf:
                df = self.fetcher.fetch_etf_history(etf, start_date, force_refresh=False)
                if not df.empty:
                    etf_data[code] = df

        if not etf_data:
            logger.error("No data fetched")
            return pd.DataFrame()

        # 构建因子值和下期收益数据
        records = []
        dates = sorted(list(set().union(*[df.index for df in etf_data.values()])))

        for date in dates:
            if date < pd.Timestamp(start_date) or date > pd.Timestamp(end_date):
                continue

            factor_values = {}
            prices = {}

            for code, df in etf_data.items():
                if date in df.index:
                    # 计算因子值
                    factor_value = self._calc_factor_value(factor_name, df, date)
                    if factor_value is not None and not np.isnan(factor_value):
                        factor_values[code] = factor_value
                        prices[code] = df.loc[date, 'close']

            # 计算下期收益 (21 天后，约 1 个月)
            next_date = date + pd.Timedelta(days=21)
            for code, df in etf_data.items():
                if code in factor_values:
                    if date in df.index and next_date in df.index:
                        current_price = df.loc[date, 'close']
                        future_price = df.loc[next_date, 'close']
                        next_return = (future_price - current_price) / current_price
                        records.append({
                            'date': date,
                            'code': code,
                            'factor_value': factor_values[code],
                            'next_return': next_return
                        })

        return pd.DataFrame(records)

    def _calc_factor_value(self, factor_name: str, df: pd.DataFrame, date: pd.Timestamp) -> Optional[float]:
        """
        计算单个因子值

        支持因子:
        - momentum: 动量 (20 日收益率)
        - volatility: 波动率 (20 日年化波动率，取负值使低波高分)
        - trend: 趋势 (价格相对 MA20 位置)
        - value: 估值 (当前价格在 252 日分位，取负值使低估值高分)
        - flow: 资金流 (20 日成交量趋势)
        """
        if date not in df.index:
            return None

        if len(df) < 60:
            return 0.5  # 数据不足返回中性值

        historical = df[df.index <= date]

        if len(historical) < 20:
            return 0.5

        if factor_name == 'momentum':
            # 20 日收益率
            if len(historical) >= 21:
                returns = historical['close'].pct_change()
                momentum = returns.iloc[-20:].sum()
                return momentum
            return 0.5

        elif factor_name == 'volatility':
            # 20 日年化波动率 (取负)
            if len(historical) >= 21:
                returns = historical['close'].pct_change()
                vol = returns.iloc[-20:].std() * np.sqrt(252)
                return -vol  # 低波动率高分数
            return 0.5

        elif factor_name == 'trend':
            # 价格相对 MA20 位置
            ma20 = historical['close'].rolling(20).mean().iloc[-1]
            current = historical['close'].iloc[-1]
            trend = (current - ma20) / ma20
            return trend

        elif factor_name == 'value':
            # 价格分位 (252 日)
            lookback = min(252, len(historical))
            recent_prices = historical['close'].iloc[-lookback:]
            current = historical['close'].iloc[-1]
            percentile = (recent_prices < current).mean()
            return 1.0 - percentile  # 低估值高分数

        elif factor_name == 'flow':
            # 成交量趋势 (20 日 vs 前 20 日)
            if 'volume' in historical.columns and len(historical) >= 40:
                recent_vol = historical['volume'].iloc[-20:].mean()
                prev_vol = historical['volume'].iloc[-40:-20].mean()
                flow = (recent_vol - prev_vol) / prev_vol if prev_vol > 0 else 0
                return flow
            return 0.5

        elif factor_name == 'relative_strength':
            # 相对强弱 (简化版：20 日收益率)
            if len(historical) >= 21:
                returns = historical['close'].pct_change()
                rs = returns.iloc[-20:].sum()
                return rs
            return 0.5

        else:
            logger.warning(f"Unknown factor: {factor_name}")
            return 0.5

    def calc_ic(self, factor_name: str, start_date: str, end_date: str) -> ICResult:
        """
        计算因子 IC 指标

        IC (Information Coefficient): 因子值与下期收益的相关性
        - IC > 0: 因子有效 (因子值越大，收益越高)
        - IC < 0: 因子反向有效
        - IC ≈ 0: 因子无效

        评判标准:
        - |IC| > 0.05: 较强因子
        - |IC| > 0.10: 强因子
        - IC IR > 0.5: 稳定性好
        """
        data = self.prepare_factor_data(factor_name, start_date, end_date)

        if data.empty:
            return ICResult(
                factor_name=factor_name,
                ic_mean=0, ic_std=0, ic_ir=0, t_stat=0, p_value=0,
                ic_count=0, positive_ratio=0
            )

        # 按日期分组计算 IC
        ic_series = []
        dates = data['date'].unique()

        for date in dates:
            day_data = data[data['date'] == date]
            if len(day_data) < 5:  # 至少 5 个样本
                continue

            factor_vals = day_data['factor_value']
            next_rets = day_data['next_return']

            # 计算 IC (Pearson 相关系数)
            if factor_vals.std() > 1e-10 and next_rets.std() > 1e-10:
                ic = factor_vals.corr(next_rets)
                if not np.isnan(ic):
                    ic_series.append({'date': date, 'ic': ic})

        ic_df = pd.DataFrame(ic_series).set_index('date')

        if ic_df.empty:
            return ICResult(
                factor_name=factor_name,
                ic_mean=0, ic_std=0, ic_ir=0, t_stat=0, p_value=0,
                ic_count=0, positive_ratio=0
            )

        ic_mean = ic_df['ic'].mean()
        ic_std = ic_df['ic'].std()
        ic_ir = ic_mean / ic_std if ic_std > 0 else 0
        t_stat = ic_mean / (ic_std / np.sqrt(len(ic_df))) if ic_std > 0 else 0
        # 简化 p 值计算 (t 分布)
        p_value = 2 * (1 - min(0.9999, abs(t_stat) / 3.5))  # 近似

        return ICResult(
            factor_name=factor_name,
            ic_mean=ic_mean,
            ic_std=ic_std,
            ic_ir=ic_ir,
            t_stat=t_stat,
            p_value=p_value,
            ic_count=len(ic_df),
            positive_ratio=(ic_df['ic'] > 0).mean(),
            ic_time_series=ic_df['ic']
        )

    def calc_quantile_returns(self, factor_name: str, start_date: str, end_date: str,
                              quantiles: int = 5) -> QuantileResult:
        """
        因子分层回测

        将标的按因子值分为 N 组，追踪每组收益表现
        - 预期：因子值最高组收益 > 因子值最低组收益
        - 多空收益 = 第 1 组收益 - 第 N 组收益
        """
        data = self.prepare_factor_data(factor_name, start_date, end_date)

        if data.empty:
            return QuantileResult(
                factor_name=factor_name,
                quantiles=quantiles,
                returns={},
                cumulative_returns={},
                final_returns={},
                sharpe_ratios={}
            )

        dates = sorted(data['date'].unique())
        quantile_returns = {q: [] for q in range(1, quantiles + 1)}
        quantile_dates = {q: [] for q in range(1, quantiles + 1)}

        # 每日调仓
        for date in dates:
            day_data = data[data['date'] == date].copy()
            if len(day_data) < quantiles:
                continue

            # 按因子值分组
            day_data['quantile'] = pd.qcut(day_data['factor_value'], q=quantiles, labels=False, duplicates='drop')
            day_data['quantile'] = day_data['quantile'] + 1  # 1-indexed

            # 计算每组平均下期收益
            for q in range(1, quantiles + 1):
                q_data = day_data[day_data['quantile'] == q]
                if not q_data.empty:
                    avg_return = q_data['next_return'].mean()
                    quantile_returns[q].append(avg_return)
                    quantile_dates[q].append(date)

        # 构建收益序列
        returns_dict = {}
        cumulative_dict = {}
        final_dict = {}
        sharpe_dict = {}

        for q in range(1, quantiles + 1):
            if quantile_returns[q]:
                ret_series = pd.Series(quantile_returns[q], index=quantile_dates[q])
                returns_dict[q] = ret_series
                cumulative_dict[q] = (1 + ret_series).cumprod()
                final_dict[q] = cumulative_dict[q].iloc[-1] - 1 if len(cumulative_dict[q]) > 0 else 0

                # 年化夏普比率
                if len(ret_series) > 10:
                    sharpe_dict[q] = ret_series.mean() / ret_series.std() * np.sqrt(252)
                else:
                    sharpe_dict[q] = 0
            else:
                returns_dict[q] = pd.Series()
                cumulative_dict[q] = pd.Series()
                final_dict[q] = 0
                sharpe_dict[q] = 0

        return QuantileResult(
            factor_name=factor_name,
            quantiles=quantiles,
            returns=returns_dict,
            cumulative_returns=cumulative_dict,
            final_returns=final_dict,
            sharpe_ratios=sharpe_dict
        )

    def rolling_ic_analysis(self, factor_name: str, start_date: str, end_date: str,
                            window_days: int = 63) -> pd.DataFrame:
        """
        滚动窗口 IC 分析 - 观察因子稳定性

        Args:
            window_days: 滚动窗口天数 (默认 63 天，约 1 季度)

        Returns:
            DataFrame with rolling IC metrics
        """
        data = self.prepare_factor_data(factor_name, start_date, end_date)

        if data.empty:
            return pd.DataFrame()

        # 按日期计算每日 IC
        daily_ic = []
        dates = sorted(data['date'].unique())

        for date in dates:
            day_data = data[data['date'] == date]
            if len(day_data) < 5:
                continue

            factor_vals = day_data['factor_value']
            next_rets = day_data['next_return']

            if factor_vals.std() > 1e-10 and next_rets.std() > 1e-10:
                ic = factor_vals.corr(next_rets)
                if not np.isnan(ic):
                    daily_ic.append({'date': date, 'ic': ic})

        ic_df = pd.DataFrame(daily_ic).set_index('date')

        if ic_df.empty:
            return pd.DataFrame()

        # 滚动统计
        ic_df['rolling_ic_mean'] = ic_df['ic'].rolling(window=window_days, min_periods=20).mean()
        ic_df['rolling_ic_std'] = ic_df['ic'].rolling(window=window_days, min_periods=20).std()
        ic_df['rolling_ic_ir'] = ic_df['rolling_ic_mean'] / ic_df['rolling_ic_std']

        return ic_df

    def analyze_all_factors(self, start_date: str, end_date: str,
                            factors: Optional[List[str]] = None) -> Dict[str, ICResult]:
        """
        分析所有因子的 IC 指标

        Returns:
            {factor_name: ICResult}
        """
        if factors is None:
            factors = ['momentum', 'volatility', 'trend', 'value', 'flow', 'relative_strength']

        results = {}
        for factor in factors:
            logger.info(f"Analyzing factor: {factor}")
            ic_result = self.calc_ic(factor, start_date, end_date)
            results[factor] = ic_result

            # 打印摘要
            print(f"  {factor}: IC={ic_result.ic_mean:.4f}, IR={ic_result.ic_ir:.2f}, "
                  f"t-stat={ic_result.t_stat:.2f}, p-value={ic_result.p_value:.4f}")

        return results

    def generate_factor_report(self, start_date: str, end_date: str,
                               factors: Optional[List[str]] = None) -> dict:
        """
        生成完整的因子分析报告

        Returns:
            dict with IC results, quantile analysis, recommendations
        """
        if factors is None:
            factors = ['momentum', 'volatility', 'trend', 'value', 'flow', 'relative_strength']

        report = {
            'period': f"{start_date} ~ {end_date}",
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ic_analysis': {},
            'quantile_analysis': {},
            'recommendations': []
        }

        # IC 分析
        print("\n=== IC 分析 ===")
        for factor in factors:
            ic_result = self.calc_ic(factor, start_date, end_date)
            report['ic_analysis'][factor] = {
                'ic_mean': ic_result.ic_mean,
                'ic_std': ic_result.ic_std,
                'ic_ir': ic_result.ic_ir,
                't_stat': ic_result.t_stat,
                'p_value': ic_result.p_value,
                'positive_ratio': ic_result.positive_ratio
            }

        # 分层回测
        print("\n=== 分层回测 (5 组) ===")
        for factor in factors:
            quant_result = self.calc_quantile_returns(factor, start_date, end_date, quantiles=5)
            report['quantile_analysis'][factor] = {
                'final_returns': quant_result.final_returns,
                'sharpe_ratios': quant_result.sharpe_ratios,
                'long_short_return': quant_result.final_returns.get(1, 0) - quant_result.final_returns.get(5, 0),
                'long_short_sharpe': quant_result.sharpe_ratios.get(1, 0) - quant_result.sharpe_ratios.get(5, 0)
            }

            q_ret = quant_result.final_returns
            print(f"  {factor}: Q1={q_ret.get(1, 0):.2%}, Q5={q_ret.get(5, 0):.2%}, "
                  f"Q1-Q5={q_ret.get(1, 0) - q_ret.get(5, 0):.2%}")

        # 生成推荐
        report['recommendations'] = self._generate_recommendations(report)

        print("\n=== 推荐 ===")
        for rec in report['recommendations']:
            print(f"  - {rec}")

        return report

    def _generate_recommendations(self, report: dict) -> List[str]:
        """基于分析结果生成因子权重调整推荐"""
        recommendations = []

        for factor, ic_data in report['ic_analysis'].items():
            # 强因子推荐
            if abs(ic_data['ic_mean']) > 0.05 and ic_data['ic_ir'] > 0.5:
                recommendations.append(
                    f"↑ {factor}: 强因子 (IC={ic_data['ic_mean']:.3f}, IR={ic_data['ic_ir']:.2f}), "
                    f"建议提升权重"
                )
            # 弱因子警告
            elif abs(ic_data['ic_mean']) < 0.02:
                recommendations.append(
                    f"↓ {factor}: 弱因子 (IC={ic_data['ic_mean']:.3f}), 建议降低权重或移除"
                )
            # 不稳定因子
            if ic_data['ic_ir'] < 0.3:
                recommendations.append(
                    f"⚠ {factor}: IC 不稳定 (IR={ic_data['ic_ir']:.2f}), 需谨慎使用"
                )

        # 基于分层回测的推荐
        for factor, q_data in report['quantile_analysis'].items():
            ls_return = q_data.get('long_short_return', 0)
            if ls_return > 0.02:  # 多空收益 > 2%
                recommendations.append(
                    f"✓ {factor}: 多空收益优秀 ({ls_return:.1%}), 因子区分度好"
                )
            elif ls_return < -0.01:  # 负向多空收益
                recommendations.append(
                    f"✗ {factor}: 多空收益为负 ({ls_return:.1%}), 考虑反向使用"
                )

        return recommendations


def run_factor_analysis(fetcher, config: dict, start_date: str = "20250101",
                        end_date: str = "20260331"):
    """运行完整的因子分析"""
    analyzer = FactorAnalyzer(fetcher, config)

    print("=" * 70)
    print(f"因子分析报告")
    print(f"期间：{start_date} ~ {end_date}")
    print("=" * 70)

    report = analyzer.generate_factor_report(start_date, end_date)

    return report


if __name__ == "__main__":
    import logging
    from src.data_fetcher_baostock import IndexDataFetcher
    from src.config_loader import load_app_config
    from pathlib import Path

    logging.basicConfig(level=logging.INFO)

    config = load_app_config(Path(__file__).parent.parent)
    fetcher = IndexDataFetcher()

    try:
        report = run_factor_analysis(fetcher, config, "20250101", "20260331")
    finally:
        fetcher.close()
