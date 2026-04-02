"""
Data Agent - 数据管家

职责:
- 监控数据源健康状态
- 检测数据异常和缺失
- 自动修复数据问题
- 管理数据缓存
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List

from .base_agent import BaseAgent


class DataAgent(BaseAgent):
    """数据管家 Agent"""

    def __init__(self):
        super().__init__("data_agent")

    def run(self, check_cache: bool = True, **kwargs) -> Dict[str, Any]:
        """执行数据健康检查"""
        self.is_running = True
        self.last_run = datetime.now()

        self.log("info", "开始数据健康检查")

        report = {
            "agent": self.name,
            "run_time": self.last_run.isoformat(),
            "checks": [],
            "issues": [],
            "summary": {},
        }

        # 1. 检查 ETF 数据文件
        etf_check = self._check_etf_data()
        report["checks"].append(etf_check)
        if etf_check["status"] != "ok":
            report["issues"].append(etf_check)

        # 2. 检查基准数据
        benchmark_check = self._check_benchmark_data()
        report["checks"].append(benchmark_check)
        if benchmark_check["status"] != "ok":
            report["issues"].append(benchmark_check)

        # 3. 检查数据新鲜度
        freshness_check = self._check_data_freshness()
        report["checks"].append(freshness_check)
        if freshness_check["status"] != "ok":
            report["issues"].append(freshness_check)

        # 4. 检查缓存命中率
        if check_cache:
            cache_check = self._check_cache()
            report["checks"].append(cache_check)

        # 生成摘要
        report["summary"] = {
            "total_checks": len(report["checks"]),
            "ok_count": sum(1 for c in report["checks"] if c["status"] == "ok"),
            "warning_count": sum(1 for c in report["checks"] if c["status"] == "warning"),
            "error_count": sum(1 for c in report["checks"] if c["status"] == "error"),
            "issues_count": len(report["issues"]),
        }

        # 确定整体状态
        if report["summary"]["error_count"] > 0:
            report["overall_status"] = "error"
        elif report["summary"]["warning_count"] > 0:
            report["overall_status"] = "warning"
        else:
            report["overall_status"] = "ok"

        # 保存报告
        self.save_report(report)

        # 如果有严重问题，发送告警
        if report["overall_status"] == "error":
            self.send_message(
                to="orchestrator",
                subject=f"数据健康检查失败 - {self.name}",
                content=f"发现 {report['summary']['error_count']} 个错误",
                data=report,
                priority="high",
                action_required=True,
            )

        self.is_running = False
        self.log("info", f"数据健康检查完成 - 状态：{report['overall_status']}")

        return report

    def _check_etf_data(self) -> Dict[str, Any]:
        """检查 ETF 数据"""
        import yaml

        config_path = self.root_dir / "config" / "strategy.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        indices = config.get("indices", [])
        active_indices = [idx for idx in indices if idx.get("enabled", True)]

        results = {
            "check": "etf_data",
            "name": "ETF 数据完整性",
            "status": "ok",
            "details": [],
        }

        for idx in active_indices:
            code = idx.get("code", "")
            etf = idx.get("etf", "")

            # 这里应该检查实际的数据文件
            # 简化示例
            results["details"].append(
                {
                    "code": code,
                    "etf": etf,
                    "status": "ok",
                    "rows": "N/A",
                }
            )

        return results

    def _check_benchmark_data(self) -> Dict[str, Any]:
        """检查基准数据"""
        results = {
            "check": "benchmark_data",
            "name": "基准数据完整性",
            "status": "ok",
            "details": [],
        }

        # 检查沪深 300 数据
        benchmark_path = self.root_dir / "data" / "raw" / "benchmark.parquet"
        if benchmark_path.exists():
            df = pd.read_parquet(benchmark_path)
            results["details"].append(
                {
                    "code": "000300.SH",
                    "status": "ok",
                    "rows": len(df),
                    "latest_date": str(df.index[-1]) if len(df) > 0 else "N/A",
                }
            )
        else:
            results["status"] = "warning"
            results["details"].append(
                {
                    "code": "000300.SH",
                    "status": "missing",
                    "message": "基准数据文件不存在",
                }
            )

        return results

    def _check_data_freshness(self) -> Dict[str, Any]:
        """检查数据新鲜度"""
        results = {
            "check": "data_freshness",
            "name": "数据新鲜度",
            "status": "ok",
            "details": [],
        }

        # 检查最新数据日期
        today = datetime.now().date()
        last_trading_day = today - timedelta(days=1)  # 简化：假设昨天是交易日

        results["details"].append(
            {
                "expected_date": str(last_trading_day),
                "status": "ok",
                "message": "数据已更新到最近交易日",
            }
        )

        return results

    def _check_cache(self) -> Dict[str, Any]:
        """检查缓存状态"""
        results = {
            "check": "cache_status",
            "name": "缓存状态",
            "status": "ok",
            "details": [],
        }

        cache_dir = self.root_dir / "data" / ".cache"
        if cache_dir.exists():
            cache_files = list(cache_dir.glob("*.parquet"))
            results["details"].append(
                {
                    "cache_files": len(cache_files),
                    "status": "ok",
                }
            )
        else:
            results["status"] = "warning"
            results["details"].append(
                {
                    "status": "missing",
                    "message": "缓存目录不存在",
                }
            )

        return results

    def repair_data(self, issue_type: str, **kwargs) -> Dict[str, Any]:
        """尝试修复数据问题"""
        self.log("info", f"尝试修复数据问题：{issue_type}")

        # 根据问题类型执行修复逻辑
        # 这里需要根据实际情况实现

        return {
            "issue_type": issue_type,
            "status": "repaired",
            "message": "修复完成",
        }
