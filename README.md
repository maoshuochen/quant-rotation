# 指数轮动量化系统 (Quant Rotation System)

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Data](https://img.shields.io/badge/Data-Baostock%2FAKShare-orange.svg)](https://akshare.akfamily.xyz/)

基于多因子评分的指数轮动研究系统，支持 A 股主要宽基指数和行业指数的评分、排名、信号生成、回测和前端可视化。

---

## 📊 策略特点

### 当前正式链路
- **唯一数据入口**: `src/data_fetcher_baostock.py`
- **唯一策略入口**: `src/strategy_baostock.py`
- **唯一回测入口**: `scripts/backtest_baostock.py`
- **唯一前端数据入口**: `scripts/generate_web_data.py`
- **唯一前端应用**: `web/`

### 核心功能
- **主线因子体系**: 估值 + 动量 + 趋势 + 波动 + 资金流 + 相对强弱
- **自动评分排名**: 每日对监控指数进行综合评分
- **交易信号生成**: 基于排名生成买入/卖出信号
- **模拟回测**: 支持历史回测和绩效分析
- **实时看板**: React 前端可视化展示

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

### 3. 运行正式链路

#### 每日评分与调仓信号
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
├── src/                     # 正式主线代码
│   ├── data_fetcher_baostock.py  # 数据获取
│   ├── scoring_baostock.py       # 主线评分引擎
│   ├── market_regime.py          # 市场状态与动态权重
│   ├── strategy_baostock.py      # 主线策略逻辑
│   ├── portfolio.py              # 组合管理
│   └── notifier.py               # 通知模块
├── scripts/                 # 正式脚本入口
│   ├── daily_run_baostock.py     # 每日运行
│   ├── backtest_baostock.py      # 主线回测
│   ├── generate_web_data.py      # 生成前端数据
│   ├── generate_backtest_json.py # 回测 JSON 产物
│   └── test_*.py                 # 主线测试脚本
├── legacy/                  # 已下线的旧实现
│   ├── src/
│   └── scripts/
├── web/                     # 前端看板
│   ├── src/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── dist/               # 构建输出
│   └── package.json
├── report_server.py         # 报告静态服务
├── data/                    # 数据缓存
│   └── raw/
├── backtest_results/        # 回测结果
├── logs/                    # 日志文件
├── requirements.txt         # Python 依赖
└── README.md               # 本文档
```

---

## 📈 当前说明

- 当前仓库以“研究型策略系统”为定位，不宣称策略指标已达成产品化目标。
- `legacy/` 下保留历史版本与实验代码，仅供参考。
- 若文档与代码不一致，以本文件和 `src/*_baostock.py` / `scripts/*_baostock.py` 为准。

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

### 5. 资金流因子 (15%)
- 成交量趋势
- 量价配合
- 成交金额趋势
- 流入强度
- 北向资金指标
- ETF 份额指标

### 6. 相对强弱 (20%)
- 相对沪深 300 表现

---

## 📊 当前回测表现

**回测期间**: 2025-01-01 ~ 2026-03-21

| 指标 | 数值 |
|------|------|
| 总收益 | -2.68% |
| 年化收益 | -1.2% |
| 最大回撤 | -3.95% |
| 夏普比率 | 0.45 |
| 胜率 | 52% |

*注：当前主线已可运行，但策略表现仍处于持续优化阶段。*

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

## 📝 当前优化方向

### 短期优化
- [ ] 修复北向资金历史数据获取
- [ ] 优化 ETF 份额数据源
- [ ] 添加更多 ETF 监控
- [ ] 改进因子归一化方法

### 中期计划
- [ ] 主线回测框架统一
- [ ] 动态权重效果验证
- [ ] 首页重构为“建议持仓 + 调仓解释”
- [ ] 报告产物协议标准化

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
