#!/bin/bash
# Wrapper: renderiza el SYSTEM STATUS MONITOR al LCD (tty1).
# Uso (necesita sudo porque /dev/tty1 sólo lo escribe root):
#   sudo ~/RoyalEnfieldObd/scripts/show-status.sh
#
# Loop persistente con auto-refresh; reintenta hasta que la moto esté online.
# Salir: Ctrl+C en la sesión que lo lanzó.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/status_tui.py" > /dev/tty1
