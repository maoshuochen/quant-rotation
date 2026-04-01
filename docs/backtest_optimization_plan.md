# 回测优化与 GitHub 自动化计划

## 一、回测脚本优化分析

### 当前性能瓶颈

1. **数据获取串行化**
   - 每个 ETF 单独请求，未并行化
   - 无增量更新机制，每次都全量获取

2. **计算效率低**
   - 评分计算在循环内重复执行
   - 因子计算未使用向量化

3. **I/O 开销大**
   - 日志输出过于频繁
   - 结果保存无压缩

### 优化方案

#### 1. 数据获取优化

```python
# 并行获取 ETF 数据
from concurrent.futures import ThreadPoolExecutor

def fetch_all_etfs_parallel(etf_list, date_range):
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(fetch_single_etf, etf_list)
    return dict(results)

# 增量更新 - 仅获取新增数据
def fetch_incremental_data(etf_code, last_cached_date):
    if last_cached_date:
        start_date = (last_cached_date + timedelta(days=1)).strftime('%Y%m%d')
    else:
        start_date = default_start
    return fetcher.fetch_etf_history(etf_code, start_date)
```

#### 2. 计算优化

```python
# 向量化评分计算
def batch_score_indices(etf_data_dict, scoring_date, benchmark):
    """批量评分，使用向量化操作"""
    all_data = pd.concat(etf_data_dict.values(), axis=1, keys=etf_data_dict.keys())

    # 向量化计算动量
    momentum = all_data['close'].pct_change(126)

    # 向量化计算波动率
    returns = all_data['close'].pct_change()
    volatility = returns.rolling(20).std() * np.sqrt(252)

    return scores_df

# 缓存中间计算结果
@lru_cache(maxsize=100)
def cached_factor_calc(code, date_tuple, window):
    """缓存因子计算结果"""
    pass
```

#### 3. 存储优化

```python
# 使用 Parquet 格式存储
values_df.to_parquet(
    result_file.with_suffix('.parquet'),
    compression='snappy',
    index=False
)

# 增量保存 - 每日追加
def append_daily_result(date, value, file_path):
    existing = pd.read_parquet(file_path)
    new_row = pd.DataFrame([{'date': date, 'value': value}])
    pd.concat([existing, new_row]).to_parquet(file_path)
```

---

## 二、GitHub 自动化回测方案

### 架构设计

```
┌─────────────────────────────────────────────────────┐
│              GitHub Actions Scheduler                │
│                  (每天 9:00 UTC)                     │
├─────────────────────────────────────────────────────┤
│  1. 拉取最新代码                                      │
│  2. 安装依赖                                        │
│  3. 运行当日回测 (增量)                              │
│  4. 更新前端数据                                     │
│  5. 提交回测结果到 gh-pages 分支                       │
│  6. 发送 Telegram 通知 (可选)                          │
└─────────────────────────────────────────────────────┘
                          ↓
        ┌─────────────────┴─────────────────┐
        │                                   │
        ↓                                   ↓
┌───────────────┐                   ┌───────────────┐
│  gh-pages 分支 │                   │  Telegram 通知  │
│  - 净值数据    │                   │  - 当日收益    │
│  - 持仓报告    │                   │  - 调仓信号    │
│  - 排名数据    │                   │  - 风险指标    │
└───────────────┘                   └───────────────┘
```

### GitHub Actions 配置

```yaml
name: Daily Backtest

on:
  schedule:
    # 每天 UTC 0 点运行 (北京时间 8 点)
    - cron: '0 0 * * *'
  workflow_dispatch:  # 支持手动触发

jobs:
  backtest:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run daily backtest
        run: |
          python scripts/backtest_baostock.py

      - name: Generate web data
        run: |
          python scripts/generate_web_data.py

      - name: Commit results
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./backtest_results
          destination_dir: data
          commit_message: 'chore: daily backtest update [skip ci]'
```

### 增量回测脚本

```python
#!/usr/bin/env python3
"""
增量回测脚本 - 仅计算新增交易日
"""
import os
from pathlib import Path

def get_last_trading_date(results_file: Path) -> Optional[str]:
    """从已有结果中获取最后一个交易日"""
    if results_file.exists():
        df = pd.read_parquet(results_file)
        return df['date'].iloc[-1]
    return None

def run_incremental_backtest():
    """增量回测主函数"""
    results_file = Path('backtest_results/current.parquet')

    # 获取最后交易日
    last_date = get_last_trading_date(results_file)

    if last_date:
        # 计算到今天的数据
        today = datetime.now().strftime('%Y%m%d')
        start_from = (pd.to_datetime(last_date) + timedelta(days=1)).strftime('%Y%m%d')
        print(f"增量回测：{start_from} ~ {today}")
    else:
        # 全量回测
        start_from = config.get('backtest_start_date', '20240101')
        today = datetime.now().strftime('%Y%m%d')
        print(f"全量回测：{start_from} ~ {today}")

    run_backtest(start_from, today)
```

---

## 三、预计优化效果

| 指标 | 当前 | 优化后 | 提升 |
|------|------|--------|------|
| 数据获取时间 | ~60s | ~15s | 4x |
| 评分计算时间 | ~30s | ~5s | 6x |
| 总回测时间 | ~90s | ~20s | 4.5x |
| 存储空间 | CSV 10MB | Parquet 3MB | 3x |

---

## 四、实施清单

- [ ] 优化数据获取 (并行 + 增量)
- [ ] 向量化评分计算
- [ ] 改用 Parquet 存储
- [ ] 创建增量回测脚本
- [ ] 添加 GitHub Actions 调度器
- [ ] 配置 Telegram 通知
- [ ] 设置 gh-pages 自动部署
