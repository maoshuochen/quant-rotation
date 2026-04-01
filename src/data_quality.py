"""
数据质量检查器
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """
    数据质量检查器

    功能:
    - 缺失值检测
    - 异常值检测
    - 连续性检查
    - 数据一致性检查
    """

    def __init__(self,
                 max_missing_ratio: float = 0.1,
                 outlier_std: float = 5.0,
                 max_gap_days: int = 7):
        """
        Args:
            max_missing_ratio: 最大缺失比例
            outlier_std: 异常值标准差倍数
            max_gap_days: 最大允许间隔天数
        """
        self.max_missing_ratio = max_missing_ratio
        self.outlier_std = outlier_std
        self.max_gap_days = max_gap_days

    def check_missing_values(self, df: pd.DataFrame) -> Dict:
        """检查缺失值"""
        missing_info = {}

        for col in df.columns:
            missing_count = df[col].isna().sum()
            missing_ratio = missing_count / len(df) if len(df) > 0 else 0

            missing_info[col] = {
                'missing_count': int(missing_count),
                'missing_ratio': float(missing_ratio),
                'is_ok': missing_ratio <= self.max_missing_ratio
            }

        overall_ok = all(v['is_ok'] for v in missing_info.values())

        return {
            'column_info': missing_info,
            'overall_ok': overall_ok,
            'total_rows': len(df)
        }

    def check_outliers(self,
                       df: pd.DataFrame,
                       columns: List[str] = None) -> Dict:
        """检查异常值"""
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        outlier_info = {}

        for col in columns:
            if col not in df.columns:
                continue

            values = df[col].dropna()
            if len(values) < 10:
                continue

            mean = values.mean()
            std = values.std()

            if std == 0:
                continue

            z_scores = np.abs((values - mean) / std)
            outliers = values[z_scores > self.outlier_std]

            outlier_info[col] = {
                'outlier_count': len(outliers),
                'outlier_ratio': len(outliers) / len(values),
                'outlier_values': outliers.tolist()[:10],  # 最多显示 10 个
                'mean': float(mean),
                'std': float(std)
            }

        return outlier_info

    def check_continuity(self,
                         df: pd.DataFrame,
                         date_column: str = None) -> Dict:
        """检查时间序列连续性"""
        if df.empty:
            return {'is_continuous': True, 'gaps': []}

        if date_column:
            dates = pd.to_datetime(df[date_column]).sort_values()
        elif isinstance(df.index, pd.DatetimeIndex):
            dates = df.index.sort_values()
        else:
            return {'is_continuous': True, 'gaps': [], 'message': 'No datetime found'}

        if len(dates) < 2:
            return {'is_continuous': True, 'gaps': []}

        # 计算日期间隔
        date_diffs = dates.to_series().diff()
        gaps = date_diffs[date_diffs > pd.Timedelta(days=self.max_gap_days)]

        gap_info = []
        for idx in gaps.index:
            prev_idx = dates.get_loc(idx) - 1
            if prev_idx >= 0:
                gap_info.append({
                    'from': dates[prev_idx].strftime('%Y-%m-%d'),
                    'to': idx.strftime('%Y-%m-%d'),
                    'gap_days': int((idx - dates[prev_idx]).days)
                })

        return {
            'is_continuous': len(gaps) == 0,
            'gaps': gap_info[:20],  # 最多显示 20 个
            'total_gaps': len(gaps),
            'date_range': {
                'start': dates.min().strftime('%Y-%m-%d'),
                'end': dates.max().strftime('%Y-%m-%d')
            }
        }

    def check_price_consistency(self, df: pd.DataFrame) -> Dict:
        """检查价格数据一致性"""
        issues = []

        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                issues.append(f'Missing column: {col}')

        if issues:
            return {'is_consistent': False, 'issues': issues}

        # 检查 high >= low
        invalid_hl = df[df['high'] < df['low']]
        if not invalid_hl.empty:
            issues.append(f"high < low on {len(invalid_hl)} days")

        # 检查 close 在 high-low 范围内
        invalid_close = df[(df['close'] > df['high']) | (df['close'] < df['low'])]
        if not invalid_close.empty:
            issues.append(f"close out of range on {len(invalid_close)} days")

        # 检查成交量/金额为负
        if 'volume' in df.columns:
            neg_vol = df[df['volume'] < 0]
            if not neg_vol.empty:
                issues.append(f"negative volume on {len(neg_vol)} days")

        if 'amount' in df.columns:
            neg_amt = df[df['amount'] < 0]
            if not neg_amt.empty:
                issues.append(f"negative amount on {len(neg_amt)} days")

        return {
            'is_consistent': len(issues) == 0,
            'issues': issues
        }

    def check_returns(self, df: pd.DataFrame) -> Dict:
        """检查收益率异常"""
        if 'close' not in df.columns or len(df) < 2:
            return {'is_normal': True, 'issues': []}

        returns = df['close'].pct_change().dropna()

        issues = []

        # 检查极端收益率
        extreme_returns = returns[returns.abs() > 0.5]  # 单日涨跌超 50%
        if not extreme_returns.empty:
            issues.append({
                'type': 'extreme_return',
                'count': len(extreme_returns),
                'dates': extreme_returns.head(10).index.strftime('%Y-%m-%d').tolist()
            })

        # 检查连续涨停/跌停
        if len(returns) > 10:
            # 连续 5 日涨跌停
            limit_up = (returns > 0.095).rolling(5).sum() == 5
            limit_down = (returns < -0.095).rolling(5).sum() == 5

            if limit_up.any():
                issues.append({'type': 'consecutive_limit_up', 'count': int(limit_up.sum())})
            if limit_down.any():
                issues.append({'type': 'consecutive_limit_down', 'count': int(limit_down.sum())})

        return {
            'is_normal': len(issues) == 0,
            'issues': issues,
            'return_stats': {
                'mean': float(returns.mean()),
                'std': float(returns.std()),
                'skew': float(returns.skew()),
                'kurtosis': float(returns.kurtosis())
            }
        }

    def full_check(self,
                   df: pd.DataFrame,
                   check_types: List[str] = None) -> Dict:
        """
        完整数据质量检查

        Args:
            df: 待检查的 DataFrame
            check_types: 检查类型列表，None 表示全部检查

        Returns:
            检查结果字典
        """
        if check_types is None:
            check_types = ['missing', 'outliers', 'continuity', 'price', 'returns']

        results = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'checks': {}
        }

        if 'missing' in check_types:
            results['checks']['missing_values'] = self.check_missing_values(df)

        if 'outliers' in check_types:
            results['checks']['outliers'] = self.check_outliers(df)

        if 'continuity' in check_types:
            results['checks']['continuity'] = self.check_continuity(df)

        if 'price' in check_types:
            results['checks']['price_consistency'] = self.check_price_consistency(df)

        if 'returns' in check_types:
            results['checks']['returns'] = self.check_returns(df)

        # 总体评估
        all_ok = True
        for check_name, check_result in results['checks'].items():
            if isinstance(check_result, dict):
                if 'is_ok' in check_result and not check_result['is_ok']:
                    all_ok = False
                elif 'is_consistent' in check_result and not check_result['is_consistent']:
                    all_ok = False
                elif 'is_normal' in check_result and not check_result['is_normal']:
                    all_ok = False

        results['overall_quality'] = 'PASS' if all_ok else 'NEEDS_REVIEW'

        return results


def create_quality_checker(
        max_missing_ratio: float = 0.1,
        outlier_std: float = 5.0,
        max_gap_days: int = 7) -> DataQualityChecker:
    """创建数据质量检查器"""
    return DataQualityChecker(max_missing_ratio, outlier_std, max_gap_days)
