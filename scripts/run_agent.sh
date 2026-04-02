#!/bin/bash
# Quant Rotation Agent Team 启动脚本
# 使用 Claude Code Subagent 机制

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
AGENT_DIR="$PROJECT_DIR/agents/prompts"
REPORT_DIR="$PROJECT_DIR/reports/agents"

# 确保报告目录存在
mkdir -p "$REPORT_DIR"

# 显示使用帮助
show_help() {
    echo "Quant Rotation Agent Team"
    echo ""
    echo "用法：$0 <agent_name> [options]"
    echo ""
    echo "可用的 Agent:"
    echo "  data      - 数据管家 (检查数据健康状态)"
    echo "  strategy  - 策略分析师 (分析因子表现)"
    echo "  frontend  - 前端工程师 (检查前端数据一致性)"
    echo "  backtest  - 回测专家 (分析回测结果)"
    echo "  risk      - 风控专家 (评估组合风险)"
    echo "  devops    - 运维工程师 (监控 CI/CD)"
    echo "  all       - 运行所有 Agent (日常模式)"
    echo ""
    echo "示例:"
    echo "  $0 data"
    echo "  $0 strategy"
    echo "  $0 all"
    echo ""
}

# 启动 subagent 的函数
run_agent() {
    local agent_name="$1"
    local prompt_file="$AGENT_DIR/${agent_name}_agent.md"

    if [ ! -f "$prompt_file" ]; then
        echo "错误：找不到 Agent prompt 文件：$prompt_file"
        echo "请确保 agent_name 正确 (data, strategy, frontend, backtest, risk, devops)"
        exit 1
    fi

    echo "========================================"
    echo "启动 ${agent_name} Agent"
    echo "========================================"
    echo "Prompt 文件：$prompt_file"
    echo ""

    # 读取 prompt 内容
    local prompt_content
    prompt_content=$(cat "$prompt_file")

    # 输出到控制台（实际使用时由 Claude 处理）
    echo "请执行以下任务："
    echo ""
    echo "$prompt_content"
    echo ""
    echo "========================================"
    echo "报告将保存到：$REPORT_DIR"
    echo "========================================"
}

# 运行所有 Agent（日常模式）
run_all() {
    echo "========================================"
    echo "运行所有 Agent (日常模式)"
    echo "========================================"
    echo ""

    # 日常模式只运行必要的 Agent
    local daily_agents=("data" "frontend" "devops")

    for agent in "${daily_agents[@]}"; do
        run_agent "$agent"
        echo ""
    done

    echo "========================================"
    echo "所有 Agent 任务已启动"
    echo "========================================"
}

# 主程序
main() {
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi

    case "$1" in
        "help"|"-h"|"--help")
            show_help
            ;;
        "all")
            run_all
            ;;
        "data"|"strategy"|"frontend"|"backtest"|"risk"|"devops")
            run_agent "$1"
            ;;
        *)
            echo "错误：未知的 Agent '$1'"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
