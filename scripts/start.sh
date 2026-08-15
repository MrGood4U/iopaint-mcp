#!/usr/bin/env bash
set -euo pipefail

DEVICE="${1:-cpu}"
MODEL="${2:-${IOPAINT_MODEL:-}}"
IOPAINT_PORT="${IOPAINT_PORT:-28680}"
MCP_PORT="${MCP_PORT:-28681}"
IOPAINT_STARTUP_TIMEOUT_SEC="${IOPAINT_STARTUP_TIMEOUT_SEC:-900}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
PYTHON="$VENV/bin/python"
mkdir -p "$ROOT/runtime/output" "$ROOT/models"

case "$DEVICE" in
  cpu|cuda) ;;
  *) echo "Device must be cpu or cuda." >&2; exit 1 ;;
esac

if [[ -z "$MODEL" ]]; then
  if [[ -t 0 ]]; then
    echo "请选择 IOPaint 模型："
    echo "  1) lama - 推荐的通用擦除模型"
    echo "  2) cv2  - OpenCV 快速模式"
    echo "  c) 自定义模型名 / HuggingFace 模型 / 本地模型路径"
    read -r -p "请输入选项（默认 1）：" selection
    case "$selection" in
      ""|1) MODEL="lama" ;;
      2) MODEL="cv2" ;;
      c|C) read -r -p "请输入模型名或路径：" MODEL; MODEL="${MODEL:-lama}" ;;
      *) echo "无效选项。" >&2; exit 1 ;;
    esac
  else
    MODEL="lama"
  fi
fi

if [[ ! -x "$PYTHON" ]]; then
  command -v python3.10 >/dev/null || { echo "Python 3.10 was not found." >&2; exit 1; }
  python3.10 -m venv "$VENV"
fi

"$PYTHON" -m pip install --upgrade pip
if [[ "$DEVICE" == "cuda" ]]; then
  "$PYTHON" -m pip install torch==2.1.2+cu121 torchvision==0.16.2+cu121 --index-url https://download.pytorch.org/whl/cu121
else
  "$PYTHON" -m pip install torch==2.1.2+cpu torchvision==0.16.2+cpu --index-url https://download.pytorch.org/whl/cpu
fi
"$PYTHON" -m pip install -e "$ROOT" iopaint

"$ROOT/scripts/stop.sh" >/dev/null 2>&1 || true
nohup "$VENV/bin/iopaint" start --model="$MODEL" --device="$DEVICE" --host=127.0.0.1 --port="$IOPAINT_PORT" --model-dir="$ROOT/models" >"$ROOT/runtime/iopaint.log" 2>&1 & echo $! >"$ROOT/runtime/iopaint.pid"
IOPAINT_PID="$(cat "$ROOT/runtime/iopaint.pid")"
echo "Waiting for IOPaint to become healthy (model download may take a while)..."
STARTED_AT="$(date +%s)"
while true; do
  if ! kill -0 "$IOPAINT_PID" 2>/dev/null; then
    echo "IOPaint exited before becoming healthy. Check $ROOT/runtime/iopaint.error.log" >&2
    exit 1
  fi
  if curl -fsS --max-time 5 "http://127.0.0.1:$IOPAINT_PORT/api/v1/server-config" >/dev/null 2>&1; then
    break
  fi
  if (( $(date +%s) - STARTED_AT >= IOPAINT_STARTUP_TIMEOUT_SEC )); then
    kill "$IOPAINT_PID" 2>/dev/null || true
    echo "IOPaint did not become healthy within ${IOPAINT_STARTUP_TIMEOUT_SEC}s. Check $ROOT/runtime/iopaint.error.log" >&2
    exit 1
  fi
  sleep 2
done

nohup "$PYTHON" -m iopaint_mcp --transport streamable-http --host 127.0.0.1 --port "$MCP_PORT" >"$ROOT/runtime/mcp.log" 2>&1 & echo $! >"$ROOT/runtime/mcp.pid"
echo "IOPaint: http://127.0.0.1:$IOPAINT_PORT"
echo "MCP:     http://127.0.0.1:$MCP_PORT/mcp"
echo "Model:   $MODEL"
