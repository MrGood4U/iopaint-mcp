#!/usr/bin/env bash
set -euo pipefail

DEVICE="${1:-cpu}"
MODEL="${2:-${IOPAINT_MODEL:-}}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$DEVICE" in
  cpu|cuda) ;;
  *) echo "Device must be cpu or cuda." >&2; exit 1 ;;
esac

if [[ -z "$MODEL" ]]; then
  if [[ -t 0 ]]; then
    echo "请选择 Docker 中的 IOPaint 模型："
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

mkdir -p "$ROOT/models" "$ROOT/data/input" "$ROOT/data/output" "$ROOT/outputs"
export IOPAINT_MODEL="$MODEL"
export MCP_HOST_OUTPUT_DIR="${MCP_HOST_OUTPUT_DIR:-$ROOT/outputs}"

export MCP_HOST_TEMP_DIR="${MCP_HOST_TEMP_DIR:-${TMPDIR:-/tmp}}"
if [[ -z "${MCP_PATH_MAPPINGS:-}" ]]; then
  export MCP_PATH_MAPPINGS="$MCP_HOST_TEMP_DIR=>/host-temp;$ROOT/data=>/data"
elif [[ "$MCP_PATH_MAPPINGS" != *'=>/data;'* && "$MCP_PATH_MAPPINGS" != *'=>/data' ]]; then
  export MCP_PATH_MAPPINGS="$MCP_PATH_MAPPINGS;$ROOT/data=>/data"
fi

COMPOSE_ARGS=(-f "$ROOT/docker-compose.yml")
if [[ "$DEVICE" == "cuda" ]]; then
  COMPOSE_ARGS+=(-f "$ROOT/docker-compose.cuda.yml")
fi
COMPOSE_ARGS+=(up)
if [[ "${DOCKER_FOREGROUND:-0}" != "1" ]]; then COMPOSE_ARGS+=(-d); fi
if [[ "${DOCKER_NO_BUILD:-0}" != "1" ]]; then COMPOSE_ARGS+=(--build); fi

docker compose "${COMPOSE_ARGS[@]}"
echo ""
echo "IOPaint model:  $IOPAINT_MODEL"
echo "IOPaint API:    http://127.0.0.1:28680"
echo "MCP endpoint:   http://127.0.0.1:28681/mcp"
echo "Input directory: $ROOT/data/input"
echo "Output directory: $MCP_HOST_OUTPUT_DIR"
