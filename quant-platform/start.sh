#!/usr/bin/env zsh
# QuantLab 本地量化工作台 — 一键启动
# 用法：
#   ./start.sh               # 启动并自动打开浏览器
#   ./start.sh --no-browser  # 只启动服务
#   PORT=9000 ./start.sh     # 指定端口

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8777}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "错误: 需要 python3。" >&2
  exit 1
fi

cd "$ROOT"
exec python3 app.py --port "$PORT" "$@"
