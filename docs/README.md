# 指数轮动量化系统 - 项目总览

**项目名称**: 指数轮动量化系统 (Quant-Rotation)  
**版本**: v2.0  
**状态**: 开发完成 ✅  
**最后更新**: 2026-03-24

---

## 📋 快速导航

| 文档类型 | 文件 | 用途 |
|----------|------|------|
| **产品 PRD** | [PRD.md](PRD.md) | 产品需求文档 (功能/指标/路线图) |
| **技术方案** | [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md) | 技术架构/模块设计/部署配置 |
| **优化文档** | [OPTIMIZATION.md](OPTIMIZATION.md) | 数据源扩展 + 因子体系增强 |
| **基本面优化** | [FUNDAMENTAL_OPTIMIZATION.md](FUNDAMENTAL_OPTIMIZATION.md) | PE/PB/ROE 数据获取 |
| **可视化指南** | [VISUALIZATION_GUIDE.md](VISUALIZATION_GUIDE.md) | 报告生成 + 图表解读 |
| **前端文档** | [FRONTEND_REPORTS.md](FRONTEND_REPORTS.md) | Web 看板 + API 集成 |

---

## 🎯 项目目标

构建一个**自动化、透明、可解释**的指数轮动量化系统，帮助投资者：
- ✅ 自动选择最优指数 ETF
- ✅ 每周自动调仓
- ✅ 全面可视化报告
- ✅ 实时状态监控

---

## 📊 核心功能

### 1. 8 因子评分模型

| 因子 | 权重 | 说明 |
|------|------|------|
| 动量 | 20% | 6 个月收益率 |
| 波动 | 15% | 年化波动率 (低波高分) |
| 趋势 | 20% | 价格相对 MA20/MA60 位置 |
| 估值 | 20% | 价格历史分位 |
| 资金流 | 15% | 成交量 + 北向资金+ETF 份额 |
| 相对强弱 | 20% | 相对沪深 300 超额收益 |
| 基本面 | 15% | PE/PB/ROE/盈利增长 |
| 情绪 | 10% | ETF 份额变化 + 成交量异常 |

**权重归一化**: 总和 1.35 → 实际权重 = 单项/1.35

---

### 2. 监控标的 (20 只 ETF)

**宽基指数 (8 只)**:
- 沪深 300 (510300)
- 中证 500 (510500)
- 中证 1000 (512100)
- 创业板指 (159915) ✅ 深市
- 科创 50 (588000)
- 消费指数 (159928) ✅ 深市
- 医药指数 (512010)
- 科技指数 (515000)

**行业指数 (12 只)**:
- 金融 (510230)、制造 (516880)、周期 (512340)、红利 (510880)
- 军工 (512660)、新能源 (516160)、半导体 (512480)、白酒 (512690)
- 银行 (512800)、证券 (512000)、煤炭 (515220)、恒生 (159920) ✅ 深市

---

### 3. 策略规则

```
持仓：前 5 名 ETF (等权重 20%)
调仓：每周一
缓冲：跌出前 8 名才卖出
成本：万三手续费 + 0.1% 滑点
```

---

## 🏗️ 技术架构

```
┌─────────────────┐
│   Web 看板      │ 端口 3000 (React/Vite)
│   Telegram Bot  │ 通知推送
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Flask API     │ 端口 5001 (报告服务)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   策略引擎      │ 评分 + 回测
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   数据获取      │ Baostock + AKShare
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   本地存储      │ Parquet + CSV
└─────────────────┘
```

---

## 📁 项目结构

```
quant-rotation/
├── src/
│   ├── data_fetcher_hybrid.py      # 混合数据获取器 (沪市 + 深市)
│   ├── fundamental_data.py         # 基本面数据获取器 (PE/PB/ROE)
│   ├── scoring_enhanced.py         # 8 因子评分引擎
│   └── visualizer.py               # 可视化报告生成器
│
├── scripts/
│   ├── daily_run_baostock.py       # 每日运行脚本
│   ├── backtest_baostock.py        # 回测脚本 (旧版)
│   └── backtest_enhanced.py        # 回测脚本 (增强版)
│
├── web/
│   ├── src/
│   │   ├── App.jsx                 # 主应用 (4 个 Tab)
│   │   ├── ReportsPage.jsx         # 报告页面
│   │   └── main.jsx                # 入口
│   └── public/
│       ├── ranking.json            # 指数排名数据
│       └── backtest.json           # 回测数据
│
├── config/
│   └── config.yaml                 # 策略配置
│
├── reports/
│   ├── *.png                       # 图表 (权益曲线/回撤/heatmap)
│   ├── *.html                      # 综合报告
│   └── *.csv                       # 数据文件
│
├── data/
│   ├── raw/                        # ETF 行情缓存
│   └── fundamental/                # 基本面数据缓存
│
├── docs/
│   ├── README.md                   # 本文件 (项目总览)
│   ├── PRD.md                      # 产品需求文档
│   ├── TECHNICAL_SPEC.md           # 技术方案
│   ├── OPTIMIZATION.md             # 优化文档
│   ├── FUNDAMENTAL_OPTIMIZATION.md # 基本面优化
│   ├── VISUALIZATION_GUIDE.md      # 可视化指南
│   └── FRONTEND_REPORTS.md         # 前端文档
│
├── report_server.py                # Flask API 服务器
└── logs/
    └── strategy.log                # 运行日志
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd /root/.openclaw/workspace/quant-rotation

# Python 依赖
pip3 install pandas numpy matplotlib seaborn flask flask-cors baostock akshare pyyaml

# Node 依赖
cd web && npm install
```

