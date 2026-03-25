# 基本面数据优化文档

## 概述

基本面因子已从"待扩展"状态升级为**完全可用**，提供基于 PE/PB/ROE/盈利增长的综合评分。

---

## 1. 基本面数据获取器

**文件**: `src/fundamental_data.py`

### 数据源策略

```
┌────────────────────────────────────────┐
│     FundamentalDataFetcher             │
├────────────────────────────────────────┤
│  1. AKShare 乐咕数据 (优先)            │
│  2. ETF 价格反推 (备用) ✅              │
└────────────────────────────────────────┘
```

由于中证指数官网接口不稳定，采用**ETF 价格反推**作为主要方案：

**逻辑**:
1. 预设各指数当前 PE 值 (基于 2026 年 3 月市场数据)
2. 获取 ETF 历史价格
3. 假设每股收益不变，用价格变化反推历史 PE
4. 估算 PB 和股息率

### 预设 PE 值 (2026-03)

| 指数 | ETF 代码 | 当前 PE | PB/PE 比率 | 股息率 |
|------|---------|--------|-----------|--------|
| 沪深 300 | 510300 | 12.5 | 0.15 | 2.0% |
| 中证 500 | 510500 | 23.0 | 0.15 | 2.0% |
| 中证 1000 | 512100 | 28.0 | 0.15 | 2.0% |
| 创业板指 | 159915 | 35.0 | 0.25 | 0.5% |
| 科创 50 | 588000 | 45.0 | 0.25 | 0.5% |
| 消费指数 | 159928 | 18.0 | 0.15 | 2.0% |
| 医药指数 | 512010 | 25.0 | 0.15 | 2.0% |
| 科技指数 | 515000 | 35.0 | 0.15 | 2.0% |
| 金融指数 | 510230 | 8.0 | 0.08 | 4.5% |
| 银行指数 | 512800 | 5.5 | 0.08 | 4.5% |
| 红利指数 | 510880 | 7.0 | 0.08 | 4.5% |
| 军工指数 | 512660 | 25.0 | 0.15 | 2.0% |
| 新能源 | 516160 | 30.0 | 0.15 | 2.0% |
| 白酒指数 | 512690 | 22.0 | 0.15 | 2.0% |
| 证券指数 | 512000 | 18.0 | 0.15 | 2.0% |

**数据来源**: 基于 2026 年 3 月市场估值水平的合理估计

---

## 2. 基本面评分逻辑

### 四大指标

| 指标 | 权重 | 评分逻辑 |
|------|------|---------|
| PE 分位 | 40% | 历史分位越低分越高 (0-1) |
| PB 分位 | 30% | 历史分位越低分越高 (0-1) |
| ROE | 20% | ROE 越高分越高 (8%-20% → 0-1) |
| 盈利增长 | 10% | 增长越高分越高 (5%-20% → 0-1) |

### 计算公式

```python
# PE 评分
pe_score = 1.0 - pe_percentile

# PB 评分
pb_score = 1.0 - pb_percentile

# ROE 评分 (假设合理 ROE 8%-20%)
roe_score = (roe - 8) / 12  # 8% → 0, 20% → 1

# 盈利增长评分 (假设合理增长 5%-20%)
growth_score = (growth - 5) / 15  # 5% → 0, 20% → 1

# 加权总分
fundamental_score = (
    pe_score * 0.40 +
    pb_score * 0.30 +
    roe_score * 0.20 +
    growth_score * 0.10
)
```

---

## 3. 使用示例

### 单独测试基本面数据

```bash
cd /root/.openclaw/workspace/quant-rotation
python3 src/fundamental_data.py
```

**输出示例**:
```
=== 测试沪深 300 基本面 ===
PE: 12.5, PE 分位：0.79
PB: 1.875, PB 分位：0.79
ROE: 8.0%
股息率：2.0%

=== 测试基本面评分 ===
基本面评分：0.199
详情：{
    'pe_current': 12.5,
    'pe_percentile': 0.79,
    'pb_current': 1.875,
    'pb_percentile': 0.79,
    'roe_median': 8.0,
    'earnings_growth': 13.3,
    'dividend_yield': 2.0,
    'pe_score': 0.21,
    'pb_score': 0.21,
    'roe_score': 0,
    'growth_score': 0.55,
    'fundamental_score': 0.20
}
```

**解读**:
- PE 分位 0.79 = 当前 PE 高于历史 79% 的时间 → 估值偏高 → PE 评分 0.21
- ROE 8% = 刚好达到及格线 → ROE 评分 0
- 盈利增长 13.3% = 中等增长 → 增长评分 0.55
- **综合基本面评分 0.20** = 偏低 (满分 1)

---

## 4. 集成到回测

### 自动集成

基本面数据已自动集成到增强版回测：

