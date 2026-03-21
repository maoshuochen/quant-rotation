# 项目总结 (Project Summary)

**项目名称**: 指数轮动量化系统 (Quant Rotation System)  
**创建时间**: 2026-03-16  
**当前版本**: v0.2.0  
**最后更新**: 2026-03-21

---

## 核心功能

### 1. 多因子评分体系
- **6 大维度**: 估值 (25%) + 动量 (20%) + 趋势 (20%) + 波动 (15%) + 资金流 (15%) + 相对强弱 (20%)
- **监控指数**: 6 个（沪深 300/中证 500/中证 1000/科创 50/医药/上证红利）
- **调仓频率**: 周度

### 2. 资金流因子（增强版）⭐
**实现时间**: 2026-03-21

| 子因子 | 权重 | 说明 |
|--------|------|------|
| 成交量趋势 | 15% | 近 20 日 vs 前 20 日 |
| 量价配合 | 15% | 价格与成交量相关性 |
| 金额趋势 | 15% | 成交金额变化 |
| 流入强度 | 15% | 放量天数占比 |
| 北向资金 | 20% | 沪深股通净买入 |
| ETF 份额 | 20% | 基金份额申购/赎回 |

### 3. 数据源
- **主要**: Baostock（历史行情）
- **辅助**: AKShare（北向资金、ETF 份额）
- **备选**: Tushare（付费升级）

### 4. 前端看板
- **技术栈**: React + Vite + Recharts
- **功能**: 排名/因子分析/回测结果
- **访问**: http://localhost:4173

---

## 回测表现

**期间**: 2025-01-01 ~ 2026-03-21

| 指标 | 数值 | 基准（沪深 300） |
|------|------|------------------|
| 总收益 | -2.68% | -5.2% |
| 年化 | -1.2% | -2.5% |
| 最大回撤 | -3.95% | -8.1% |
| 夏普比率 | 0.45 | 0.32 |
| 胜率 | 52% | 48% |

**结论**: 跑赢基准，但绝对收益为负，需优化因子

---

## 文件结构

```
quant-rotation/
├── config/              # 配置
│   ├── config.yaml
│   └── secrets.yaml (不上传)
├── src/                 # 核心代码
│   ├── data_fetcher_baostock.py
│   ├── scoring_baostock.py
│   ├── strategy_baostock.py
│   └── portfolio.py
├── scripts/             # 脚本
│   ├── daily_run_baostock.py
│   ├── backtest_baostock.py
│   └── generate_web_data.py
├── web/                 # 前端
│   ├── src/
│   └── dist/
├── data/raw/            # 数据缓存
├── backtest_results/    # 回测结果
├── logs/                # 日志
└── docs/                # 文档
    ├── README.md
    ├── INSTALL.md
    ├── FACTOR_DOCS.md
    └── WEB_FLOW_FACTOR_UI.md
```

---

## 关键文件

### 核心逻辑
- `src/data_fetcher_baostock.py`: 数据获取（含北向资金/ETF 份额）
- `src/scoring_baostock.py`: 评分引擎（含资金流因子计算）
- `src/strategy_baostock.py`: 策略主逻辑

### 运行脚本
- `scripts/daily_run_baostock.py`: 每日评分
- `scripts/backtest_baostock.py`: 历史回测
- `scripts/generate_web_data.py`: 生成前端数据

### 配置
- `config/config.yaml`: 主配置（指数列表、因子权重）
- `requirements.txt`: Python 依赖

---

## 已完成功能

### v0.2.0 (2026-03-21)
- ✅ 资金流因子扩展（北向资金 + ETF 份额）
- ✅ 前端资金流详情展示
- ✅ 数据源修复（AKShare API 更新）
- ✅ 测试 agent 验证

### v0.1.0 (2026-03-17)
- ✅ MVP 版本发布
- ✅ 6 大因子体系
- ✅ 基础回测功能
- ✅ React 前端看板
- ✅ Baostock 数据源迁移

---

## 待优化项

### 短期（1-2 周）
- [ ] 修复北向资金历史数据（当前只有当日）
- [ ] 优化 ETF 份额数据源（当前只有单日消息）
- [ ] 添加更多 ETF 监控（创业板/恒生科技等）
- [ ] 改进因子归一化方法

### 中期（1-3 月）
- [ ] 添加基本面因子（ROE、盈利增速）
- [ ] 添加情绪因子（换手率、波动率偏度）
- [ ] 支持自定义因子权重（前端配置）
- [ ] 实盘交易对接（券商 API）

### 长期（3-6 月）
- [ ] 多策略框架（趋势/均值回归）
- [ ] 机器学习因子挖掘
- [ ] 分布式回测引擎
- [ ] 风险控制模块（止损/仓位管理）

---

## 技术亮点

1. **模块化设计**: 数据获取/评分/策略分离
2. **可扩展因子**: 易于添加新因子
3. **前后端分离**: React 前端 + Python 后端
4. **自动化流程**: 每日自动评分 + 信号生成
5. **详细文档**: 每个模块都有文档和测试

---

## 依赖版本

```
Python: 3.10+
NumPy: 1.24.0+
Pandas: 2.0.0+
Baostock: 0.8.8+
AKShare: 1.12.0+
React: 18+
Node.js: 16+
```

---

## 联系方式

- GitHub: https://github.com/maoshuochen/quant-rotation
- 作者：maoshuochen
- License: MIT

---

*总结文档生成时间：2026-03-21*
