#!/usr/bin/env bash
set -uo pipefail

COOLDOWN_SECONDS="${COOLDOWN_SECONDS:-120}"
MAX_CYCLES="${MAX_CYCLES:-}"

usage() {
  echo "Usage: $0 <command> [args ...]"
  echo "Example: COOLDOWN_SECONDS=120 $0 python3 scripts/blog_file_manager.py --blog-id 5"
}

if [ "$#" -eq 0 ]; then
  usage
  exit 1
fi

cooldown() {
  local remaining mins secs
  remaining="$COOLDOWN_SECONDS"
  while [ "$remaining" -gt 0 ]; do
    mins=$((remaining / 60))
    secs=$((remaining % 60))
    printf '\rCooldown active: restarting in %02d:%02d ' "$mins" "$secs"
    sleep 1
    remaining=$((remaining - 1))
  done
  printf '\rCooldown complete. Restarting now.        \n'
}

cycle=0
while true; do
  cycle=$((cycle + 1))
  echo "============================================================"
  echo "Cycle #$cycle started at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "Command: $*"
  "$@"
  exit_code=$?
  if [ "$exit_code" -eq 0 ]; then
    echo "Cycle #$cycle completed successfully."
  else
    echo "Cycle #$cycle failed with exit code $exit_code."
  fi
  if [ -n "$MAX_CYCLES" ] && [ "$cycle" -ge "$MAX_CYCLES" ]; then
    echo "Reached MAX_CYCLES=$MAX_CYCLES, stopping loop."
    exit 0
  fi
  cooldown
done

