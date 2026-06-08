#!/usr/bin/env bash
set -euo pipefail

cd /home/ubuntu/auto_forex

export WINEPREFIX="${WINEPREFIX:-/home/ubuntu/.wine}"
export WINEDEBUG="${WINEDEBUG:--all}"

MT5_TERMINAL_LINUX_PATH="${MT5_TERMINAL_LINUX_PATH:-/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe}"
WINDOWS_PYTHON="${WINDOWS_PYTHON:-C:\\Python310\\python.exe}"
WINE_BIN="${WINE_BIN:-/usr/lib/wine/wine64}"
XVFB_DISPLAY="${XVFB_DISPLAY:-:88}"
XVFB_GEOMETRY="${XVFB_GEOMETRY:-1280x1024x24}"

if ! pgrep -f "Xvfb $XVFB_DISPLAY" >/dev/null 2>&1; then
  Xvfb "$XVFB_DISPLAY" -screen 0 "$XVFB_GEOMETRY" -nolisten tcp >/tmp/auto-forex-xvfb.out 2>/tmp/auto-forex-xvfb.err &
  XVFB_PID=$!
  trap 'kill "$XVFB_PID" 2>/dev/null || true' EXIT
  sleep 3
fi

export DISPLAY="$XVFB_DISPLAY"

if [[ -x "$MT5_TERMINAL_LINUX_PATH" ]] && ! pgrep -f "terminal64.exe" >/dev/null 2>&1; then
  nohup "$WINE_BIN" "$MT5_TERMINAL_LINUX_PATH" >/tmp/auto-forex-mt5.out 2>/tmp/auto-forex-mt5.err &
  sleep 45
fi

exec "$WINE_BIN" "$WINDOWS_PYTHON" -m forex_bot.main
