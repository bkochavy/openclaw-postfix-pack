#!/usr/bin/env bash
set -euo pipefail

FORCE_SETUP=0
QUIET=0
CHECK_ONLY=0

usage() {
  cat <<'EOF'
Usage: bash install.sh [--setup] [--quiet] [--check]

  --setup   Force setup wizard even if config already exists
  --quiet   Non-interactive defaults
  --check   Verify current install only (no writes)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --setup)
      FORCE_SETUP=1
      ;;
    --quiet)
      QUIET=1
      ;;
    --check)
      CHECK_ONLY=1
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

die() {
  log "ERROR: $*"
  exit 1
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    die "required command not found: $cmd"
  fi
}

os_name() {
  uname -s
}

ensure_dir() {
  mkdir -p "$1"
}

latest_file() {
  local pattern="$1"
  ls -1t ${pattern} 2>/dev/null | head -n 1 || true
}

OPENCLAW_HOME="${OPENCLAW_HOME:-${HOME}/.openclaw}"
BIN_DIR="${OPENCLAW_HOME}/bin"
BACKUP_DIR="${OPENCLAW_HOME}/backups"
LOG_DIR="${OPENCLAW_HOME}/logs"
CONFIG_PATH="${OPENCLAW_POSTFIX_CONFIG:-${OPENCLAW_HOME}/postfix-pack.json}"
OPENCLAW_JSON="${OPENCLAW_JSON:-${OPENCLAW_HOME}/openclaw.json}"

PACK_ROOT=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd 2>/dev/null || pwd)"
if [[ -f "${SCRIPT_DIR}/scripts/patch.py" ]]; then
  PACK_ROOT="${SCRIPT_DIR}"
elif [[ -f "${PWD}/scripts/patch.py" ]]; then
  PACK_ROOT="${PWD}"
fi

TMP_PACK_DIR=""
cleanup_tmp() {
  if [[ -n "${TMP_PACK_DIR}" && -d "${TMP_PACK_DIR}" ]]; then
    rm -rf "${TMP_PACK_DIR}"
  fi
}
trap cleanup_tmp EXIT

fetch_pack_if_needed() {
  if [[ -n "${PACK_ROOT}" ]]; then
    return
  fi

  local repo_slug="${OPENCLAW_POSTFIX_REPO:-bkochavy/openclaw-postfix-pack}"
  local repo_ref="${OPENCLAW_POSTFIX_REF:-main}"

  TMP_PACK_DIR="$(mktemp -d)"
  local archive_url="https://codeload.github.com/${repo_slug}/tar.gz/${repo_ref}"
  log "Fetching pack source from ${archive_url}"
  curl -fsSL "${archive_url}" | tar -xz -C "${TMP_PACK_DIR}"
  PACK_ROOT="$(find "${TMP_PACK_DIR}" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  [[ -n "${PACK_ROOT}" ]] || die "Failed to unpack repository archive"
}

render_template() {
  local src="$1"
  local dst="$2"
  sed \
    -e "s|__HOME__|${HOME}|g" \
    -e "s|__PATH__|${PATH}|g" \
    -e "s|__OPENCLAW_HOME__|${OPENCLAW_HOME}|g" \
    -e "s|__CONFIG_PATH__|${CONFIG_PATH}|g" \
    "$src" >"$dst"
}

install_payload() {
  ensure_dir "$BIN_DIR"
  ensure_dir "$BACKUP_DIR"
  ensure_dir "$LOG_DIR"

  install -m 0755 "${PACK_ROOT}/scripts/patch.py" "${BIN_DIR}/patch.py"
  install -m 0755 "${PACK_ROOT}/scripts/setup-wizard.py" "${BIN_DIR}/setup-wizard.py"
  install -m 0755 "${PACK_ROOT}/scripts/wrapper.sh" "${BIN_DIR}/wrapper.sh"
  install -m 0755 "${PACK_ROOT}/scripts/selfheal.sh" "${BIN_DIR}/selfheal.sh"
  install -m 0644 "${PACK_ROOT}/postfix-pack.example.json" "${OPENCLAW_HOME}/postfix-pack.example.json"

  cat >"${BIN_DIR}/postfix-apply" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
OPENCLAW_HOME="${OPENCLAW_HOME:-${HOME}/.openclaw}"
exec python3 "${OPENCLAW_HOME}/bin/patch.py" "$@"
EOF
  chmod 0755 "${BIN_DIR}/postfix-apply"
}

