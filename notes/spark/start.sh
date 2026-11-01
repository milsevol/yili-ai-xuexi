#!/usr/bin/env zsh
# Spark 主题 — 一键启动（默认：浏览器可视化交互演示）
# 用法：
#   ./start.sh           # 打开交互页
#   ./start.sh 06        # 打开并跳到第 6 章（Shuffle 与 Join）
#   ./start.sh --cli     # 终端摘要菜单
#   ./start.sh --cli 06  # 终端查看某章摘要
#   ./start.sh --help

set -euo pipefail

TOPIC_ROOT="$(cd "$(dirname "$0")" && pwd)"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '2,9p' "$0" | sed -E 's/^# ?//'
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "错误: 需要 python3。" >&2
  exit 1
fi

echo "==> Spark 演示（可视化交互页）"
cd "$TOPIC_ROOT"
exec python3 demos/main.py "$@"
