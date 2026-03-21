#!/usr/bin/env python3
"""
生成回测统计 JSON 供前端使用
"""
import pandas as pd
import json
from pathlib import Path

root_dir = Path(__file__).parent.parent
results_dir = root_dir / 'backtest_results'

# 读取最新的回测结果
csv_files = list(results_dir.glob('backtest_*.csv'))
if not csv_files:
    print("没有找到回测结果文件")
    exit(1)

latest_file = max(csv_files, key=lambda f: f.stat().st_mtime)
print(f"读取回测结果：{latest_file}")

df = pd.read_csv(latest_file)
df['date'] = pd.to_datetime(df['date'])

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

# 保存到 web/dist 目录
output_file = root_dir / 'web' / 'dist' / 'backtest.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"回测数据已保存：{output_file}")
print(f"\n📊 回测摘要:")
print(f"  总收益率：{total_return*100:.2f}%")
print(f"  年化收益：{annual_return*100:.2f}%")
print(f"  最大回撤：{max_drawdown*100:.2f}%")
print(f"  夏普比率：{sharpe:.2f}")
