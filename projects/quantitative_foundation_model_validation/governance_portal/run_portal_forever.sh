#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
PORTAL_SCRIPT="projects/quantitative_foundation_model_validation/governance_portal/portal_server.py"
PORTAL_LOG="projects/quantitative_foundation_model_validation/preexperiment/governance_records/portal_server.log"

cd "$PROJECT_ROOT" || exit 1
mkdir -p "$(dirname "$PORTAL_LOG")"

while true; do
    printf '[%s] starting governance portal\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$PORTAL_LOG"
    .venv/bin/python "$PORTAL_SCRIPT" --host 127.0.0.1 --port 8011 >> "$PORTAL_LOG" 2>&1
    exit_code=$?
    printf '[%s] portal exited with code %s; restarting in 3 seconds\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$exit_code" >> "$PORTAL_LOG"
    sleep 3
done
