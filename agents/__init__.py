"""
Quant Rotation Agent Team
多 Agent 协作的量化轮动策略持续迭代系统
"""
__version__ = "0.1.0"

from .base_agent import BaseAgent
from .orchestrator import Orchestrator

__all__ = ["BaseAgent", "Orchestrator"]
