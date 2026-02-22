#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-${HOME}/.openclaw}"
LOGDIR="${OPENCLAW_HOME}/logs"
PATCHER="${OPENCLAW_HOME}/bin/patch.py"
PACK_CONFIG="${OPENCLAW_POSTFIX_CONFIG:-${OPENCLAW_HOME}/postfix-pack.json}"
OPENCLAW_BIN="${OPENCLAW_BIN:-$(command -v openclaw || true)}"
PORT="${OPENCLAW_GATEWAY_PORT:-18789}"

mkdir -p "$LOGDIR"

if [[ -z "$OPENCLAW_BIN" ]]; then
  echo "openclaw-wrapper: openclaw binary not found" >&2
  exit 1
fi

{
  echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] ensure postfix patch"
  if [[ -x "$PATCHER" ]]; then
    "$PATCHER" --config "$PACK_CONFIG" --sync-models || true
  else
    echo "patcher missing: $PATCHER"
  fi
} >>"${LOGDIR}/postfix-patch.log" 2>&1

exec "$OPENCLAW_BIN" gateway run --port "$PORT"
