#!/usr/bin/env bash
# Play the monitoring build. Every play session writes ~/es-observe/logs/play-<date>-<time>.jsonl.
# Uses your normal saves and plugins (~/.local/share/endless-sky) unless ES_CONFIG names another folder,
# e.g. a Flatpak install: ES_CONFIG=~/.var/app/io.github.endless_sky.endless_sky/data/endless-sky
set -euo pipefail

BASE=${ES_OBSERVE:-$HOME/es-observe}
mkdir -p "$BASE/logs"
LOG="$BASE/logs/play-$(date +%Y%m%d-%H%M%S).jsonl"
ARGS=(--resources "$BASE/src")
[ -n "${ES_CONFIG:-}" ] && ARGS+=(--config "$ES_CONFIG")
echo "Logging to $LOG"
ES_COMBAT_LOG="$LOG" exec "$BASE/build/endless-sky" "${ARGS[@]}" "$@"
