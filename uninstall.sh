#!/usr/bin/env bash
set -euo pipefail
OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
CONFIG_PATH="$OPENCLAW_HOME/openclaw.json"

command -v openclaw >/dev/null 2>&1 || {
  echo "openclaw is required" >&2
  exit 1
}

openclaw plugins uninstall --force message-stamp-suffix || rm -rf "$OPENCLAW_HOME/extensions/message-stamp-suffix"
python3 - "$CONFIG_PATH" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
obj = json.loads(p.read_text())
messages = obj.get('messages', {})
if messages.get('responsePrefix') == '[[ocstamp:{provider}:{model}:{identityname}]]':
    messages.pop('responsePrefix', None)
plugins = obj.get('plugins', {})
entries = plugins.get('entries', {})
entries.pop('message-stamp-suffix', None)
allow = plugins.get('allow', [])
plugins['allow'] = [x for x in allow if x != 'message-stamp-suffix']
p.write_text(json.dumps(obj, indent=2) + '\n')
PY
if command -v openclaw >/dev/null 2>&1; then
  openclaw gateway restart >/dev/null 2>&1 || true
fi
echo "openclaw-postfix-pack v2 removed"
