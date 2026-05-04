#!/bin/bash
# Sincroniza memoria + transcripts de Claude Code (laptop) a otras máquinas.
# Idempotente vía rsync — solo transfiere lo nuevo.
#
# Uso:
#   ./scripts/backup-claude-to-surface.sh           # default: a la Surface
#   ./scripts/backup-claude-to-surface.sh mac       # a la Mac
#   ./scripts/backup-claude-to-surface.sh dell      # a la Dell Pro
#   ./scripts/backup-claude-to-surface.sh all       # a todas (saltea offline)

set -e

SRC="$HOME/.claude/projects/-home-pipboy-Descargas/"
DST="~/.claude/projects/-home-pipboy-Descargas/"

# Mac y Surface comparten dongle USB-eth → misma IP cuando se rotan.
# El script salta máquinas no alcanzables.
declare -A TARGETS=(
    [surface]="pipboy@10.42.0.180"
    [mac]="macuser@10.42.0.180"
    [dell]="pipboy@192.168.1.107"
)

push_to() {
    local name="$1"
    local host="${TARGETS[$name]}"
    if [[ -z "$host" ]]; then
        echo "× target desconocido: $name"
        return 1
    fi
    echo "→ $name ($host)"
    if ! ssh -o ConnectTimeout=3 -o BatchMode=yes "$host" "mkdir -p $DST" 2>/dev/null; then
        echo "  × $host inalcanzable, saltando"
        return 0
    fi
    rsync -az "$SRC" "$host:$DST"
    ssh "$host" "cd $DST && echo \"  memory: \$(ls memory/ | wc -l) | transcripts: \$(ls *.jsonl 2>/dev/null | wc -l) | total: \$(du -sh . | cut -f1)\""
}

target="${1:-surface}"
case "$target" in
    surface|mac|dell)
        push_to "$target"
        ;;
    all)
        for t in surface mac dell; do push_to "$t"; done
        ;;
    *)
        echo "uso: $0 [surface|mac|dell|all]"
        exit 1
        ;;
esac
