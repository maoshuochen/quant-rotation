# Quant Rotation Agent Team 使用指南

## 快速开始

### 方式 1：使用启动脚本

```bash
# 查看可用的 Agent
./scripts/run_agent.sh --help

# 运行 Data Agent
./scripts/run_agent.sh data

# 运行所有日常 Agent
./scripts/run_agent.sh all
```

### 方式 2：直接在 Claude 会话中启动

在主会话中告诉 Claude 启动哪个 subagent：

```
请启动 Data Agent subagent，使用 agents/prompts/data_agent.md 作为 prompt

请启动 Strategy Agent subagent，分析最近的因子表现
```

---

## Agent 列表

| Agent | 职责 | Prompt 文件 |
|------|------|-------------|
| `data` | 数据管家 | `agents/prompts/data_agent.md` |
| `strategy` | 策略分析师 | `agents/prompts/strategy_agent.md` |
| `frontend` | 前端工程师 | `agents/prompts/frontend_agent.md` |
| `backtest` | 回测专家 | `agents/prompts/backtest_agent.md` |
| `risk` | 风控专家 | `agents/prompts/risk_agent.md` |
| `devops` | 运维工程师 | `agents/prompts/devops_agent.md` |

---

## 运行模式

### 日常任务（每个交易日）

```bash
# 运行日常 Agent（data, frontend, devops）
./scripts/run_agent.sh all
```

或在 Claude 中说：
```
请运行日常 Agent 任务，检查数据健康、前端一致性和部署状态
```

### 周度分析（每周一）

```bash
# 运行所有 Agent
./scripts/run_agent.sh strategy
./scripts/run_agent.sh backtest
./scripts/run_agent.sh risk
```

或在 Claude 中说：
```
请启动 Strategy Agent、Backtest Agent 和 Risk Agent 进行周度分析
```

### 紧急处理

当发现问题时，启动相应的 Agent：

```bash
# 数据问题
./scripts/run_agent.sh data

# 前端问题
./scripts/run_agent.sh frontend

# 部署问题
./scripts/run_agent.sh devops
```

---

## 报告位置

所有 Agent 生成的报告保存在：

```
reports/agents/
├── data_health_YYYYMMDD.json
├── strategy_analysis_YYYYMMDD.json
├── frontend_check_YYYYMMDD.json
├── backtest_analysis_YYYYMMDD.json
├── risk_report_YYYYMMDD.json
└── devops_status_YYYYMMDD.json
```

---

## 与 Claude 交互示例

### 启动 Data Agent

```
请启动 Data Agent 检查数据健康状态，需要：
1. 检查所有 ETF 数据文件
2. 验证基准数据完整性
3. 检查数据新鲜度
4. 生成 JSON 报告保存到 reports/agents/
```

### 启动 Strategy Agent

```
请启动 Strategy Agent 分析因子表现，需要：
1. 分析 momentum、trend、flow 因子的 IC 值和 IR 值
2. 检测是否有因子衰减
3. 根据当前市场状态提出权重调整建议
4. 生成 JSON 报告
```

### 启动多个 Agent

```
请依次启动以下 Agent 进行周度分析：
1. Strategy Agent - 分析因子表现
2. Backtest Agent - 分析回测结果
3. Risk Agent - 评估组合风险

每个 Agent 的报告都保存到 reports/agents/
```

---

## 添加新 Agent

1. 在 `agents/prompts/` 目录创建新的 prompt 模板

```markdown
# New Agent - 名称

## 角色
...

## 任务
...

## 输出格式
...
```

2. 在 `agents/prompts.json` 中添加配置

```json
{
  "new_agent": {
    "name": "New Agent",
    "role": "...",
    "prompt_file": "agents/prompts/new_agent.md"
  }
}
```

3. 更新 `scripts/run_agent.sh` 添加支持

---

## 最佳实践

1. **定期运行**: 每个交易日运行日常 Agent，每周一运行周度分析
2. **保存报告**: 所有报告都保存为 JSON 格式，便于后续分析
3. **及时响应**: 当 Agent 报告 warning 或 error 时，及时处理
4. **持续优化**: 根据实际使用情况优化 Agent prompt

---

## 故障排查

### Agent 无法启动

检查 prompt 文件是否存在：
```bash
ls -la agents/prompts/
```

### 报告未生成

确认 `reports/agents/` 目录存在：
```bash
mkdir -p reports/agents
```

### 查看更多日志

运行脚本时添加 `-v` 参数（如果支持）或在 Claude 中要求输出详细日志。
