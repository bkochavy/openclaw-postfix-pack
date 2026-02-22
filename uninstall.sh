#!/usr/bin/env bash
set -euo pipefail

KEEP_CONFIG=1

usage() {
  cat <<'EOF'
Usage: bash uninstall.sh [--remove-config]

  --remove-config  Remove ~/.openclaw/postfix-pack.json
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remove-config)
      KEEP_CONFIG=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

log() {
  printf "[%s] %s\n" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*"
}

latest_file() {
  local pattern="$1"
  ls -1t ${pattern} 2>/dev/null | head -n 1 || true
}

OPENCLAW_HOME="${OPENCLAW_HOME:-${HOME}/.openclaw}"
BACKUP_DIR="${OPENCLAW_HOME}/backups"
CONFIG_PATH="${OPENCLAW_POSTFIX_CONFIG:-${OPENCLAW_HOME}/postfix-pack.json}"

if [[ "$(uname -s)" == "Darwin" ]]; then
  SELFHEAL_PLIST="${HOME}/Library/LaunchAgents/ai.openclaw.gateway-selfheal.plist"
  GATEWAY_PLIST="${HOME}/Library/LaunchAgents/ai.openclaw.gateway.plist"

  launchctl bootout "gui/$(id -u)/ai.openclaw.gateway-selfheal" >/dev/null 2>&1 || true
  rm -f "$SELFHEAL_PLIST"

  gateway_backup="$(latest_file "${BACKUP_DIR}/ai.openclaw.gateway.plist.postfix-pack.*.bak")"
  if [[ -n "$gateway_backup" ]]; then
    cp "$gateway_backup" "$GATEWAY_PLIST"
    launchctl bootout "gui/$(id -u)/ai.openclaw.gateway" >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$(id -u)" "$GATEWAY_PLIST" >/dev/null 2>&1 || true
    launchctl kickstart -k "gui/$(id -u)/ai.openclaw.gateway" >/dev/null 2>&1 || true
    log "restored gateway plist from backup"
  fi
elif [[ "$(uname -s)" == "Linux" ]] && command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now openclaw-gateway-selfheal.timer >/dev/null 2>&1 || true
  rm -f "${HOME}/.config/systemd/user/openclaw-gateway-selfheal.timer"
  rm -f "${HOME}/.config/systemd/user/openclaw-gateway-selfheal.service"
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

rm -f "${OPENCLAW_HOME}/bin/patch.py"
rm -f "${OPENCLAW_HOME}/bin/setup-wizard.py"
rm -f "${OPENCLAW_HOME}/bin/wrapper.sh"
rm -f "${OPENCLAW_HOME}/bin/selfheal.sh"
rm -f "${OPENCLAW_HOME}/bin/postfix-apply"
rm -f "${OPENCLAW_HOME}/postfix-pack.example.json"

if [[ "$KEEP_CONFIG" -eq 0 ]]; then
  rm -f "$CONFIG_PATH"
fi

log "uninstall complete"
