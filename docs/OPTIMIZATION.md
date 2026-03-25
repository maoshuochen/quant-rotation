# 量化回测框架优化文档

## 优化概述

本次优化聚焦于**数据源扩展**和**因子体系增强**两大方向。

---

## 1. 数据源扩展 ✅

### 问题
- 原 Baostock 仅支持沪市 ETF (51xxxx/58xxxx)
- 深市 ETF (15xxxx/16xxxx) 数据缺失，如：
  - 创业板指 ETF (159915)
  - 消费指数 ETF (159928)
  - 恒生指数 ETF (159920)

### 解决方案：混合数据获取器

**文件**: `src/data_fetcher_hybrid.py`

```
┌─────────────────────────────────────┐
│     HybridDataFetcher               │
├─────────────────────────────────────┤
│  沪市 ETF (51/56/58) → Baostock     │
│  深市 ETF (15/16)    → AKShare Sina │
│  北向资金           → AKShare 东方财富 │
│  ETF 份额            → AKShare 上交所/深交所│
└─────────────────────────────────────┘
```

### 核心功能

| 功能 | 数据源 | 支持市场 |
|------|--------|---------|
| ETF 历史行情 | Baostock + AKShare Sina | 沪市 + 深市 |
| 北向资金 | AKShare 东方财富 | 全市场 |
| ETF 份额变化 | AKShare 上交所/深交所 | 沪市 + 深市 |
| 资金流指标 | 计算得出 | 全市场 |

### 使用示例

```python
from src.data_fetcher_hybrid import HybridDataFetcher

fetcher = HybridDataFetcher()

# 沪市 ETF (自动使用 Baostock)
df_sh = fetcher.fetch_etf_history("510300", "20250101")

# 深市 ETF (自动使用 AKShare)
df_sz = fetcher.fetch_etf_history("159915", "20250101")

# 北向资金
df_nb = fetcher.fetch_northbound_flow("20250101")
nb_metrics = fetcher.calc_northbound_metrics(df_nb)

# ETF 份额
df_shares = fetcher.fetch_etf_shares("510300", "20250101")
shares_metrics = fetcher.calc_etf_shares_metrics(df_shares)
```

### 新增 ETF 标的

配置文件中扩展至 **20 只 ETF** (8 宽基 + 12 行业)：

**宽基 (8 只)**:
- 沪深 300 (510300) ✅
- 中证 500 (510500) ✅
- 中证 1000 (512100) ✅
- **创业板指 (159915) ✅ [新增]**
- 科创 50 (588000) ✅
- **消费指数 (159928) ✅ [新增]**
- 医药指数 (512010) ✅
- 科技指数 (515000) ✅

**行业 (12 只)**:
- 金融 (510230)、制造 (516880)、周期 (512340)、红利 (510880)
- 军工 (512660)、新能源 (516160)、半导体 (512480)、白酒 (512690)
- 银行 (512800)、证券 (512000)、**煤炭 (515220) [新增]**、**恒生 (159920) [新增]**

---

## 2. 因子体系增强 ✅

### 问题
- 原 6 因子体系缺少基本面和情绪维度
- 估值因子用价格分位替代 PE，精度不足
- 无市场情绪监测

### 解决方案：增强评分引擎

**文件**: `src/scoring_enhanced.py`

### 新因子体系 (8 因子)

```
┌──────────────────────────────────────────────────────┐
│              增强因子体系 (总分 100%)                 │
├──────────────────────────────────────────────────────┤
│  动量 (20%)     │ 6 个月收益率，1 个月动量辅助          │
│  波动 (15%)     │ 年化波动率，低波动高分               │
│  趋势 (20%)     │ 价格相对 MA20/MA60 位置              │
│  估值 (20%)     │ 价格历史分位 (简化 PE)               │
│  资金流 (15%)   │ 成交量/金额趋势 + 北向资金 + ETF 份额  │
│  相对强弱 (20%) │ 相对沪深 300 超额收益                │
│  基本面 (10%)   │ ROE/盈利增长 [待扩展]                │
│  情绪 (10%)     │ ETF 份额变化/成交量异常/动量加速      │
└──────────────────────────────────────────────────────┘
```

**注意**: 因子权重总和超过 100%，系统会自动归一化。

### 新增因子详解

#### 1. 基本面因子 (10%)

**当前实现**: 简化处理 (返回中性分数 0.5)

**规划扩展**:
```python
# 未来可接入的数据
- 指数 PE/PB 分位 (中证指数官网)
- 成分股 ROE 中位数
- 盈利增长率
- 现金流指标
```

**使用建议**: 当前权重较低 (10%)，不影响整体评分，待数据源完善后可提高权重。

#### 2. 情绪因子 (10%)

**三大指标**:

| 指标 | 权重 | 计算逻辑 |
|------|------|---------|
| ETF 份额变化 | 40% | 20 日份额变化率 (±20% → 0~1 分) |
| 成交量异常 | 30% | 成交量 Z-Score (±3σ → 0~1 分) |
| 动量加速 | 30% | 近 20 日动量 vs 前 20 日动量 |

**解读**:
- 份额增长 + 放量 + 动量加速 = 情绪高涨 (高分)
- 份额缩减 + 缩量 + 动量减速 = 情绪低迷 (低分)

### 增强归因系统

