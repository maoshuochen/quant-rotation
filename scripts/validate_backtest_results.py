#!/usr/bin/env python3
"""
回测数据验证脚本
验证回测结果数据的完整性和合理性
"""
import pandas as pd
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
results_dir = root_dir / 'backtest_results'


def validate_backtest_data(df: pd.DataFrame) -> tuple:
    """
    验证回测数据

    Returns:
        (is_valid, errors, warnings)
    """
    errors = []
    warnings = []

    # 1. 基本检查
    if df.empty:
        errors.append("回测数据为空")
        return False, errors, warnings

    if 'date' not in df.columns or 'value' not in df.columns:
        errors.append("缺少必要字段 (date, value)")
        return False, errors, warnings

    # 2. 日期连续性检查
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # 3. 计算每日收益率
    df['daily_return'] = df['value'].pct_change()

    # 4. 检查初始资金
    initial_capital = df['value'].iloc[0]
    if initial_capital <= 0:
        errors.append(f"初始资金异常：{initial_capital:,.2f}")

    # 5. 检查最终价值
    final_value = df['value'].iloc[-1]
    if final_value <= 0:
        errors.append(f"最终价值异常：{final_value:,.2f}")

    # 6. 检查单日涨跌幅（阈值 20%）
    abnormal_dates = df[df['daily_return'].abs() > 0.20]
    for _, row in abnormal_dates.iterrows():
        if pd.notna(row['daily_return']):
            warnings.append(
                f"单日涨跌幅超过 20%: {row['date'].strftime('%Y-%m-%d')} "
                f"({row['daily_return']*100:+.2f}%)")

    # 7. 检查单日涨跌幅（阈值 50% - 严重错误）
    critical_dates = df[df['daily_return'].abs() > 0.50]
    for _, row in critical_dates.iterrows():
        if pd.notna(row['daily_return']):
            errors.append(
                f"严重异常：单日涨跌幅超过 50%: {row['date'].strftime('%Y-%m-%d')} "
                f"({row['daily_return']*100:+.2f}%)")

    # 8. 检查最大回撤
    df['rolling_max'] = df['value'].cummax()
    df['drawdown'] = (df['value'] - df['rolling_max']) / df['rolling_max']
    max_drawdown = df['drawdown'].min()

    if max_drawdown < -0.50:
        warnings.append(f"最大回撤超过 50%: {max_drawdown*100:.2f}%")

    # 9. 检查收益率合理性
    total_return = (final_value - initial_capital) / initial_capital

    # 年化收益率检查（假设 252 个交易日）
    trading_days = len(df)
    years = trading_days / 252
    if years > 0:
        annual_return = (1 + total_return) ** (1 / years) - 1
        if annual_return > 2.0:  # 年化超过 200%
            warnings.append(f"年化收益率异常：{annual_return*100:.2f}%")
        elif annual_return < -0.8:  # 年化亏损超过 80%
            warnings.append(f"年化收益率异常：{annual_return*100:.2f}%")

    # 10. 检查数据完整性（不应该有重复日期）
    if df['date'].duplicated().any():
        errors.append("存在重复日期")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def main():
    """主函数"""
    print("=" * 60)
    print("回测数据验证")
    print("=" * 60)

    # 查找最新的回测结果
    parquet_file = results_dir / 'current.parquet'
    csv_file = None

    if not parquet_file.exists():
        # 查找最新 CSV
        csv_files = list(results_dir.glob('backtest_*.csv'))
        if csv_files:
            csv_file = max(csv_files, key=lambda f: f.stat().st_mtime)
            print(f"使用 CSV 文件：{csv_file}")
        else:
            print("❌ 未找到回测结果文件")
            sys.exit(1)
    else:
        print(f"使用 Parquet 文件：{parquet_file}")

    # 读取数据
    if parquet_file.exists():
        df = pd.read_parquet(parquet_file)
    else:
        df = pd.read_csv(csv_file)

    print(f"数据范围：{df['date'].iloc[0]} 至 {df['date'].iloc[-1]}")
    print(f"交易日数：{len(df)}")
    print()

    # 验证
    is_valid, errors, warnings = validate_backtest_data(df)

    # 输出结果
    if errors:
        print("❌ 错误:")
        for err in errors:
            print(f"   - {err}")

    if warnings:
        print("⚠️ 警告:")
        for warn in warnings:
            print(f"   - {warn}")

    if is_valid:
        print("✅ 验证通过：回测数据正常")

        # 输出摘要
        initial = df['value'].iloc[0]
        final = df['value'].iloc[-1]
        total_return = (final - initial) / initial

        df['rolling_max'] = df['value'].cummax()
        df['drawdown'] = (df['value'] - df['rolling_max']) / df['rolling_max']
        max_dd = df['drawdown'].min()

        print()
        print("📊 回测摘要:")
        print(f"   初始资金：{initial:,.2f}")
        print(f"   最终价值：{final:,.2f}")
        print(f"   总收益率：{total_return*100:.2f}%")
        print(f"   最大回撤：{max_dd*100:.2f}%")
    else:
        print()
        print("❌ 验证失败：回测数据存在问题，请检查")
        sys.exit(1)

    return 0 if is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
