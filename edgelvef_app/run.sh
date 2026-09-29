#!/bin/sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
cd "$PROJECT_ROOT"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/0}"
export DISPLAY="${DISPLAY:-:0}"
export GDK_BACKEND=x11

# A system service can start before XWayland is ready. Wait a bounded time;
# failure then returns to systemd, whose RestartSec prevents a hot loop.
attempt=0
while [ ! -S /tmp/.X11-unix/X0 ] && [ "$attempt" -lt 60 ]; do
    attempt=$((attempt + 1))
    sleep 1
done
if [ ! -S /tmp/.X11-unix/X0 ]; then
    echo "EdgeLVEF: X display socket /tmp/.X11-unix/X0 not ready after 60 seconds" >&2
    exit 1
fi
exec python3 -u main.py
