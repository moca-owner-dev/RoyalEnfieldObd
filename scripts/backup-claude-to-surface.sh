#!/bin/bash
# Sincroniza la memoria + transcripts de Claude Code (laptop) a la Surface.
# Sirve como backup point-in-time. Idempotente: solo transfiere lo nuevo.
#
# Uso: ./scripts/backup-claude-to-surface.sh

set -e

SURFACE_HOST="${SURFACE_HOST:-pipboy@10.42.0.180}"
SRC="$HOME/.claude/projects/-home-pipboy-Descargas/"
# Path remoto: usamos ~ para que se expanda en el shell remoto
DST="~/.claude/projects/-home-pipboy-Descargas/"

echo "→ Backup Claude memory + transcripts a $SURFACE_HOST"
ssh "$SURFACE_HOST" "mkdir -p $DST"
rsync -az --info=progress2 "$SRC" "$SURFACE_HOST:$DST"

echo "→ Resumen en destino:"
ssh "$SURFACE_HOST" "cd $DST && echo '   memory/:' && ls memory/ | wc -l && echo '   transcripts:' && ls *.jsonl 2>/dev/null | wc -l && echo '   total:' && du -sh ."
