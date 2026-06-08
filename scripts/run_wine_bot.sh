#!/usr/bin/env bash
set -euo pipefail

cd /home/ubuntu/auto_forex

export WINEPREFIX="${WINEPREFIX:-/home/ubuntu/.wine}"
export WINEDEBUG="${WINEDEBUG:--all}"

MT5_TERMINAL_LINUX_PATH="${MT5_TERMINAL_LINUX_PATH:-/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe}"
WINDOWS_PYTHON="${WINDOWS_PYTHON:-C:\\Python310\\python.exe}"
WINE_BIN="${WINE_BIN:-/usr/lib/wine/wine64}"

if [[ -x "$MT5_TERMINAL_LINUX_PATH" ]] && ! pgrep -f "terminal64.exe" >/dev/null 2>&1; then
  nohup xvfb-run -a "$WINE_BIN" "$MT5_TERMINAL_LINUX_PATH" >/tmp/auto-forex-mt5.out 2>/tmp/auto-forex-mt5.err &
  sleep 15
fi

exec xvfb-run -a "$WINE_BIN" "$WINDOWS_PYTHON" -m forex_bot.main
