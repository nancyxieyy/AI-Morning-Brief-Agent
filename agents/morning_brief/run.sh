#!/bin/bash
# 早安 AI 简报 Agent 启动脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/morning_brief.log"
PYTHON="/opt/homebrew/Caskroom/miniforge/base/bin/python3"

mkdir -p "$PROJECT_DIR/logs"
echo "----------------------------------------" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始运行" >> "$LOG_FILE"

"$PYTHON" "$SCRIPT_DIR/run.py" >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 运行结束" >> "$LOG_FILE"
