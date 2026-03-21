# 前端资金流因子详情功能

**更新日期**: 2026-03-21

---

## 新增功能

### 1. 资金流因子展开详情

在「因子」标签页，当选中某个指数后，可以看到**资金流因子详解**模块。

**展开方式**: 点击「展开 ▼」按钮

---

## 子因子得分

显示资金流因子的 6 个子因子得分：

| 子因子 | 说明 |
|--------|------|
| 成交量趋势 | 近 20 日 vs 前 20 日成交量变化 |
| 量价配合 | 价格与成交量相关性 |
| 金额趋势 | 成交金额变化趋势 |
| 流入强度 | 放量天数占比 |
| 北向资金 | 沪深股通净买入趋势 |
| ETF 份额 | 基金份额申购/赎回 |

---

## 权重分布图

饼图展示资金流因子的权重分配：

- **基础指标 60%** (蓝色)
  - 成交量趋势 15%
  - 量价配合 15%
  - 金额趋势 15%
  - 流入强度 15%

- **北向资金 20%** (绿色)
  - 净买入趋势
  - 买入天数占比
  - 资金流向

- **ETF 份额 20%** (紫色)
  - 份额变化
  - 流入天数占比

---

## 北向资金指标

显示 4 个关键指标：

| 指标 | 说明 | 单位 |
|------|------|------|
| 20 日净买入 | 近 20 日北向资金净买入总和 | 亿元 |
| 5 日均值 | 近 5 日日均净买入 | 亿元 |
| 买入占比 | 净买入>0 的天数占比 | % |
| 趋势 | 近期 vs 前期资金流向对比 | - |

**颜色标识**:
- 🟢 绿色：正值 (流入)
- 🔴 红色：负值 (流出)

---

## ETF 份额指标

显示 4 个关键指标：

| 指标 | 说明 | 单位 |
|------|------|------|
| 20 日变化 | 近 20 日份额变化 | % |
| 5 日变化 | 近 5 日份额变化 | % |
| 流入占比 | 份额增长天数占比 | % |
| 趋势 | 份额变化趋势 | % |

**颜色标识**:
- 🟢 绿色：份额增长 (申购)
- 🔴 红色：份额减少 (赎回)

---

## 数据来源

### 实时数据
- **北向资金**: AKShare 东方财富 API
- **ETF 份额**: AKShare 东方财富 API

### 更新频率
- 每个交易日更新

---

## 技术实现

### 前端文件
- `web/src/App.jsx` - 主应用组件
  - 新增 `showFlowDetail` 状态
  - 新增资金流详情 UI
  - 新增北向资金/ETF 份额指标卡片

### 数据生成
- `scripts/generate_web_data.py` - 生成前端数据
  - 调用 `fetch_northbound_flow()` 获取北向资金
  - 调用 `fetch_etf_shares()` 获取 ETF 份额
  - 计算并保存 `flow_details` 对象

### 数据格式

```json
{
  "ranking": [...],
  "factor_weights": {...},
  "flow_details": {
    "000300.SH": {
      "volume_trend": 0.75,
      "price_volume_corr": 0.60,
      "amount_trend": 0.80,
      "flow_intensity": 0.55,
      "northbound": 0.65,
      "northbound_metrics": {
        "net_flow_20d_sum": 150.5,
        "net_flow_5d_avg": 12.3,
        "buy_ratio": 0.70,
        "trend": 0.25
      },
      "etf_shares": 0.70,
      "etf_shares_metrics": {
        "shares_change_20d": 0.08,
        "shares_change_5d": 0.02,
        "inflow_days_ratio": 0.65,
        "trend": 0.05
      }
    }
  }
}
```

---

## 使用方法

### 1. 生成数据

```bash
cd /root/.openclaw/workspace/quant-rotation
python3 scripts/generate_web_data.py
```

### 2. 构建前端

```bash
cd web
npm run build
```

### 3. 启动服务

```bash
npm run preview
# 或部署到服务器
```

### 4. 访问页面

打开浏览器访问 `http://localhost:4173`

---

## 降级处理

### 数据缺失时

如果北向资金或 ETF 份额数据获取失败：

1. **自动降级**: 使用基础指标代理 (0.5 分)
2. **显示占位符**: 显示 "-" 或默认值
3. **不影响主评分**: 资金流因子仍然正常计算

### 错误处理

```javascript
// 前端安全获取数据
const flowDetail = data.flowDetails?.[selectedCode] || {}
const nbMetrics = flowDetail.northbound_metrics || {}
const value = nbMetrics[metric.key]
const displayValue = value !== undefined ? value.toFixed(2) : '-'
```

---

## 视觉效果

### 卡片布局
- 桌面端：2-4 列网格
- 移动端：2 列网格

### 颜色方案
- 背景：`bg-zinc-900` / `bg-black/50`
- 边框：`border-zinc-800`
- 文字：`text-gray-500` / `text-white`
- 正值：`text-emerald-400`
- 负值：`text-red-400`

### 图表
- **饼图**: Recharts PieChart
- **颜色**: 蓝色/绿色/紫色区分

---

## 下一步优化

1. **实时刷新**: 交易时间内自动刷新数据
2. **历史趋势**: 显示北向资金/ETF 份额历史曲线
3. **资金流预警**: 异常波动时高亮显示
4. **多 ETF 对比**: 同时显示多个 ETF 的资金流

---

*文档更新时间：2026-03-21*