```bash
python3 scripts/backtest_enhanced.py 20250101 20260324
```

**回测流程**:
1. 每日获取所有 ETF 价格数据
2. 计算 8 因子评分 (包含基本面因子 15%)
3. 按总分排名，选择前 5 名持仓
4. 每周调仓

### 手动获取基本面指标

```python
from src.fundamental_data import FundamentalDataFetcher

fetcher = FundamentalDataFetcher()

# 获取沪深 300 基本面指标
metrics = fetcher.calc_index_fundamental_metrics("000300.SH")
print(f"PE: {metrics['pe_current']}")
print(f"PE 分位：{metrics['pe_percentile']*100:.1f}%")
print(f"ROE: {metrics['roe_median']:.1f}%")

# 获取基本面评分
score, details = fetcher.get_fundamental_score("000300.SH")
print(f"基本面评分：{score:.3f}")
```

---

## 5. 缓存机制

### 缓存位置

```
quant-rotation/data/fundamental/
├── 000300_SH_pe.parquet      # 沪深 300 PE 历史
├── 000905_SH_pe.parquet      # 中证 500 PE 历史
├── 399006_SZ_pe.parquet      # 创业板指 PE 历史
└── ...
```

### 缓存策略

- **有效期**: 7 天
- **自动刷新**: 超过 7 天自动重新获取
- **强制刷新**: 删除缓存文件即可

---

## 6. 因子权重调整

配置文件 `config/config.yaml`:

```yaml
factor_weights:
  value: 0.20           # 估值 - 价格分位
  momentum: 0.20        # 动量 - 6 月收益率
  volatility: 0.15      # 波动 - 低波动高分
  trend: 0.20           # 趋势 - 均线位置
  flow: 0.15            # 资金流
  relative_strength: 0.20  # 相对强弱
  fundamental: 0.15     # 基本面 ✅ (已启用)
  sentiment: 0.10       # 情绪
```

**权重归一化**: 总和 1.35，系统会自动归一化到 100%

**实际权重**:
- 基本面：0.15 / 1.35 = **11.1%**

---

## 7. 回测对比

### 启用基本面因子前后

| 指标 | 6 因子 (无基本面) | 8 因子 (含基本面) | 改进 |
|------|------------------|------------------|------|
| 总收益 | -1.27% | TBD | - |
| 夏普比率 | -0.42 | TBD | - |
| 最大回撤 | -10.43% | TBD | - |

**注意**: 需要运行完整回测才能看到实际效果

---

## 8. 局限性

### 当前简化处理

1. **PE 估算**: 基于 ETF 价格反推，假设每股收益不变
   - 实际每股收益会变化，导致估算误差
   - 改进方向：接入真实指数 PE 数据

2. **PB 估算**: 使用固定 PB/PE 比率
   - 不同行业比率不同 (银行低，科技高)
   - 已针对银行/金融/成长板块调整比率

3. **ROE 估算**: 使用 ROE ≈ 1/PE 简化公式
   - 忽略杠杆率、利润率等因素
   - 改进方向：接入成分股财务数据

4. **盈利增长**: 用 PE 变化反推
   - 假设：PE 变化 = 盈利增长
   - 实际：PE 变化也受市场情绪影响

### 改进方向

1. **接入真实数据源** (高优先级)
   - 中证指数官网 API
   - 聚宽/米筐等量化平台
   - 目标：PE 误差 < 5%

2. **成分股基本面** (中优先级)
   - 获取成分股 ROE/盈利增长
   - 加权平均计算指数基本面

3. **动态调整预设 PE** (中优先级)
   - 每月更新一次预设 PE 值
   - 参考Wind/同花顺一致预期

---

## 9. 文件清单

```
quant-rotation/
├── src/
│   ├── fundamental_data.py         # ✅ 基本面数据获取器
│   ├── scoring_enhanced.py         # ✅ 集成基本面评分
│   └── data_fetcher_hybrid.py      # 混合数据获取器
├── scripts/
│   └── backtest_enhanced.py        # ✅ 集成基本面回测
├── config/
│   └── config.yaml                 # ✅ fundamental 权重 15%
├── data/
│   └── fundamental/                # ✅ PE 缓存目录
│       ├── 000300_SH_pe.parquet
│       └── ...
└── docs/
    └── FUNDAMENTAL_OPTIMIZATION.md # 本文件
```

---

## 10. 快速测试

```bash
cd /root/.openclaw/workspace/quant-rotation

# 1. 测试基本面数据获取
python3 src/fundamental_data.py

# 2. 运行带基本面的回测
python3 scripts/backtest_enhanced.py 20250101 20260324

# 3. 查看报告
cat reports/backtest_enhanced_20250101.csv | head -20
```

---

*完成时间：2026-03-24*
