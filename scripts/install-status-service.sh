#!/bin/bash
# Instala interceptor-status.service y lo arranca al boot.
# Uso (corre UNA sola vez con sudo):
#   sudo bash ~/RoyalEnfieldObd/scripts/install-status-service.sh
#
# Lo que hace:
#   1. Copia la unit a /etc/systemd/system/
#   2. Recarga systemd
#   3. Desactiva getty@tty1 (el login de consola en el LCD compite por tty1)
#   4. Habilita + arranca interceptor-status.service
#   5. Muestra el estado

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo." >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_SRC="$REPO_ROOT/systemd/interceptor-status.service"
UNIT_DST="/etc/systemd/system/interceptor-status.service"

echo ">> Copying unit -> $UNIT_DST"
install -m 0644 "$UNIT_SRC" "$UNIT_DST"

echo ">> systemctl daemon-reload"
systemctl daemon-reload

echo ">> Disabling getty@tty1.service (LCD console login)"
systemctl disable --now getty@tty1.service || true

echo ">> Enabling + starting interceptor-status.service"
systemctl enable --now interceptor-status.service

echo
systemctl --no-pager status interceptor-status.service || true
