#!/usr/bin/env python3
"""
生成回测统计 JSON 供前端使用
优先使用 current.parquet，如果没有则使用最新的 CSV 文件
"""
import pandas as pd
import json
from pathlib import Path

root_dir = Path(__file__).parent.parent
results_dir = root_dir / 'backtest_results'
outputs_dir = root_dir / 'outputs' / 'frontend'
outputs_dir.mkdir(parents=True, exist_ok=True)

# 优先使用 current.parquet
parquet_file = results_dir / 'current.parquet'
if parquet_file.exists():
    print(f"读取回测结果：{parquet_file}")
    df = pd.read_parquet(parquet_file)
    df = df.copy()
else:
    # 回退到 CSV
    csv_files = list(results_dir.glob('backtest_*.csv'))
    if not csv_files:
        print("没有找到回测结果文件")
        exit(1)

    latest_file = max(csv_files, key=lambda f: f.stat().st_mtime)
    print(f"读取回测结果：{latest_file}")
    df = pd.read_csv(latest_file)
    df['date'] = pd.to_datetime(df['date'])

# 确保必要字段存在
if 'drawdown' not in df.columns:
    df['rolling_max'] = df['value'].cummax()
    df['drawdown'] = (df['value'] - df['rolling_max']) / df['rolling_max']

if 'return' not in df.columns:
    df['return'] = df['value'].pct_change()

if 'cum_return' not in df.columns:
    df['cum_return'] = (df['value'] / df['value'].iloc[0]) - 1

# 计算关键统计
initial_capital = df['value'].iloc[0]
final_value = df['value'].iloc[-1]
total_return = (final_value - initial_capital) / initial_capital

# 年化收益
days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
years = days / 365
annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return

# 最大回撤
max_drawdown = df['drawdown'].min()
max_drawdown_date = df.loc[df['drawdown'].idxmin(), 'date']

# 夏普比率
daily_returns = df['return'].dropna()
sharpe = daily_returns.mean() / daily_returns.std() * (252 ** 0.5) if len(daily_returns) > 20 else 0

# 准备图表数据
chart_data = []
for _, row in df.iterrows():
    chart_data.append({
        'date': row['date'].strftime('%Y-%m-%d'),
        'value': round(row['value'], 2),
        'cum_return': round(row['cum_return'], 4) if pd.notna(row['cum_return']) else 0,
        'drawdown': round(row['drawdown'], 4) if pd.notna(row['drawdown']) else 0
    })

# 构建输出
output = {
    'summary': {
        'initial_capital': initial_capital,
        'final_value': round(final_value, 2),
        'total_return': round(total_return, 4),
        'annual_return': round(annual_return, 4),
        'max_drawdown': round(max_drawdown, 4),
        'max_drawdown_date': max_drawdown_date.strftime('%Y-%m-%d') if pd.notna(max_drawdown_date) else '',
        'sharpe_ratio': round(sharpe, 2),
        'trading_days': len(df),
        'period': {
            'start': df['date'].iloc[0].strftime('%Y-%m-%d'),
            'end': df['date'].iloc[-1].strftime('%Y-%m-%d')
        }
    },
    'chart_data': chart_data
}

# 保存到 backtest_results/latest.json
latest_output = results_dir / 'latest.json'
with open(latest_output, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

# 保存到 outputs/frontend 与 web/dist
outputs_file = outputs_dir / 'backtest.json'
with open(outputs_file, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

output_file = root_dir / 'web' / 'dist' / 'backtest.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"回测数据已保存：{output_file}")
print(f"回测数据已保存：{outputs_file}")
print(f"回测数据已保存：{latest_output}")
print(f"\n📊 回测摘要:")
print(f"  总收益率：{total_return*100:.2f}%")
print(f"  年化收益：{annual_return*100:.2f}%")
print(f"  最大回撤：{max_drawdown*100:.2f}%")
print(f"  夏普比率：{sharpe:.2f}")
