#!/usr/bin/env sh
set -eu
TASK_SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$TASK_SCRIPT_DIR/artcraft_edge.py" "$@"
