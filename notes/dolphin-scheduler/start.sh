#!/usr/bin/env zsh
# 海豚调度主题 — 一键启动（默认：浏览器可视化交互演示）
# 用法：
#   ./start.sh           # 打开交互页
#   ./start.sh 04        # 打开并跳到第 4 章
#   ./start.sh --cli     # 终端版菜单
#   ./start.sh --cli 04  # 终端版直达章节
#   ./start.sh --help

set -euo pipefail

TOPIC_ROOT="$(cd "$(dirname "$0")" && pwd)"
DEMOS="$TOPIC_ROOT/demos"
REQ="$DEMOS/requirements.txt"
VENV="$TOPIC_ROOT/.venv"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '2,9p' "$0" | sed -E 's/^# ?//'
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "错误: 需要 python3。" >&2
  exit 1
fi

echo "==> 海豚调度演示（可视化优先）"
echo "    python3: $(python3 -V 2>&1)"

cd "$TOPIC_ROOT"

need_venv=0
if [[ -f "$REQ" ]] && grep -Eqv '^[[:space:]]*(#|$)' "$REQ"; then
  need_venv=1
fi

if (( need_venv )); then
  if [[ ! -d "$VENV" ]]; then
    echo "==> 创建虚拟环境: .venv"
    python3 -m venv "$VENV"
  fi
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  echo "==> 安装依赖: demos/requirements.txt"
  pip install -q -r "$REQ"
  PY=python
else
  PY=python3
fi

echo "==> 启动 demos/main.py ${*:-}"
echo
exec "$PY" "$DEMOS/main.py" "$@"