每次评分输出详细归因数据：

```python
scores = engine.score_index(etf_data)
attribution = scores['attribution']

# 示例输出
{
    'momentum_6m': 12.5,          # 6 个月收益率%
    'momentum_1m': 3.2,           # 1 个月收益率%
    'volatility_annual': 18.7,    # 年化波动率%
    'price_vs_ma20': 2.3,         # 相对 MA20 位置%
    'price_vs_ma60': 5.1,         # 相对 MA60 位置%
    'ma20_above_ma60': True,      # 金叉状态
    'value_percentile': 35.2,     # 价格分位%
    'value_assessment': '合理',    # 估值评估
    'volume_change_pct': 15.3,    # 成交量变化%
    'price_volume_corr': 0.42,    # 量价相关系数
    'northbound_20d_sum': 125.6,  # 北向资金 20 日净流入 (亿元)
    'etf_shares_change_20d': 5.2, # ETF 份额 20 日变化%
    'excess_return': 3.8,         # 相对基准超额收益%
    'best_factor': 'trend',       # 最强因子
    'worst_factor': 'value'       # 最弱因子
}
```

---

## 3. 回测框架升级

### 新回测脚本

**文件**: `scripts/backtest_enhanced.py`

### 功能特性

- ✅ 支持混合数据源 (沪市 + 深市 ETF)
- ✅ 8 因子评分体系
- ✅ 交易成本建模 (手续费 + 滑点)
- ✅ 周/月调仓频率可选
- ✅ 详细归因输出
- ✅ 自动保存交易记录和权益曲线

### 使用方法

```bash
cd /root/.openclaw/workspace/quant-rotation

# 回测 2025 年至今
python3 scripts/backtest_enhanced.py 20250101

# 回测指定区间
python3 scripts/backtest_enhanced.py 20250101 20260324
```

### 输出报告

**权益曲线**: `reports/backtest_enhanced_<start_date>.csv`
**交易记录**: `reports/trades_enhanced_<start_date>.csv`

**报告指标**:
- 总收益率 / 年化收益
- 最大回撤
- 夏普比率
- 交易次数 / 交易成本
- 调仓频率

---

## 4. 配置文件更新

**文件**: `config/config.yaml`

### 主要变更

1. **ETF 列表扩展**: 18 只 → 20 只
2. **新增 market 字段**: 明确标注每只 ETF 的市场 (sh/sz)
3. **因子权重调整**:
   - 估值：25% → 20% (为基本面/情绪因子腾出空间)
   - 新增：fundamental (10%), sentiment (10%)

---

## 5. 下一步优化建议

### 高优先级

1. **基本面数据接入**
   - 爬取中证指数官网 PE/PB 数据
   - 接入 AKShare 指数基本面接口
   - 目标：基本面因子权重提升至 15%

2. **交易成本优化**
   - 添加印花税 (卖出时收取)
   - 考虑冲击成本 (大额交易)
   - 目标：成本建模误差 < 5%

3. **可视化报告**
   - 权益曲线图
   - 回撤分布图
   - 持仓热力图
   - 因子贡献分解

### 中优先级

4. **动态权重调整**
   - 牛市：加重动量/趋势因子
   - 熊市：加重低波/估值因子
   - 使用市场状态识别模型

5. **参数优化框架**
   - 网格搜索最优 top_n/buffer_n
   - Walk-Forward 分析避免过拟合
   - 蒙特卡洛模拟压力测试

6. **实时数据推送**
   - 每日评分推送至 Telegram
   - 调仓提醒
   - 异常波动预警

---

## 6. 文件清单

```
quant-rotation/
├── src/
│   ├── data_fetcher_hybrid.py      # [新增] 混合数据获取器
│   ├── scoring_enhanced.py         # [新增] 增强评分引擎
│   ├── data_fetcher_baostock.py    # 保留 (向后兼容)
│   └── scoring_baostock.py         # 保留 (向后兼容)
├── scripts/
│   ├── backtest_enhanced.py        # [新增] 增强版回测
│   ├── daily_run_baostock.py       # 保留
│   └── backtest_baostock.py        # 保留
├── config/
│   └── config.yaml                 # [已更新] 配置扩展
├── reports/                        # [新增] 回测报告目录
│   ├── backtest_enhanced_*.csv
│   └── trades_enhanced_*.csv
└── docs/
    └── OPTIMIZATION.md             # [本文件]
```

---

## 7. 测试验证

### 单元测试

```bash
# 测试混合数据获取器
python3 src/data_fetcher_hybrid.py

# 预期输出:
# === 测试沪市 ETF (510300) ===
# 510300: XXX rows
# === 测试深市 ETF (159915) ===
# 159915: XXX rows  ← 关键：深市 ETF 有数据
# === 测试北向资金 ===
# 北向资金：XXX rows
```

### 回测对比

运行新旧两版回测，对比结果：

```bash
# 旧版 (Baostock 仅沪市)
python3 scripts/backtest_baostock.py 20250101

# 新版 (混合数据源 + 增强因子)
python3 scripts/backtest_enhanced.py 20250101
```

**预期改进**:
- 可选 ETF 数量：15 只 → 20 只 (+33%)
- 夏普比率提升：目标 +0.2~0.5
- 最大回撤降低：目标 -1%~-3%

---

*最后更新：2026-03-24*
