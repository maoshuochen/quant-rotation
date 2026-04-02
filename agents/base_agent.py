"""
Agent 基类 - 所有 Agent 的父类
"""
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(self, name: str, config_path: Optional[str] = None):
        self.name = name
        self.root_dir = Path(__file__).parent.parent
        self.config_path = config_path or self.root_dir / "config" / "agents" / f"{name}.yaml"
        self.logs_dir = self.root_dir / "logs" / "agents"
        self.reports_dir = self.root_dir / "reports" / "agents"

        # 确保目录存在
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # 配置
        self.config = self._load_config()

        # 日志
        self._setup_logging()

        # 状态
        self.last_run: Optional[datetime] = None
        self.is_running = False

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        import yaml

        if Path(self.config_path).exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {"enabled": True, "schedule": None, "thresholds": {}}

    def _setup_logging(self):
        """设置日志"""
        self.logger = logging.getLogger(f"agents.{self.name}")

        if not self.logger.handlers:
            handler = logging.FileHandler(self.logs_dir / f"{self.name}.log", encoding="utf-8")
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        self.logger.setLevel(logging.INFO)

    def log(self, level: str, message: str, **kwargs):
        """记录日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "level": level,
            "message": message,
            **kwargs,
        }
        getattr(self.logger, level.lower())(message)
        return log_entry

    def save_report(self, report: Dict[str, Any], filename: Optional[str] = None) -> Path:
        """保存报告"""
        if filename is None:
            filename = f"{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report_path = self.reports_dir / filename
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        self.log("info", f"Report saved: {report_path}")
        return report_path

    def send_message(
        self,
        to: str,
        subject: str,
        content: str,
        data: Optional[Dict] = None,
        priority: str = "normal",
        action_required: bool = False,
    ):
        """发送消息到其他 Agent 或 Orchestrator"""
        message = {
            "from": self.name,
            "to": to,
            "type": "alert" if action_required else "report",
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "subject": subject,
                "content": content,
                "data": data or {},
                "action_required": action_required,
            },
        }

        # 保存到消息队列文件
        messages_dir = self.logs_dir / "messages"
        messages_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{self.name}_{to}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(messages_dir / filename, "w", encoding="utf-8") as f:
            json.dump(message, f, ensure_ascii=False, indent=2)

        self.log("info", f"Message sent to {to}: {subject}")
        return message

    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """执行 Agent 任务 - 由子类实现"""
        pass

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "agent": self.name,
            "status": "healthy" if self.config.get("enabled", True) else "disabled",
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "is_running": self.is_running,
            "timestamp": datetime.now().isoformat(),
        }

    def __repr__(self):
        return f"<{self.__class__.__name__}(name={self.name})>"