### 2. 启动服务

```bash
# 前端 (端口 3000)
cd web && npm run dev

# API 服务器 (端口 5001)
cd .. && python3 report_server.py
```

### 3. 运行回测

```bash
# 增强版回测 (含基本面因子)
python3 scripts/backtest_enhanced.py 20250101 20260324
```

### 4. 查看看板

浏览器打开：**http://localhost:3000**

---

## 📈 回测表现

**回测期间**: 2025-01-02 ~ 2026-03-20 (442 天)

| 指标 | 数值 | 目标 | 状态 |
|------|------|------|------|
| 总收益 | -1.27% | > 10% | ⚠️ 待优化 |
| 年化收益 | -1.05% | > 10% | ⚠️ 待优化 |
| 最大回撤 | -10.43% | < 15% | ✅ 达标 |
| 夏普比率 | -0.42 | > 0.5 | ⚠️ 待优化 |
| 交易次数 | 32 | - | - |
| 交易成本 | 9,792 | - | - |

**注**: 回测期间市场整体下跌，策略表现待优化

---

## ✅ 已完成功能

### v1.0 (基础版)
- [x] 6 因子评分模型
- [x] 沪市 ETF 数据 (Baostock)
- [x] 基础回测
- [x] Web 看板 (排名/因子/回测)

### v2.0 (增强版) ✅ 当前版本
- [x] 8 因子评分模型 (+基本面 + 情绪)
- [x] 混合数据源 (沪市 + 深市)
- [x] 基本面数据获取 (PE/PB/ROE)
- [x] 可视化报告 (6 种图表)
- [x] 报告页面集成
- [x] Flask API 服务
- [x] Telegram 通知

---

## 📅 路线图

### v2.1 (2026-Q2)
- [ ] 因子 IC 分析
- [ ] 动态权重调整
- [ ] 行业集中度限制

### v2.2 (2026-Q3)
- [ ] 极端市场止损
- [ ] 多策略组合
- [ ] 云端备份

### v3.0 (2026-Q4)
- [ ] 实时回测
- [ ] 参数优化框架
- [ ] 多用户支持

---

## 🔧 关键命令

```bash
# 测试数据获取
python3 src/data_fetcher_hybrid.py

# 测试基本面数据
python3 src/fundamental_data.py

# 运行回测
python3 scripts/backtest_enhanced.py 20250101 20260324

# 生成可视化报告
python3 src/visualizer.py

# 查看 API
curl http://localhost:5001/api/reports

# 查看日志
tail -f logs/strategy.log
```

---

## 📞 支持

### 文档
- 产品需求：[PRD.md](PRD.md)
- 技术方案：[TECHNICAL_SPEC.md](TECHNICAL_SPEC.md)
- 使用指南：[VISUALIZATION_GUIDE.md](VISUALIZATION_GUIDE.md)

### 问题反馈
- GitHub Issues: (待开放)
- 邮件：(待配置)

---

## 📝 更新日志

### v2.0 (2026-03-24)
- ✅ 新增基本面因子 (PE/PB/ROE)
- ✅ 新增情绪因子 (ETF 份额/成交量异常)
- ✅ 新增深市 ETF 支持 (159915/159928/159920)
- ✅ 新增可视化报告系统 (6 种图表)
- ✅ 新增 Web 报告页面
- ✅ 新增 Flask API 服务

### v1.0 (2026-03-17)
- ✅ 基础 6 因子评分模型
- ✅ Baostock 数据源
- ✅ 基础回测框架
- ✅ Web 看板 (3 页面)

---

## ⚠️ 免责声明

1. 本系统仅供学习和研究使用
2. 不构成任何投资建议
3. 历史回测不代表未来表现
4. 投资有风险，入市需谨慎

---

*最后更新：2026-03-24 23:35*
