# Quant Rotation Agent Team (Claude Subagent 版本)

## 概述

基于 Claude Code Subagent 机制的量化轮动策略持续迭代系统。每个 Agent 是一个 Claude subagent，通过 prompt 模板驱动。

---

## Agent 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          用户 (User)                                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Claude Code (主会话)                              │
│                    协调所有 subagent                                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐           ┌───────────────┐
│ Data Agent    │          │ Strategy Agent│           │ Frontend Agent│
│ (数据管家)     │          │ (策略分析师)  │           │ (前端工程师)   │
│ subagent      │          │ subagent      │           │ subagent      │
└───────────────┘          └───────────────┘           └───────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐           ┌───────────────┐
│ Backtest Agent│          │ Risk Agent    │           │ DevOps Agent  │
│ (回测专家)     │          │ (风控专家)    │          │ (运维工程师)   │
│ subagent      │          │ subagent      │           │ subagent      │
└───────────────┘          └───────────────┘           └───────────────┘
```

---

## Subagent 定义

### 1. Data Agent (数据管家)

**Prompt 模板**: `agents/prompts/data_agent.md`

**职责**:
- 监控数据源健康状态（Baostock/AKShare）
- 检测数据异常和缺失
- 检查数据文件完整性
- 生成数据质量报告

**输出**:
- `reports/agents/data_health_YYYYMMDD.json`

### 2. Strategy Agent (策略分析师)

**Prompt 模板**: `agents/prompts/strategy_agent.md`

**职责**:
- 分析因子表现
- 检测因子衰减
- 提出因子优化建议
- 监控市场状态变化

**输出**:
- `reports/agents/strategy_analysis_YYYYMMDD.json`

### 3. Frontend Agent (前端工程师)

**Prompt 模板**: `agents/prompts/frontend_agent.md`

**职责**:
- 监控前端数据一致性
- 检测显示问题
- 优化用户体验
- 生成可视化报告

**输出**:
- `reports/agents/frontend_check_YYYYMMDD.json`

### 4. Backtest Agent (回测专家)

**Prompt 模板**: `agents/prompts/backtest_agent.md`

**职责**:
- 分析回测结果
- 检测过拟合风险
- 优化回测参数
- 生成业绩归因

**输出**:
- `reports/agents/backtest_analysis_YYYYMMDD.json`

### 5. Risk Agent (风控专家)

**Prompt 模板**: `agents/prompts/risk_agent.md`

**职责**:
- 监控组合风险指标
- 检测极端市场情况
- 生成风险预警
- 评估最大回撤

**输出**:
- `reports/agents/risk_report_YYYYMMDD.json`

### 6. DevOps Agent (运维工程师)

**Prompt 模板**: `agents/prompts/devops_agent.md`

**职责**:
- 监控 CI/CD 状态
- 管理部署流程
- 检查 workflow 配置
- 处理告警通知

**输出**:
- `reports/agents/devops_status_YYYYMMDD.json`

---

## 使用方式

### 日常任务

```bash
# 运行 Data Agent 检查数据
./scripts/run_agent.sh data

# 运行 Strategy Agent 分析因子
./scripts/run_agent.sh strategy

# 运行所有 Agent
./scripts/run_agent.sh all
```

### 与 Claude 交互

在主会话中使用以下指令：

```
请启动 Data Agent 检查数据健康状态

请启动 Strategy Agent 分析最近的因子表现

请启动 Backtest Agent 分析回测结果
```

---

## 目录结构

```
quant-rotation/
├── agents/
│   ├── prompts/           # Agent prompt 模板
│   │   ├── data_agent.md
│   │   ├── strategy_agent.md
│   │   ├── frontend_agent.md
│   │   ├── backtest_agent.md
│   │   ├── risk_agent.md
│   │   └── devops_agent.md
│   └── prompts.json       # Prompt 汇总配置
├── reports/agents/        # Agent 生成的报告
├── scripts/
│   └── run_agent.sh       # 运行 Agent 的脚本
└── AGENT_TEAM_SUBAGENT.md # 本文档
```

---

## Subagent 优势

1. **无需额外依赖**: 使用 Claude Code 内置的 subagent 机制
2. **自然语言交互**: 通过自然语言指令启动
3. **共享上下文**: 所有 subagent 共享主会话的上下文
4. **灵活扩展**: 添加新 Agent 只需创建新的 prompt 模板

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.2.0 | 2026-04-02 | 重构为 Claude Subagent 架构 |
| 0.1.0 | 2026-04-02 | 初始设计 |
