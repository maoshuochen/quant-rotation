# 指数轮动量化系统 - 项目总览

## 项目状态

✅ **MVP 完成** (2026-03-17)

- [x] 数据源切换至 Baostock
- [x] 因子评分系统
- [x] 策略回测
- [x] Web 仪表盘

## 项目结构

```
quant-rotation/
├── config/
│   └── config.yaml           # 策略配置
├── src/
│   ├── data_fetcher.py       # 原数据获取器 (AKShare)
│   ├── data_fetcher_baostock.py  # Baostock 数据获取器 ✅
│   ├── factor_engine.py      # 因子计算
│   ├── scoring.py            # 原评分系统
│   ├── scoring_baostock.py   # Baostock 评分系统 ✅
│   ├── strategy.py           # 原策略逻辑
│   ├── strategy_baostock.py  # Baostock 策略逻辑 ✅
│   ├── portfolio.py          # 模拟账户
│   └── notifier.py           # 通知模块
├── scripts/
│   ├── daily_run.py          # 原每日运行
│   ├── daily_run_baostock.py # Baostock 每日运行 ✅
│   ├── backtest.py           # 原回测脚本
│   ├── backtest_baostock.py  # Baostock 回测 ✅
│   ├── export_ranking_json.py # 导出数据到前端 ✅
│   └── fetch_all_data.py     # 数据获取
├── web/                      # Web 仪表盘 ✅
│   ├── src/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── public/
│   │   └── ranking.json      # 排名数据
│   └── package.json
├── data/
│   └── raw/                  # 缓存数据
├── logs/                     # 日志
├── backtest_results/         # 回测结果
├── README.md                 # 项目说明
├── BAOSTOCK_MIGRATION.md     # 迁移指南
├── QUICKSTART.md             # 快速开始
└── PROJECT_SUMMARY.md        # 本文档
```

## 核心功能

### 1. 数据获取 (Baostock)

```python
from src.data_fetcher_baostock import IndexDataFetcher

fetcher = IndexDataFetcher()

# 获取 ETF 历史数据
df = fetcher.fetch_etf_history("510300", "20250101")

# 获取指数历史数据 (返回空，需用 ETF 替代)
df = fetcher.fetch_index_history("000300.SH", "20250101")
```

### 2. 因子评分

5 个核心因子：

| 因子 | 权重 | 说明 |
|------|------|------|
| 动量 | 20% | 6 个月收益率 |
| 波动 | 15% | 年化波动率 (低波高分) |
| 趋势 | 20% | 价格相对 MA20/MA60 |
| 估值 | 25% | 价格历史分位 |
| 相对强弱 | 20% | 相对沪深 300 |

### 3. 策略逻辑

```
每周一 → 获取数据 → 计算因子 → 综合评分 → 排名
  ↓
选前 5 名 → 等权重配置
  ↓
跌出前 8 名 → 卖出
```

### 4. 回测

```bash
python3 scripts/backtest_baostock.py 20250101 20260317
```

**结果** (2025-01-01 ~ 2026-03-17):
- 总收益：-2.68%
- 最大回撤：-3.95%
- 夏普比率：-1.48
- 调仓次数：9 次

### 5. Web 仪表盘

```bash
cd web
npm run dev
# 访问 http://localhost:3000
```

功能：
- 指数排名表格
- 因子雷达图
- 因子贡献度条形图
- 计算逻辑说明

## 快速开始

### 运行策略

```bash
cd /root/.openclaw/workspace/quant-rotation
python3 scripts/daily_run_baostock.py
```

### 更新前端数据

```bash
python3 scripts/export_ranking_json.py
```

### 查看回测

```bash
python3 scripts/backtest_baostock.py 20250101
```

## 配置 Cron

```bash
crontab -e

# 每周一 9:00 运行策略
0 9 * * 1 cd /root/.openclaw/workspace/quant-rotation && python3 scripts/daily_run_baostock.py >> logs/cron.log 2>&1

# 每天 9:00 更新前端数据
0 9 * * 2-6 cd /root/.openclaw/workspace/quant-rotation && python3 scripts/export_ranking_json.py
```

## 监控指数

| 代码 | 名称 | ETF | 数据状态 |
|------|------|-----|---------|
| 000300.SH | 沪深 300 | 510300 | ✅ |
| 000905.SH | 中证 500 | 510500 | ✅ |
| 000852.SH | 中证 1000 | 512100 | ✅ |
| 399006.SZ | 创业板指 | 159915 | ❌ (深市) |
| 000688.SH | 科创 50 | 588000 | ✅ |
| 000932.CSI | 消费指数 | 159928 | ❌ (深市) |
| 000933.CSI | 医药指数 | 512010 | ✅ |
| 000993.CSI | 科技指数 | 515000 | ✅ |

**可用**: 6/8 (75%)

## 下一步优化

- [ ] 添加更多沪市 ETF (扩大选择范围)
- [ ] 优化因子计算 (增加基本面因子)
- [ ] 动态权重调整
- [ ] 可视化报告 (净值曲线、持仓饼图)
- [ ] 实盘接口 (谨慎)
- [ ] 深市 ETF 数据补充 (AKShare 混合)

## 相关文档

- [README.md](README.md) - 项目说明
- [BAOSTOCK_MIGRATION.md](BAOSTOCK_MIGRATION.md) - 数据源迁移指南
- [QUICKSTART.md](QUICKSTART.md) - 快速开始
- [web/README.md](web/README.md) - Web 仪表盘文档

---

最后更新：2026-03-17
