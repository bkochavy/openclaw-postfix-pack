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
  gateway_domain="gui/$(id -u)"
  gateway_target="${gateway_domain}/${LABEL}"
  needs_reload=0

  if [[ "$current_prog" != "$WRAPPER" ]]; then
    log "selfheal: correcting ProgramArguments to wrapper"
    "$PLISTBUDDY" -c "Delete :ProgramArguments" "$PLIST" >/dev/null 2>&1 || true
    "$PLISTBUDDY" -c "Add :ProgramArguments array" "$PLIST"
    "$PLISTBUDDY" -c "Add :ProgramArguments:0 string $WRAPPER" "$PLIST"
    needs_reload=1
  else
    log "selfheal: ProgramArguments already healthy"
  fi

  if ! launchctl print "$gateway_target" >/dev/null 2>&1; then
    log "selfheal: gateway launch agent missing from launchd; bootstrapping"
    needs_reload=1
  fi

  if [[ "$needs_reload" -eq 1 ]]; then
    bootout_err="$(launchctl bootout "$gateway_target" 2>&1 || true)"
    bootstrap_err="$(launchctl bootstrap "$gateway_domain" "$PLIST" 2>&1 || true)"
    kickstart_err="$(launchctl kickstart -k "$gateway_target" 2>&1 || true)"

    if launchctl print "$gateway_target" >/dev/null 2>&1; then
      log "selfheal: gateway launch agent reloaded"
    else
      log "selfheal: gateway launch agent reload failed"
      [[ -n "$bootout_err" ]] && log "selfheal: bootout: $bootout_err"
      [[ -n "$bootstrap_err" ]] && log "selfheal: bootstrap: $bootstrap_err"
      [[ -n "$kickstart_err" ]] && log "selfheal: kickstart: $kickstart_err"
    fi
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
