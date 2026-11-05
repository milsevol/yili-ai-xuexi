#!/usr/bin/env zsh
# 提示词工程 — 一键启动（本地服务 + 可视化交互演示）
# 用法：
#   ./start.sh           # 启动本地服务并打开交互页
#   ./start.sh 03        # 打开并跳到第 3 章（思维链 CoT）
#   ./start.sh --port 9000  # 指定本地服务端口
#   ./start.sh --cli     # 终端摘要菜单
#   ./start.sh --help
# 说明：页面上的「真实调用」需要已配置 DEEPSEEK_API_KEY

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

echo "==> 提示词工程 演示（本地服务 + 交互页）"
cd "$TOPIC_ROOT"
exec python3 demos/main.py "$@"
