#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-${HOME}/.openclaw}"
LOGDIR="${OPENCLAW_HOME}/logs"
PATCHER="${OPENCLAW_HOME}/bin/patch.py"
WRAPPER="${OPENCLAW_HOME}/bin/wrapper.sh"
PACK_CONFIG="${OPENCLAW_POSTFIX_CONFIG:-${OPENCLAW_HOME}/postfix-pack.json}"
mkdir -p "$LOGDIR"
LOGFILE="${LOGDIR}/gateway-selfheal.log"

log() {
  printf "[%s] %s\n" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*" >>"$LOGFILE"
}

log "selfheal: start"

if [[ -x "$PATCHER" ]]; then
  if "$PATCHER" --config "$PACK_CONFIG" --sync-models >>"$LOGFILE" 2>&1; then
    log "selfheal: patch check ok"
  else
    log "selfheal: patch check failed (non-fatal)"
  fi
else
  log "selfheal: patcher missing: $PATCHER"
fi

if [[ "$(uname -s)" == "Darwin" ]]; then
  PLIST="${HOME}/Library/LaunchAgents/ai.openclaw.gateway.plist"
  LABEL="ai.openclaw.gateway"
  PLISTBUDDY="/usr/libexec/PlistBuddy"

  if [[ ! -f "$PLIST" ]]; then
    log "selfheal: gateway plist missing: $PLIST"
    exit 0
  fi

  if [[ ! -x "$WRAPPER" ]]; then
    log "selfheal: wrapper missing: $WRAPPER"
    exit 0
  fi

  current_prog="$($PLISTBUDDY -c "Print :ProgramArguments:0" "$PLIST" 2>/dev/null || true)"
  if [[ "$current_prog" != "$WRAPPER" ]]; then
    log "selfheal: correcting ProgramArguments to wrapper"
    "$PLISTBUDDY" -c "Delete :ProgramArguments" "$PLIST" >/dev/null 2>&1 || true
    "$PLISTBUDDY" -c "Add :ProgramArguments array" "$PLIST"
    "$PLISTBUDDY" -c "Add :ProgramArguments:0 string $WRAPPER" "$PLIST"

    launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
    launchctl kickstart -k "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
    log "selfheal: gateway launch agent reloaded"
  else
    log "selfheal: ProgramArguments already healthy"
  fi
elif [[ "$(uname -s)" == "Linux" ]] && command -v systemctl >/dev/null 2>&1; then
  GATEWAY_UNIT="openclaw-gateway.service"
  if ! systemctl --user is-active "$GATEWAY_UNIT" >/dev/null 2>&1; then
    log "selfheal: gateway service not active — attempting restart"
    systemctl --user start "$GATEWAY_UNIT" 2>/dev/null || true
  else
    log "selfheal: gateway service active"
  fi
fi

log "selfheal: done"
