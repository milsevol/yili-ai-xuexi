#!/usr/bin/env zsh
# 金融 Agent 平台 — 一键启动（FastAPI 后端 + Vue 控制台）
# 用法：
#   ./start.sh                 # 启动并打开控制台
#   ./start.sh --reset         # 清空演示数据后重建
#   ./start.sh --port 9000     # 指定端口
#   ./start.sh --no-browser    # 只启动服务
# 依赖：fastapi / uvicorn（pip install -r demos/requirements.txt）
# 模型：配置 DEEPSEEK_API_KEY 使用真实模型；未配置时自动离线模拟

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

if ! python3 -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "缺少依赖，请先执行：" >&2
  echo "  python3 -m pip install -r \"$TOPIC_ROOT/demos/requirements.txt\"" >&2
  exit 1
fi

echo "==> 金融 Agent 平台（FastAPI + Vue 控制台）"
cd "$TOPIC_ROOT"
exec python3 demos/main.py "$@"
