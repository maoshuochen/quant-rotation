"""
Orchestrator - Agent 总协调器

职责:
- 协调各 Agent 工作
- 汇总各 Agent 报告
- 生成综合周报/月报
- 决策冲突处理
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base_agent import BaseAgent


class Orchestrator(BaseAgent):
    """Agent 总协调器"""

    def __init__(self):
        super().__init__("orchestrator")

        # 注册子 Agent
        self.agents = {}
        self._register_agents()

    def _register_agents(self):
        """注册子 Agent"""
        from .data_agent import DataAgent

        # 实例化所有 Agent
        self.agents["data_agent"] = DataAgent()

        # 未来可以添加更多 Agent
        # self.agents["strategy_agent"] = StrategyAgent()
        # self.agents["backtest_agent"] = BacktestAgent()
        # self.agents["risk_agent"] = RiskAgent()
        # self.agents["frontend_agent"] = FrontendAgent()
        # self.agents["devops_agent"] = DevOpsAgent()

        self.logger.info(f"已注册 {len(self.agents)} 个 Agent")

    def run(self, mode: str = "daily", **kwargs) -> Dict[str, Any]:
        """
        运行 Agent Team

        Args:
            mode: 运行模式
                - daily: 日常运行
                - weekly: 周度分析
                - monthly: 月度分析
                - emergency: 紧急处理
        """
        self.is_running = True
        start_time = datetime.now()

        self.log("info", f"启动 Agent Team - 模式：{mode}")

        report = {
            "orchestrator": "orchestrator",
            "mode": mode,
            "start_time": start_time.isoformat(),
            "agent_reports": {},
            "summary": {},
            "actions_taken": [],
        }

        # 1. 健康检查 - 确保所有 Agent 可用
        health_report = self._health_check_all()
        report["health_check"] = health_report

        # 2. 根据模式执行不同流程
        if mode == "daily":
            agent_reports = self._run_daily_workflow()
        elif mode == "weekly":
            agent_reports = self._run_weekly_workflow()
        elif mode == "monthly":
            agent_reports = self._run_monthly_workflow()
        elif mode == "emergency":
            agent_reports = self._run_emergency_workflow(**kwargs)
        else:
            agent_reports = {}

        report["agent_reports"] = agent_reports

        # 3. 汇总报告
        report["summary"] = self._summarize_reports(agent_reports)
        report["end_time"] = datetime.now().isoformat()

        # 4. 保存综合报告
        self.save_report(report, filename=f"orchestrator_{mode}_{datetime.now().strftime('%Y%m%d')}.json")

        # 5. 处理消息队列
        self._process_messages()

        self.is_running = False
        self.log("info", f"Agent Team 运行完成 - 耗时：{report['summary'].get('duration_seconds', 'N/A')}s")

        return report

    def _health_check_all(self) -> Dict[str, Any]:
        """所有 Agent 健康检查"""
        health_status = {}

        for name, agent in self.agents.items():
            try:
                health = agent.health_check()
                health_status[name] = health
            except Exception as e:
                health_status[name] = {
                    "agent": name,
                    "status": "error",
                    "error": str(e),
                }
                self.logger.error(f"{name} 健康检查失败：{e}")

        return health_status

    def _run_daily_workflow(self) -> Dict[str, Any]:
        """日常流程"""
        reports = {}

        # Data Agent 检查数据
        self.log("info", "启动 Data Agent - 数据健康检查")
        try:
            data_report = self.agents["data_agent"].run()
            reports["data_agent"] = data_report

            # 如果数据有问题，可能需要通知其他 Agent
            if data_report.get("overall_status") == "error":
                self.log("warning", "数据检查发现错误，需要关注")
        except Exception as e:
            self.logger.error(f"Data Agent 运行失败：{e}")
            reports["data_agent"] = {"status": "error", "error": str(e)}

        # 未来可以添加更多 Agent 的日常任务
        # Strategy Agent 分析因子
        # Backtest Agent 运行回测
        # Risk Agent 计算风险

        return reports

    def _run_weekly_workflow(self) -> Dict[str, Any]:
        """周度流程"""
        reports = {}

        # 先执行日常流程
        daily_reports = self._run_daily_workflow()
        reports.update(daily_reports)

        # Strategy Agent 周度分析
        # 未来实现

        return reports

    def _run_monthly_workflow(self) -> Dict[str, Any]:
        """月度流程"""
        reports = {}

        # 先执行周度流程
        weekly_reports = self._run_weekly_workflow()
        reports.update(weekly_reports)

        # 生成月度综合报告
        # 未来实现

        return reports

    def _run_emergency_workflow(self, **kwargs) -> Dict[str, Any]:
        """紧急流程"""
        reports = {}
        issue_type = kwargs.get("issue_type", "unknown")

        self.log("warning", f"紧急处理：{issue_type}")

        # 根据问题类型调用相应 Agent
        if issue_type.startswith("data"):
            try:
                data_report = self.agents["data_agent"].run()
                reports["data_agent"] = data_report
            except Exception as e:
                reports["data_agent"] = {"status": "error", "error": str(e)}

        return reports

    def _summarize_reports(self, reports: Dict[str, Any]) -> Dict[str, Any]:
        """汇总所有 Agent 报告"""
        summary = {
            "total_agents": len(reports),
            "successful": 0,
            "failed": 0,
            "warnings": 0,
            "duration_seconds": 0,
        }

        for name, report in reports.items():
            if isinstance(report, dict):
                status = report.get("overall_status", report.get("status", "unknown"))
                if status == "ok":
                    summary["successful"] += 1
                elif status == "error":
                    summary["failed"] += 1
                elif status == "warning":
                    summary["warnings"] += 1

        # 计算耗时（如果有时戳信息）
        # ...

        return summary

    def _process_messages(self):
        """处理消息队列"""
        messages_dir = self.logs_dir / "messages"
        if not messages_dir.exists():
            return

        # 处理发给 orchestrator 的消息
        for msg_file in messages_dir.glob("*_orchestrator_*.json"):
            try:
                with open(msg_file, "r", encoding="utf-8") as f:
                    message = json.load(f)

                self.log("info", f"处理消息：{message['payload']['subject']}")

                # 根据消息类型处理
                if message.get("action_required"):
                    self._handle_action_message(message)

                # 处理完后可以标记为已读或删除
            except Exception as e:
                self.logger.error(f"处理消息失败：{e}")

    def _handle_action_message(self, message: Dict[str, Any]):
        """处理需要行动的消息"""
        # 根据消息内容决定采取什么行动
        payload = message.get("payload", {})
        subject = payload.get("subject", "")
        data = payload.get("data", {})

        # 实现具体的处理逻辑
        pass

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "is_running": self.is_running,
            "registered_agents": list(self.agents.keys()),
            "last_run": self.last_run.isoformat() if self.last_run else None,
        }

    def add_agent(self, name: str, agent: BaseAgent):
        """添加新 Agent"""
        self.agents[name] = agent
        self.log("info", f"添加 Agent: {name}")

    def remove_agent(self, name: str):
        """移除 Agent"""
        if name in self.agents:
            del self.agents[name]
            self.log("info", f"移除 Agent: {name}")
