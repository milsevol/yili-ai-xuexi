#!/usr/bin/env zsh
# 一键启动 Web 总入口（VitePress）
# 环境：macOS + zsh + nvm(Node 24.19) + python3

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
WEB="$ROOT/web"
NODE_VERSION="24.19"

echo "==> yili-ai-xuexi 一键启动"
echo "    仓库: $ROOT"

# --- nvm + Node ---
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "$NVM_DIR/nvm.sh"
elif [[ -s "/usr/local/opt/nvm/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "/usr/local/opt/nvm/nvm.sh"
else
  echo "错误: 未找到 nvm（$HOME/.nvm/nvm.sh）。请先安装 nvm。" >&2
  exit 1
fi

echo "==> 切换 Node: nvm use $NODE_VERSION"
nvm use "$NODE_VERSION" >/dev/null

echo "    node: $(node -v)"
echo "    npm:  $(npm -v)"

# --- Python（演示环境自检，不阻断启动站点）---
if command -v python3 >/dev/null 2>&1; then
  echo "    python3: $(python3 -V 2>&1)"
else
  echo "警告: 未找到 python3，本地主题演示将无法运行。" >&2
fi

# --- Web 依赖 ---
if [[ ! -d "$WEB" ]]; then
  echo "错误: 未找到 web/ 目录" >&2
  exit 1
fi

cd "$WEB"

if [[ ! -d node_modules/vitepress ]]; then
  echo "==> 安装 Web 依赖: npm install"
  npm install
else
  echo "==> Web 依赖已就绪"
fi

echo "==> 同步笔记并启动 VitePress（浏览器将自动打开）"
echo "    本地地址: http://localhost:5173/"
echo "    停止: Ctrl+C"
echo

npm run sync
exec npx vitepress dev docs --open
