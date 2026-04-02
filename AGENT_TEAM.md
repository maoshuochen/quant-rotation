# Quant Rotation Agent Team

## 概述

基于多 Agent 协作的量化轮动策略持续迭代系统，实现自动化监控、分析、优化和部署。

---

## Agent 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Agent Orchestrator                            │
│                         (总协调器)                                    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐           ┌───────────────┐
│ Data Agent    │          │ Strategy Agent│           │ Frontend Agent│
│ (数据管家)     │          │ (策略分析师)  │           │ (前端工程师)   │
└───────────────┘          └───────────────┘           └───────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐           ┌───────────────┐
│ Backtest Agent│          │ Risk Agent    │           │ DevOps Agent  │
│ (回测专家)     │          │ (风控专家)    │           │ (运维工程师)   │
└───────────────┘          └───────────────┘           └───────────────┘
```

---

## Agent 职责

### 1. Data Agent (数据管家)
**职责**：
- 监控数据源健康状态（Baostock/AKShare）
- 检测数据异常和缺失
- 自动修复数据问题
- 管理数据缓存

**触发条件**：
- 每日数据更新后
- 数据健康检查失败时

**输出**：
- 数据质量报告
- 数据修复建议

### 2. Strategy Agent (策略分析师)
**职责**：
- 分析因子表现
- 检测因子衰减
- 提出因子优化建议
- 监控市场状态变化

**触发条件**：
- 每周回测完成后
- 市场状态显著变化时

**输出**：
- 因子表现分析报告
- 策略调整建议

### 3. Frontend Agent (前端工程师)
**职责**：
- 监控前端数据一致性
- 检测显示问题
- 优化用户体验
- 生成可视化报告

**触发条件**：
- 数据更新后
- 用户反馈问题时

**输出**：
- 前端健康检查报告
- UI 优化建议

### 4. Backtest Agent (回测专家)
**职责**：
- 分析回测结果
- 检测过拟合风险
- 优化回测参数
- 生成业绩归因

**触发条件**：
- 每次回测完成后

**输出**：
- 回测分析报告
- 参数优化建议

### 5. Risk Agent (风控专家)
**职责**：
- 监控组合风险指标
- 检测极端市场情况
- 生成风险预警
- 评估最大回撤

**触发条件**：
- 每日净值更新后
- 市场波动率异常时

**输出**：
- 风险评估报告
- 风控参数调整建议

### 6. DevOps Agent (运维工程师)
**职责**：
- 监控 CI/CD 状态
- 管理部署流程
- 监控系统资源
- 处理告警通知

**触发条件**：
- 部署失败时
- 系统资源告警

**输出**：
- 部署状态报告
- 运维告警

### 7. Orchestrator (总协调器)
**职责**：
- 协调各 Agent 工作
- 汇总各 Agent 报告
- 生成综合周报/月报
- 决策冲突处理

**触发条件**：
- 每日定时汇总
- 紧急事件处理

**输出**：
- 综合运营报告
- Agent 任务调度日志

---

## 工作流程

### 日常流程 (每个交易日)

```
00:00 UTC ─┬─ Data Agent 检查数据完整性
           │
           ├─ Backtest Agent 运行增量回测
           │
           ├─ Risk Agent 计算风险指标
           │
           ├─ Frontend Agent 更新页面数据
           │
           └─ DevOps Agent 部署到 Pages
```

### 周度流程 (每周一)

```
周一 00:00 UTC ─┬─ Orchestrator 启动周度分析
                │
                ├─ Strategy Agent 分析因子表现
                │
                ├─ Backtest Agent 生成周度归因
                │
                └─ Orchestrator 生成周报
```

### 月度流程 (每月 1 日)

```
1 日 00:00 UTC ─┬─ 所有 Agent 生成月度报告
                │
                ├─ Strategy Agent 提出月度优化方案
                │
                ├─ Risk Agent 评估月度风险
                │
                └─ Orchestrator 生成月报并归档
```

---

## 通信协议

### 消息格式

```json
{
  "from": "agent_name",
  "to": "agent_name|all|orchestrator",
  "type": "report|alert|request|response",
  "priority": "normal|high|urgent",
  "timestamp": "ISO8601",
  "payload": {
    "subject": "消息主题",
    "content": "详细内容",
    "data": {},
    "action_required": false
  }
}
```

### 消息队列

使用 GitHub Issues 作为消息队列：
- Label: `data-agent`, `strategy-agent`, `risk-agent` 等
- Label: `priority-high`, `priority-urgent`
- Label: `action-required`, `informational`

---

## 数据存储

| 数据类型 | 存储位置 | 保留期 |
|----------|----------|--------|
| 原始数据 | `data/raw/` | 永久 |
| 回测结果 | `backtest_results/` | 永久 |
| Agent 报告 | `reports/agent/` | 1 年 |
| 消息日志 | `logs/agents/` | 90 天 |
| 配置文件 | `config/agents/` | 永久 |

---

## 启动方式

### 本地开发

```bash
# 启动单个 Agent
python -m agents.data_agent --watch

# 启动所有 Agent
python -m agents.orchestrator --start-all
```

### GitHub Actions

```yaml
# .github/workflows/agents.yml
on:
  schedule:
    - cron: '0 0 * * *'  # 每日 UTC 0 点
  workflow_dispatch:

jobs:
  run-agents:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Agent Team
        run: |
          python -m agents.orchestrator --headless
```

---

## 监控面板

访问 `https://maoshuochen.github.io/quant-rotation/agents` 查看：
- Agent 运行状态
- 任务执行历史
- 告警统计
- 报告归档

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.1.0 | 2026-04-02 | 初始设计 |
