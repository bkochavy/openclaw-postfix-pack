#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_HOME="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME"' EXIT

mkdir -p "$TMP_HOME/.openclaw"
cat >"$TMP_HOME/.openclaw/openclaw.json" <<'JSON'
{}
JSON

HOME="$TMP_HOME" bash "$REPO_ROOT/install.sh"

python3 - "$TMP_HOME/.openclaw/openclaw.json" <<'PY'
import json, sys
obj = json.load(open(sys.argv[1], "r", encoding="utf-8"))
assert obj["messages"]["responsePrefix"] == "[[ocstamp:{provider}:{model}:{identityname}]]"
assert obj["plugins"]["entries"]["message-stamp-suffix"]["enabled"] is True
assert obj["plugins"]["installs"]["message-stamp-suffix"]["source"] == "path"
print("message-stamp-suffix install smoke ok")
PY
