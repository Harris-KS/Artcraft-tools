#!/usr/bin/env sh
set -eu
TASK_SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ ! -f "$TASK_SCRIPT_DIR/artcraft_edge.py" ]; then
    echo 'The complete linux-edge folder is required; artcraft_edge.py is missing.' >&2
    echo 'Download and extract https://github.com/Harris-KS/Artcraft-tools/archive/refs/heads/main.zip' >&2
    exit 2
fi
exec python3 "$TASK_SCRIPT_DIR/artcraft_edge.py" "$@"
