# Agent Team 使用指南

## 快速开始

### 本地运行

```bash
# 查看 Agent Team 状态
python -m agents.cli --status

# 运行日常任务
python -m agents.cli --mode daily

# 单独运行 Data Agent
python -m agents.cli --agent data_agent

# 紧急模式
python -m agents.cli --mode emergency --issue-type data_missing
```

### GitHub Actions

Agent Team 已集成到 GitHub Actions：

- **定时运行**: 每个交易日 UTC 0 点（北京时间 8 点）
- **手动触发**: 通过 Actions 页面选择运行模式
- **自动告警**: 运行失败时自动创建 GitHub Issue

---

## 运行模式

| 模式 | 说明 | 触发条件 |
|------|------|----------|
| `daily` | 日常任务 | 每个交易日自动运行 |
| `weekly` | 周度分析 | 每周一自动运行 |
| `monthly` | 月度报告 | 每月 1 日自动运行 |
| `emergency` | 紧急处理 | 手动触发 |

---

## Agent 列表

### 已实现

| Agent | 职责 | 状态 |
|------|------|------|
| `orchestrator` | 总协调器 | ✅ 可用 |
| `data_agent` | 数据管家 | ✅ 可用 |

### 计划中

| Agent | 职责 | 预期完成 |
|------|------|----------|
| `strategy_agent` | 策略分析师 | v0.2.0 |
| `backtest_agent` | 回测专家 | v0.2.0 |
| `risk_agent` | 风控专家 | v0.3.0 |
| `frontend_agent` | 前端工程师 | v0.3.0 |
| `devops_agent` | 运维工程师 | v0.4.0 |

---

## 报告位置

Agent 生成的报告保存在：

```
reports/agents/
├── data_agent_YYYYMMDD_HHMMSS.json
├── orchestrator_daily_YYYYMMDD.json
└── ...
```

日志文件保存在：

```
logs/agents/
├── orchestrator.log
├── data_agent.log
└── messages/
```

---

## 消息系统

Agent 之间通过 JSON 消息通信，消息文件保存在 `logs/agents/messages/` 目录。

### 消息格式

```json
{
  "from": "data_agent",
  "to": "orchestrator",
  "type": "alert",
  "priority": "high",
  "timestamp": "2026-04-02T00:00:00",
  "payload": {
    "subject": "数据健康检查失败",
    "content": "发现 2 个错误",
    "data": {...},
    "action_required": true
  }
}
```

---

## 扩展 Agent

### 创建新 Agent

1. 继承 `BaseAgent` 类
2. 实现 `run()` 方法
3. 在 `orchestrator.py` 中注册

```python
from .base_agent import BaseAgent

class MyAgent(BaseAgent):
    def run(self, **kwargs) -> Dict[str, Any]:
        self.is_running = True
        self.last_run = datetime.now()

        # 实现你的逻辑
        report = {...}

        self.is_running = False
        return report
```

### 配置文件

在 `config/agents/` 目录创建配置文件：

```yaml
# config/agents/my_agent.yaml
enabled: true
schedule:
  daily: "0 0 * * 1-5"
thresholds:
  warning_threshold: 0.8
```

---

## 故障排查

### Agent 未运行

检查 `logs/agents/orchestrator.log` 查看错误信息。

### 报告缺失

确认 `reports/agents/` 目录存在且有写入权限。

### 消息积压

检查 `logs/agents/messages/` 目录，清理已处理的消息。

---

## 最佳实践

1. **定期清理日志**: 日志文件可能快速增长，建议定期清理 90 天前的日志
2. **监控磁盘空间**: 报告和日志可能占用大量磁盘空间
3. **设置告警通知**: 配置 Telegram 或邮件告警，及时响应问题
4. **版本控制**: 将 Agent 代码纳入版本控制，记录变更历史

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.1.0 | 2026-04-02 | 初始版本，实现 Data Agent 和 Orchestrator |