run_setup_wizard() {
  local wizard="${BIN_DIR}/setup-wizard.py"
  local cmd=(python3 "$wizard" --config "$CONFIG_PATH")

  if [[ "$QUIET" -eq 1 ]]; then
    cmd+=(--quiet)
    "${cmd[@]}"
    return
  fi

  if [[ -r /dev/tty ]]; then
    "${cmd[@]}" </dev/tty
  else
    log "No TTY available; running setup wizard with defaults"
    cmd+=(--quiet)
    "${cmd[@]}"
  fi
}

wire_macos() {
  local launchd_dir="${HOME}/Library/LaunchAgents"
  local selfheal_plist="${launchd_dir}/ai.openclaw.gateway-selfheal.plist"
  local gateway_plist="${launchd_dir}/ai.openclaw.gateway.plist"
  local ts
  ts="$(date -u +"%Y%m%d-%H%M%S")"

  ensure_dir "$launchd_dir"

  if [[ -f "$gateway_plist" ]]; then
    cp "$gateway_plist" "${BACKUP_DIR}/ai.openclaw.gateway.plist.postfix-pack.${ts}.bak"
    /usr/libexec/PlistBuddy -c "Delete :ProgramArguments" "$gateway_plist" >/dev/null 2>&1 || true
    /usr/libexec/PlistBuddy -c "Add :ProgramArguments array" "$gateway_plist"
    /usr/libexec/PlistBuddy -c "Add :ProgramArguments:0 string ${BIN_DIR}/wrapper.sh" "$gateway_plist"

    launchctl bootout "gui/$(id -u)/ai.openclaw.gateway" >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$(id -u)" "$gateway_plist" >/dev/null 2>&1 || true
    launchctl kickstart -k "gui/$(id -u)/ai.openclaw.gateway" >/dev/null 2>&1 || true
  else
    log "gateway plist not found at ${gateway_plist}; wrapper installed but not wired"
  fi

  render_template \
    "${PACK_ROOT}/templates/launchd/ai.openclaw.gateway-selfheal.plist.template" \
    "$selfheal_plist"

  launchctl bootout "gui/$(id -u)/ai.openclaw.gateway-selfheal" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "$selfheal_plist" >/dev/null 2>&1 || true
  launchctl kickstart -k "gui/$(id -u)/ai.openclaw.gateway-selfheal" >/dev/null 2>&1 || true
}

wire_linux() {
  if ! command -v systemctl >/dev/null 2>&1; then
    log "systemctl not found; skipped systemd selfheal wiring"
    return
  fi

  local systemd_user_dir="${HOME}/.config/systemd/user"
  ensure_dir "$systemd_user_dir"

  render_template \
    "${PACK_ROOT}/templates/systemd/openclaw-gateway-selfheal.service" \
    "${systemd_user_dir}/openclaw-gateway-selfheal.service"

  cp "${PACK_ROOT}/templates/systemd/openclaw-gateway-selfheal.timer" \
    "${systemd_user_dir}/openclaw-gateway-selfheal.timer"

  systemctl --user daemon-reload
  systemctl --user enable --now openclaw-gateway-selfheal.timer >/dev/null 2>&1 || true
}

