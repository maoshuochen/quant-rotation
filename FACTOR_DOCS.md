# 因子文档 - 详细说明

## 因子体系总览

| 维度 | 权重 | 方向 | 说明 |
|------|------|------|------|
| 估值 (Value) | 25% | 越低越好 | PE/PB 历史分位 |
| 动量 (Momentum) | 20% | 越高越好 | 6 月收益率 |
| 趋势 (Trend) | 20% | 越高越好 | 价格在均线上方 |
| 资金流 (Flow) | 15% | 越高越好 | 成交量/金额趋势 |
| 相对强弱 (RS) | 20% | 越高越好 | 相对沪深 300 |

---

## 资金流因子 (Flow Factor) 🔥

### 核心逻辑

资金流因子衡量**资金流入/流出**的强度和方向，通过以下子指标综合计算：

### 基础指标 (60%)

### 1. 成交量趋势 (Volume Trend) - 权重 15%

```python
# 计算最近 20 日 vs 前 20 日的成交量变化
recent_vol = 近 20 日成交量均值
prev_vol = 前 20 日成交量均值
vol_change = (recent_vol - prev_vol) / prev_vol

# 归一化到 0-1
vol_score = 0.5 + vol_change  # 假设 -50% ~ +50% 范围
```

**含义**：
- `vol_change > 0`：成交量放大，资金关注度提升
- `vol_change < 0`：成交量萎缩，资金关注度下降

---

### 2. 量价配合 (Price-Volume Correlation) - 权重 15%

```python
# 计算价格收益率与成交量收益率的相关性
price_returns = 价格日收益率序列
vol_returns = 成交量日收益率序列
corr = correlation(price_returns, vol_returns)

# 归一化：-1~1 -> 0~1
corr_score = 0.5 + corr * 0.5
```

**含义**：
- `corr > 0`：价涨量增、价跌量缩（健康）
- `corr < 0`：价涨量缩、价跌量增（背离，警惕）

**理想状态**：正相关性，表示资金流向与价格走势一致

---

### 3. 成交金额趋势 (Amount Trend) - 权重 15%

```python
# 类似成交量，但用成交金额（更准确反映资金规模）
recent_amt = 近 20 日成交金额均值
prev_amt = 前 20 日成交金额均值
amt_change = (recent_amt - prev_amt) / prev_amt

amt_score = 0.5 + amt_change
```

**为什么用金额**：
- 成交量受价格影响（高价股成交量天然小）
- 成交金额直接反映资金规模

---

### 4. 资金流入强度 (Flow Intensity) - 权重 15%

---

### 北向资金指标 (20%)

通过 AKShare 获取沪深股通北向资金数据，计算以下指标：

```python
# 1. 净买入趋势 (近 20 日总和)
net_flow_20d_sum = 近 20 日北向净买入总和 (亿元)
# 归一化：-50 亿 ~ +50 亿 -> 0~1
nb_net_score = 0.5 + net_flow_20d_sum / 100

# 2. 买入天数占比
buy_ratio = 净买入>0 的天数 / 总天数

# 3. 资金趋势 (近 10 日 vs 前 10 日)
trend = (近期净买入 - 前期净买入) / |前期净买入|
```

**含义**：
- `net_flow_20d_sum > 0`：外资净流入
- `buy_ratio > 0.6`：多数时间为买入
- `trend > 0`：资金流入加速

---

### ETF 份额指标 (20%)

通过 AKShare 获取 ETF 真实份额数据，计算以下指标：

```python
# 1. 20 日份额变化
shares_change_20d = (当前份额 - 20 日前份额) / 20 日前份额
# 归一化：-20% ~ +20% -> 0~1
etf_20d_score = 0.5 + shares_change_20d / 0.4

# 2. 5 日份额变化 (短期)
shares_change_5d = 近 5 日份额变化

# 3. 流入天数占比
inflow_days_ratio = 份额增长天数 / 总天数
```

**含义**：
- `shares_change_20d > 0`：份额增长，资金申购
- `shares_change_20d < 0`：份额萎缩，资金赎回
- `inflow_days_ratio > 0.6`：多数时间为净申购

```python
# 计算近 20 日中，成交量高于中位数的天数占比
vol_median = 近 60 日成交量中位数
high_vol_days = 近 20 日中 volume > vol_median 的天数
flow_intensity = high_vol_days / 20
```

**含义**：
- `flow_intensity > 0.5`：近期放量天数多于缩量天数
- `flow_intensity < 0.5`：近期缩量为主

---

### 资金流得分计算

```python
flow_score = (
    # 基础指标 (60%)
    vol_score * 0.15 +          # 成交量趋势
    corr_score * 0.15 +         # 量价配合
    amt_score * 0.15 +          # 成交金额趋势
    flow_intensity * 0.15 +     # 资金流入强度
    
    # 北向资金 (20%)
    nb_score * 0.20 +           # 北向资金综合评分
    
    # ETF 份额 (20%)
    etf_score * 0.20            # ETF 份额综合评分
)
```

**得分解读**：
- `> 0.7`：资金大幅流入，强烈看好
- `0.5-0.7`：资金温和流入
- `0.3-0.5`：资金流出或观望
- `< 0.3`：资金大幅流出，警惕

---

## 其他因子简述

### 估值因子 (Value, 25%)

用价格历史分位代替 PE/PB（简化版）：
```python
percentile = (近 252 日价格 < 当前价格) 的比例
value_score = 1 - percentile
```

### 动量因子 (Momentum, 20%)

6 个月累计收益率：
```python
momentum_6m = 近 126 日收益率之和
momentum_score = 0.5 + momentum_6m  # 归一化
```

### 趋势因子 (Trend, 20%)

价格在均线上方得分：
```python
score = 0.5
if price > MA20: score += 0.25
if price > MA60: score += 0.25
```

### 相对强弱 (RS, 20%)

相对于沪深 300 的表现：
```python
ratio = ETF 价格 / 沪深 300 价格
rs_60d = ratio 当前值 / ratio 60 日前值
rs_score = 0.5 + (rs_60d - 1) * 2
```

---

## 扩展计划

### ✅ 已完成 (2026-03-21)

- [x] 北向资金因子集成
- [x] ETF 份额变化因子集成
- [x] 增强版资金流评分

### 待实现

#### 主力资金流因子 (需要 Level-2 数据)

```python
# 大单净流入
large_order_net_inflow = 大单买入 - 大单卖出
main_force_score = normalize(large_order_net_inflow)
```

#### 行业资金轮动

```python
# 各行业 ETF 资金流对比
industry_flow_rank = rank(industry_etf_flow_scores)
```

---

## 文件位置

- 数据获取：`src/data_fetcher_baostock.py`
  - `fetch_northbound_flow()` - 北向资金
  - `fetch_etf_shares()` - ETF 份额
  - `fetch_money_flow()` - 资金流指标
  
- 评分计算：`src/scoring_baostock.py`
  - `calc_flow_score()` - 资金流评分

- 配置：`config/config.yaml`
  - `factor_weights` - 各因子权重

---

*最后更新：2026-03-21*
