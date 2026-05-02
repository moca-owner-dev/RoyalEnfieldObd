#!/bin/bash
# Wrapper: renderiza el dashboard TUI al LCD (tty1).
# Uso (necesita sudo porque /dev/tty1 sólo lo escribe root):
#   sudo ~/RoyalEnfieldObd/scripts/show-tui.sh
#
# El sudo envuelve TODO el comando incluyendo la redirección, evitando
# el problema clásico de "pipe a sudo" donde el redirect no escala los
# privilegios.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/dashboard_tui.py" > /dev/tty1
