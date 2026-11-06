#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

say() { printf '%s\n' "$*"; }
fail() { printf '\n[错误] %s\n' "$*" >&2; exit 1; }

say ""
say "=== 直播运营助手 · macOS 安装依赖 ==="
say ""

if ! command -v python3 >/dev/null 2>&1; then
  fail "未找到 python3。请先安装 Python 3.11 或更高版本：https://www.python.org/downloads/macos/"
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  fail "Python 版本过低。需要 3.11 或更高版本：python3 --version"
fi
say "[=] Python：$(python3 --version 2>&1)"

if ! command -v node >/dev/null 2>&1; then
  fail "未找到 Node.js。请先安装 Node.js 20 或更高版本：https://nodejs.org/"
fi
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if [ "$NODE_MAJOR" -lt 20 ]; then
  fail "Node.js 版本过低：$(node --version)。需要 20 或更高版本。"
fi
say "[=] Node.js：$(node --version)"

if command -v pnpm >/dev/null 2>&1; then
  PNPM=(pnpm)
elif command -v corepack >/dev/null 2>&1; then
  PNPM_SPEC="$(node -p 'require("./frontend/package.json").packageManager')"
  PNPM=(corepack "$PNPM_SPEC")
else
  fail "未找到 pnpm/corepack。请安装 Node.js 20+，或在终端运行：npm install -g pnpm"
fi
say "[=] pnpm：$("${PNPM[@]}" --version)"

VENV="$ROOT/backend/.venv"
if [ ! -x "$VENV/bin/python" ]; then
  say "[+] 创建后端虚拟环境 ..."
  python3 -m venv "$VENV"
else
  say "[=] 后端虚拟环境已存在"
fi

say "[+] 安装后端依赖 ..."
"$VENV/bin/python" -m pip install --upgrade pip
(
  cd "$ROOT/backend"
  "$VENV/bin/python" -m pip install -e .
)

say "[+] 安装前端依赖 ..."
(
  cd "$ROOT/frontend"
  "${PNPM[@]}" install --frozen-lockfile
)

say "[+] 构建前端（后端会直接托管构建结果）..."
(
  cd "$ROOT/frontend"
  "${PNPM[@]}" build
)

if [ ! -f "$ROOT/backend/.env" ]; then
  cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
  say "[+] 已生成 backend/.env"
else
  say "[=] backend/.env 已存在"
fi

chmod +x "$ROOT/安装依赖-macOS.command" "$ROOT/启动直播运营助手-macOS.command" 2>/dev/null || true

say ""
say "=== 安装完成 ==="
say "下一步：双击「启动直播运营助手-macOS.command」"
say "首次连接数据源时，在弹出的 Chrome 里登录一次千川即可。"
say ""
read -r -p "按回车关闭窗口..." _
