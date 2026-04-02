"""
Agent Team 命令行入口
"""
import argparse
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.orchestrator import Orchestrator


def main():
    parser = argparse.ArgumentParser(description="Quant Rotation Agent Team")

    parser.add_argument(
        "--mode",
        type=str,
        default="daily",
        choices=["daily", "weekly", "monthly", "emergency"],
        help="运行模式",
    )

    parser.add_argument(
        "--agent",
        type=str,
        default=None,
        help="单独运行某个 Agent",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="无头模式（用于 CI/CD）",
    )

    parser.add_argument(
        "--issue-type",
        type=str,
        default=None,
        help="紧急模式下的问题类型",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="查看 Agent Team 状态",
    )

    args = parser.parse_args()

    # 创建 Orchestrator
    orchestrator = Orchestrator()

    if args.status:
        # 查看状态
        status = orchestrator.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0

    if args.agent:
        # 单独运行某个 Agent
        if args.agent not in orchestrator.agents:
            print(f"错误：未知的 Agent '{args.agent}'")
            print(f"可用的 Agent: {list(orchestrator.agents.keys())}")
            return 1

        agent = orchestrator.agents[args.agent]
        print(f"运行 Agent: {args.agent}")
        report = agent.run()
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        return 0

    # 运行 Orchestrator
    print(f"启动 Agent Team - 模式：{args.mode}")

    kwargs = {}
    if args.mode == "emergency" and args.issue_type:
        kwargs["issue_type"] = args.issue_type

    try:
        report = orchestrator.run(mode=args.mode, **kwargs)
        print("\n" + "=" * 60)
        print("Agent Team 运行完成")
        print("=" * 60)
        print(json.dumps(report["summary"], indent=2, ensure_ascii=False))

        if not args.headless:
            print("\n详细报告已保存到：reports/agents/")

        return 0 if report["summary"].get("failed", 0) == 0 else 1

    except Exception as e:
        print(f"错误：{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