verify_install() {
  local patcher_path="$1"
  local failures=0

  if [[ ! -f "$OPENCLAW_JSON" ]]; then
    log "verify: missing openclaw config ${OPENCLAW_JSON}"
    failures=$((failures + 1))
  fi

  if [[ ! -x "$patcher_path" ]]; then
    log "verify: patcher not executable ${patcher_path}"
    failures=$((failures + 1))
  fi

  if [[ -f "$OPENCLAW_JSON" ]]; then
    if ! python3 - "$OPENCLAW_JSON" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
doc = json.loads(path.read_text(encoding="utf-8"))
errors = []
any_channel_ok = False
channels = doc.get("channels", {})
for ch_val in channels.values():
    if not isinstance(ch_val, dict):
        continue
    if isinstance(ch_val.get("responsePrefix"), str) and ch_val["responsePrefix"].startswith("postfix:"):
        any_channel_ok = True
        break
    accounts = ch_val.get("accounts", {})
    if isinstance(accounts, dict):
        for acc in accounts.values():
            if isinstance(acc, dict) and isinstance(acc.get("responsePrefix"), str) and acc["responsePrefix"].startswith("postfix:"):
                any_channel_ok = True
                break
    if any_channel_ok:
        break

if not any_channel_ok:
    errors.append("no channel has responsePrefix in postfix mode")
if errors:
    print("\n".join(errors))
    raise SystemExit(1)
PY
    then
      log "verify: responsePrefix checks failed"
      failures=$((failures + 1))
    fi
  fi

  if ! python3 "$patcher_path" --config "$CONFIG_PATH" --openclaw-json "$OPENCLAW_JSON" --check-only >/tmp/openclaw-postfix-verify.log 2>&1; then
    log "verify: patch check failed"
    cat /tmp/openclaw-postfix-verify.log >&2 || true
    failures=$((failures + 1))
  fi

  if [[ "$(os_name)" == "Darwin" ]]; then
    local gateway_plist="${HOME}/Library/LaunchAgents/ai.openclaw.gateway.plist"
    local expected_prog="${OPENCLAW_HOME}/bin/wrapper.sh"
    if [[ -f "$gateway_plist" ]]; then
      local current_prog
      current_prog="$(/usr/libexec/PlistBuddy -c "Print :ProgramArguments:0" "$gateway_plist" 2>/dev/null || true)"
      if [[ "$current_prog" != "$expected_prog" ]]; then
        log "verify: gateway ProgramArguments not using wrapper"
        failures=$((failures + 1))
      fi
    fi
  elif [[ "$(os_name)" == "Linux" ]] && command -v systemctl >/dev/null 2>&1; then
    if ! systemctl --user is-enabled openclaw-gateway-selfheal.timer >/dev/null 2>&1; then
      log "verify: selfheal timer not enabled"
      failures=$((failures + 1))
    fi
  fi

  if [[ "$failures" -gt 0 ]]; then
    die "verification failed (${failures} issue(s))"
  fi
}

fetch_pack_if_needed

require_cmd bash
require_cmd python3

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  patcher_for_check="${OPENCLAW_HOME}/bin/patch.py"
  if [[ ! -x "$patcher_for_check" ]]; then
    patcher_for_check="${PACK_ROOT}/scripts/patch.py"
  fi
  verify_install "$patcher_for_check"
  log "check: PASS"
  exit 0
fi

if [[ ! -f "$OPENCLAW_JSON" ]]; then
  die "openclaw config not found: ${OPENCLAW_JSON}"
fi

install_payload

# Run initial model sync from openclaw.json if it exists
if [[ -f "$OPENCLAW_JSON" ]]; then
  "${BIN_DIR}/postfix-apply" --config "$CONFIG_PATH" --sync-models --openclaw-json "$OPENCLAW_JSON" 2>/dev/null || true
fi

if [[ "$FORCE_SETUP" -eq 1 || ! -f "$CONFIG_PATH" ]]; then
  run_setup_wizard
else
  log "Using existing config ${CONFIG_PATH}"
fi

if [[ "$(os_name)" == "Darwin" ]]; then
  wire_macos
elif [[ "$(os_name)" == "Linux" ]]; then
  wire_linux
fi

"${BIN_DIR}/postfix-apply" --config "$CONFIG_PATH" --openclaw-json "$OPENCLAW_JSON"
verify_install "${BIN_DIR}/patch.py"

echo "✅ Done. Every reply will end with: anK/s46-1m@A (example)"
