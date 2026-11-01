#!/usr/bin/env zsh
# 打包静态站点（VitePress）
# 默认按 GitHub Pages 项目站路径打包：base=/yili-ai-xuexi/
#
# 用法：
#   ./deploy.sh              # 仅打包
#   ./deploy.sh --preview    # 打包后本地预览产物
#   ./deploy.sh --base /     # 按站点根路径打包（自有域名 / 非 GitHub 子路径）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
WEB="$ROOT/web"
DIST="$WEB/docs/.vitepress/dist"
NODE_VERSION="24.19"
BASE="/yili-ai-xuexi/"
DO_PREVIEW=0

normalize_base() {
  local b="$1"
  [[ "$b" == /* ]] || b="/${b}"
  [[ "$b" == */ ]] || b="${b}/"
  print -r -- "$b"
}

while (( $# > 0 )); do
  case "$1" in
    --preview|-p)
      DO_PREVIEW=1
      shift
      ;;
    --base)
      [[ -n "${2:-}" ]] || { echo "错误: --base 需要路径参数" >&2; exit 1; }
      BASE="$(normalize_base "$2")"
      shift 2
      ;;
    --base=*)
      BASE="$(normalize_base "${1#--base=}")"
      shift
      ;;
    -h|--help)
      sed -n '2,10p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "未知参数: $1（可用 --help）" >&2
      exit 1
      ;;
  esac
done

echo "==> yili-ai-xuexi 打包部署"
echo "    仓库: $ROOT"
echo "    base: $BASE"

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "$NVM_DIR/nvm.sh"
elif [[ -s "/usr/local/opt/nvm/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "/usr/local/opt/nvm/nvm.sh"
else
  echo "错误: 未找到 nvm。" >&2
  exit 1
fi

echo "==> 切换 Node: nvm use $NODE_VERSION"
nvm use "$NODE_VERSION" >/dev/null
echo "    node: $(node -v)  npm: $(npm -v)"

cd "$WEB"

if [[ ! -d node_modules/vitepress ]]; then
  echo "==> 安装依赖: npm install"
  npm install
else
  echo "==> 依赖已就绪"
fi

echo "==> 构建静态站点"
export VITEPRESS_BASE="$BASE"
npm run build

echo
echo "==> 打包完成"
echo "    产物目录: $DIST"
echo "    文件数:   $(find "$DIST" -type f | wc -l | tr -d ' ')"
echo
echo "部署方式见: 部署说明.md"
echo "  · GitHub Pages（推荐）: 推送 main 后由 Actions 自动部署"
echo "  · 其它静态托管: 将上述 dist 目录内容上传即可"
echo

if (( DO_PREVIEW )); then
  echo "==> 本地预览构建产物（Ctrl+C 结束）"
  echo "    当前 base=$BASE"
  exec npx vitepress preview docs
fi
