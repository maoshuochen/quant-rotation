# Baostock 数据源迁移指南

## 概述

量化轮动系统已从 AKShare/Tushare 迁移到 **Baostock** 数据源。

## 主要变更

### 1. 数据获取方式

**之前**: 使用指数代码直接获取指数数据
**现在**: 使用 ETF 数据替代指数数据（Baostock 不支持指数数据）

### 2. 新文件

```
src/
├── data_fetcher_baostock.py   # Baostock 数据获取器
├── scoring_baostock.py        # 评分系统 (适配 ETF 数据)
└── strategy_baostock.py       # 策略主逻辑

scripts/
├── daily_run_baostock.py      # 每日运行脚本
└── backtest_baostock.py       # 回测脚本
```

### 3. 数据覆盖

| 指数 | ETF 代码 | 数据状态 |
|------|---------|---------|
| 沪深 300 | 510300 | ✅ 有数据 |
| 中证 500 | 510500 | ✅ 有数据 |
| 中证 1000 | 512100 | ✅ 有数据 |
| 创业板指 | 159915 | ❌ 无数据 (深市 ETF) |
| 科创 50 | 588000 | ✅ 有数据 |
| 消费指数 | 159928 | ❌ 无数据 (深市 ETF) |
| 医药指数 | 512010 | ✅ 有数据 |
| 科技指数 | 515000 | ✅ 有数据 |

**注意**: Baostock 主要支持沪市 ETF (sh.)，深市 ETF (sz.) 数据可能缺失。

## 使用方法

### 每日运行

```bash
cd /root/.openclaw/workspace/quant-rotation
python3 scripts/daily_run_baostock.py
```

### 回测

```bash
# 回测 2025 年至今
python3 scripts/backtest_baostock.py 20250101

# 回测指定区间
python3 scripts/backtest_baostock.py 20250101 20260317
```

### 刷新数据缓存

```bash
python3 src/data_fetcher_baostock.py
```

## 评分因子 (简化版)

由于使用 ETF 数据而非指数数据，部分因子简化处理：

| 因子 | 权重 | 计算方式 |
|------|------|---------|
| 动量 | 20% | 6 个月收益率 |
| 波动 | 15% | 年化波动率 (低波高分) |
| 趋势 | 20% | 价格相对 MA20/MA60 位置 |
| 估值 | 25% | 价格历史分位 (替代 PE 分位) |
| 相对强弱 | 20% | 相对沪深 300 的强度 |

## 配置调整

如需修改策略参数，编辑 `config/config.yaml`:

```yaml
strategy:
  top_n: 5              # 选前 5 名
  buffer_n: 8           # 跌出前 8 卖出
  rebalance_frequency: "weekly"  # weekly / monthly

factor_weights:
  value: 0.25
  momentum: 0.20
  volatility: 0.15
  # ... 其他因子
```

## 回测结果示例

```
📊 回测结果 (2025-01-01 ~ 2026-03-17)
  初始资金：1,000,000
  最终价值：973,156
  总收益率：-2.68%
  年化收益：-13.23%
  最大回撤：-3.95%
  夏普比率：-1.48
  交易天数：45
  调仓次数：9
```

**注意**: 回测期间较短 (仅 45 天)，结果仅供参考。

## 下一步优化

- [ ] 添加更多沪市 ETF (扩大可选范围)
- [ ] 优化因子计算 (增加基本面因子)
- [ ] 动态权重调整
- [ ] 添加交易成本分析
- [ ] 生成可视化报告

## 常见问题

### Q: 为什么有些 ETF 没有数据？
A: Baostock 主要支持沪市 ETF，深市 ETF 数据可能缺失。可以考虑：
   - 使用沪市 ETF 替代品
   - 混合使用 AKShare 获取深市数据

### Q: 估值因子准确吗？
A: 当前使用价格分位替代 PE 分位，是简化处理。如需准确估值数据，建议：
   - 手动导入指数 PE 数据
   - 或使用其他数据源补充

### Q: 如何添加新 ETF？
A: 在 `config/config.yaml` 的 `indices` 列表中添加：

```yaml
indices:
  - code: "000001.SH"
    name: "上证指数"
    etf: "510210"  # 对应 ETF 代码
```

---

最后更新：2026-03-17
