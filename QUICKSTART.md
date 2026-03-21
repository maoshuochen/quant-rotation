# 快速开始 - 量化轮动系统

## 1. 运行每日策略

```bash
cd /root/.openclaw/workspace/quant-rotation
python3 scripts/daily_run_baostock.py
```

**输出示例**:
```
📊 指数排名:
  1. 000933.CSI: 0.7353
  2. 000300.SH: 0.7168
  3. 000688.SH: 0.7006
  
💰 组合总值：998,765.96
📈 持仓数：5
```

## 2. 运行回测

```bash
# 回测 2025 年至今
python3 scripts/backtest_baostock.py 20250101

# 回测指定区间
python3 scripts/backtest_baostock.py 20250101 20260317
```

**输出示例**:
```
📊 回测结果
  初始资金：1,000,000
  最终价值：973,156
  总收益率：-2.68%
  最大回撤：-3.95%
  夏普比率：-1.48
```

## 3. 刷新数据

```bash
# 手动刷新所有 ETF 数据
python3 src/data_fetcher_baostock.py
```

## 4. 配置 Cron (自动运行)

```bash
crontab -e

# 每周一 9:00 运行策略
0 9 * * 1 cd /root/.openclaw/workspace/quant-rotation && python3 scripts/daily_run_baostock.py >> logs/cron.log 2>&1
```

## 5. 查看日志

```bash
# 查看今日日志
tail -f logs/strategy_$(date +%Y%m%d).log

# 查看所有日志
ls -la logs/
```

## 6. 调整参数

编辑 `config/config.yaml`:

```yaml
strategy:
  top_n: 5        # 选前 5 名
  buffer_n: 8     # 跌出前 8 卖出
  
factor_weights:
  momentum: 0.20  # 动量权重
  value: 0.25     # 估值权重
  # ...
```

## 7. 查看结果文件

```bash
# 回测结果
ls -la backtest_results/

# 数据缓存
ls -la data/raw/
```

---

**更多信息**: 参见 `README.md` 和 `BAOSTOCK_MIGRATION.md`
