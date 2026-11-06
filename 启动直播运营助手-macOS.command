#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

say() { printf '%s\n' "$*"; }
fail() { printf '\n[错误] %s\n' "$*" >&2; exit 1; }

APP_URL="http://127.0.0.1:8000/"
HEALTH_URL="http://127.0.0.1:8000/health"
VENV="$ROOT/backend/.venv"
PYTHON="$VENV/bin/python"
LOGS="$ROOT/.local/logs"
RUN_DIR="$ROOT/.local/run"

mkdir -p "$LOGS" "$RUN_DIR"

say ""
say "=== 直播运营助手 · macOS 启动 ==="
say ""

if curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1; then
  say "[=] 后端已在运行 (8000)"
else
  [ -x "$PYTHON" ] || fail "后端环境不存在。请先双击「安装依赖-macOS.command」。"

  if [ ! -f "$ROOT/frontend/dist/index.html" ]; then
    say "[+] 首次启动，正在构建前端 ..."
    if command -v pnpm >/dev/null 2>&1; then
      PNPM=(pnpm)
    elif command -v corepack >/dev/null 2>&1; then
      PNPM_SPEC="$(node -p 'require("./frontend/package.json").packageManager')"
      PNPM=(corepack "$PNPM_SPEC")
    else
      fail "未找到 pnpm/corepack，请先重新运行安装脚本。"
    fi
    (
      cd "$ROOT/frontend"
      "${PNPM[@]}" build
    )
  fi

  say "[+] 启动后端 (8000) ..."
  (
    cd "$ROOT/backend"
    nohup "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
      >"$LOGS/backend.out.log" 2>"$LOGS/backend.err.log" &
    printf '%s\n' "$!" >"$RUN_DIR/backend.pid"
  )

  READY=0
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1; then
      READY=1
      break
    fi
    sleep 0.5
  done
  if [ "$READY" -ne 1 ]; then
    say "[×] 后端没有在 30 秒内就绪。最近日志："
    tail -n 30 "$LOGS/backend.err.log" 2>/dev/null || true
    fail "请查看 $LOGS 下的日志。"
  fi
  say "[=] 后端已就绪 (8000)"
fi

say "[+] 检查数据源（Chrome 调试端口 9222）..."
CONNECT_RESULT="$(curl -fsS --max-time 90 -X POST "$APP_URL/api/live-watch/connection/connect?mode=assistant" 2>/dev/null || true)"
if [ -n "$CONNECT_RESULT" ]; then
  printf '%s' "$CONNECT_RESULT" | "$PYTHON" -c 'import json, sys; d = json.load(sys.stdin); print("    " + str(d.get("message") or "数据源检查完成"))' || say "    数据源检查完成"
else
  say "    [警告] 数据源检查失败，可在工具里点「连接数据源」重试。"
fi

say ""
say "工具地址：$APP_URL"
say "日志目录：$LOGS"
say "首次使用若弹出千川登录页，登录一次即可；登录态会保存在助手专用 Chrome 配置中。"
open "$APP_URL"
say ""
read -r -p "按回车关闭此窗口（后台服务继续运行）..." _
