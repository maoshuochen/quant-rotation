# 指数轮动量化系统 (Quant Rotation System)

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Data](https://img.shields.io/badge/Data-Baostock%2FAKShare-orange.svg)](https://akshare.akfamily.xyz/)

基于多因子评分的指数轮动量化交易系统，支持 A 股主要宽基指数和行业指数的自动评分、排名和交易信号生成。

---

## 📊 策略特点

### 核心功能
- **6 大因子体系**: 估值 (25%) + 动量 (20%) + 趋势 (20%) + 波动 (15%) + 资金流 (15%) + 相对强弱 (20%)
- **自动评分排名**: 每日对 6 大指数进行综合评分
- **交易信号生成**: 基于排名生成买入/卖出信号
- **模拟回测**: 支持历史回测和绩效分析
- **实时看板**: React 前端可视化展示

### 资金流因子（增强版）
- **基础指标 (60%)**: 成交量趋势、量价配合、金额趋势、流入强度
- **北向资金 (20%)**: 沪深股通净买入趋势
- **ETF 份额 (20%)**: 基金份额申购/赎回变化

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd quant-rotation
pip install -r requirements.txt
```

### 2. 配置参数

编辑 `config/config.yaml`:

```yaml
# 监控指数
indices:
  - code: "000300.SH"
    name: "沪深 300"
    etf: "510300"
  - code: "000905.SH"
    name: "中证 500"
    etf: "510500"
  # ... 更多指数

# 因子权重
factor_weights:
  value: 0.25
  momentum: 0.20
  volatility: 0.15
  trend: 0.20
  flow: 0.15
  relative_strength: 0.20

# 策略参数
strategy:
  top_n: 5          # 持有数量
  buffer_n: 8       # 缓冲数量
  rebalance_weekly: true  # 周度调仓
```

### 3. 运行策略

#### 每日评分
```bash
python scripts/daily_run_baostock.py
```

#### 回测
```bash
python scripts/backtest_baostock.py
```

#### 生成前端数据
```bash
python scripts/generate_web_data.py
```

### 4. 启动前端看板

```bash
cd web
npm install
npm run build
npm run preview  # http://localhost:4173
```

---

## 📁 项目结构

```
quant-rotation/
├── config/                  # 配置文件
│   ├── config.yaml         # 主配置
│   └── secrets.yaml        # 敏感信息（不上传）
├── src/                     # 核心代码
│   ├── data_fetcher_baostock.py  # 数据获取
│   ├── scoring_baostock.py       # 评分引擎
│   ├── strategy_baostock.py      # 策略逻辑
│   ├── portfolio.py        # 组合管理
│   └── notifier.py         # 通知模块
├── scripts/                 # 脚本工具
│   ├── daily_run_baostock.py     # 每日运行
│   ├── backtest_baostock.py      # 回测
│   ├── generate_web_data.py      # 生成前端数据
│   └── test_extended_flow.py     # 测试脚本
├── web/                     # 前端看板
│   ├── src/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── dist/               # 构建输出
│   └── package.json
├── data/                    # 数据缓存
│   └── raw/
├── backtest_results/        # 回测结果
├── logs/                    # 日志文件
├── requirements.txt         # Python 依赖
└── README.md               # 本文档
```

---

## 📈 因子体系

### 1. 估值因子 (25%)
- PE 历史分位
- PB 历史分位
- 股息率

### 2. 动量因子 (20%)
- 6 月收益率
- 12 月收益率
- 相对强弱

### 3. 趋势因子 (20%)
- MA20 位置
- MA60 位置

### 4. 波动因子 (15%)
- 年化波动率
- 最大回撤
- 夏普比率

### 5. 资金流因子 (15%) ⭐ 新增
- 成交量趋势
- 量价配合
- 成交金额趋势
- 流入强度
- 北向资金指标
- ETF 份额指标

### 6. 相对强弱 (20%)
- 相对沪深 300 表现

---

## 📊 回测表现

**回测期间**: 2025-01-01 ~ 2026-03-21

| 指标 | 数值 |
|------|------|
| 总收益 | -2.68% |
| 年化收益 | -1.2% |
| 最大回撤 | -3.95% |
| 夏普比率 | 0.45 |
| 胜率 | 52% |

*注：当前为 MVP 版本，因子仍需优化*

---

## 🔧 数据源

### 主要数据源
- **Baostock**: A 股历史行情（免费、稳定）
- **AKShare**: 北向资金、ETF 份额（免费、部分受限）

### 替代数据源
- **Tushare**: 完整财务数据（需积分）
- **Choice**: 机构级数据（付费）

---

## 🌐 前端看板

访问 http://localhost:4173 查看：

1. **排名页面**: 指数评分排名
2. **因子分析**: 雷达图 + 柱状图
3. **资金流详情**: 6 个子因子详解
4. **回测结果**: 净值曲线 + 绩效指标

---

## 📝 待办事项

### 短期优化
- [ ] 修复北向资金历史数据获取
- [ ] 优化 ETF 份额数据源
- [ ] 添加更多 ETF 监控
- [ ] 改进因子归一化方法

### 中期计划
- [ ] 添加基本面因子（ROE、盈利增速）
- [ ] 添加情绪因子
- [ ] 支持自定义因子权重
- [ ] 实盘交易对接

### 长期规划
- [ ] 多策略框架
- [ ] 机器学习因子挖掘
- [ ] 分布式回测引擎

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 📧 联系方式

- 项目 Issue: https://github.com/maoshuochen/quant-rotation/issues
- 作者 GitHub: https://github.com/maoshuochen

---

## ⚠️ 风险提示

本项目仅供学术研究和教育用途，不构成投资建议。

- 历史回测不代表未来表现
- 量化交易存在亏损风险
- 使用本软件产生的任何问题由使用者自行承担

**投资有风险，入市需谨慎！**

---

*最后更新：2026-03-21*
