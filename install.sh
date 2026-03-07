#!/usr/bin/env bash
set -euo pipefail
OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
CONFIG_PATH="$OPENCLAW_HOME/openclaw.json"
SCRIPT_PATH="$(set +u; printf %s "${BASH_SOURCE[0]-}")"
SCRIPT_DIR=""
if [ -n "$SCRIPT_PATH" ] && [ -e "$SCRIPT_PATH" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
fi
TMP_REPO=""

cleanup() {
  if [ -n "$TMP_REPO" ] && [ -d "$TMP_REPO" ]; then
    rm -rf "$TMP_REPO"
  fi
}
trap cleanup EXIT

fetch_if_needed() {
  if [ -f "$SCRIPT_DIR/plugin/index.ts" ]; then
    return 0
  fi
  TMP_REPO="$(mktemp -d)"
  curl -fsSL "https://codeload.github.com/bkochavy/openclaw-postfix-pack/tar.gz/main" | tar -xz -C "$TMP_REPO"
  SCRIPT_DIR="$(find "$TMP_REPO" -mindepth 1 -maxdepth 1 -type d | head -1)"
}

command -v openclaw >/dev/null 2>&1 || {
  echo "openclaw is required" >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required" >&2
  exit 1
}

mkdir -p "$OPENCLAW_HOME"
[ -f "$CONFIG_PATH" ] || printf '{}\n' > "$CONFIG_PATH"
fetch_if_needed
openclaw plugins install "$SCRIPT_DIR/plugin"
python3 - "$CONFIG_PATH" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
obj = json.loads(p.read_text())
obj.setdefault('messages', {})['responsePrefix'] = '[[ocstamp:{provider}:{model}:{identityname}]]'
plugins = obj.setdefault('plugins', {})
allow = plugins.setdefault('allow', [])
if 'message-stamp-suffix' not in allow:
    allow.append('message-stamp-suffix')
entries = plugins.setdefault('entries', {})
entry = entries.setdefault('message-stamp-suffix', {'enabled': True})
entry['enabled'] = True
entry['config'] = {
    'marker': 'ocstamp',
    'separator': '\n',
    'identityMode': 'initial',
    'providerAliases': {
        'anthropic': 'anK',
        'claude-cli': 'anO',
        'codex-cli': 'opK',
        'lmstudio': 'lmL',
        'opencode': 'ocK',
        'openai-codex': 'opK',
        'openrouter': 'orK',
        'vercel-ai-gateway': 'veT',
        'xai': 'xaK'
    },
    'modelAliases': {
        'claude-haiku-4.5': 'h45',
        'claude-haiku-4-5': 'h45',
        'claude-opus-4.6': 'o46',
        'claude-opus-4-6': 'o46',
        'claude-sonnet-4.5': 's45',
        'claude-sonnet-4-5': 's45',
        'claude-sonnet-4.6': 's46',
        'claude-sonnet-4-6': 's46',
        'glm-5': 'g5',
        'gpt-5.2': 'gpt52',
        'gpt-5.3-codex': 'gpt53c',
        'gpt-5.3-codex-spark': 'gpt53s',
        'gpt-5.4': 'gpt54',
        'grok-4-1-fast': 'g41f',
        'haiku-4.6': 'h46',
        'kimi-k2.5': 'k25',
        'minimax-m2.5': 'm25',
        'opus-4.6': 'o46',
        'qwen3-8b-mlx': 'q38b',
        'sonnet-4.6': 's46'
    }
}

def strip_postfix(node):
    if isinstance(node, dict):
        for key in list(node.keys()):
            value = node[key]
            if key == 'responsePrefix' and isinstance(value, str) and value.startswith('postfix:'):
                del node[key]
                continue
            strip_postfix(value)
    elif isinstance(node, list):
        for item in node:
            strip_postfix(item)

strip_postfix(obj.get('channels', {}))
p.write_text(json.dumps(obj, indent=2) + '\n')
PY

launchctl bootout "gui/$(id -u)/ai.openclaw.gateway-selfheal" >/dev/null 2>&1 || true
launchctl disable "gui/$(id -u)/ai.openclaw.gateway-selfheal" >/dev/null 2>&1 || true
rm -f "$HOME/Library/LaunchAgents/ai.openclaw.gateway-selfheal.plist"
rm -f "$OPENCLAW_HOME/bin/patch.py" "$OPENCLAW_HOME/bin/ensure-openclaw-postfix-patch.py" "$OPENCLAW_HOME/bin/selfheal.sh" "$OPENCLAW_HOME/bin/wrapper.sh" "$OPENCLAW_HOME/bin/openclaw-gateway-wrapper.sh" "$OPENCLAW_HOME/bin/openclaw-gateway-selfheal.sh" "$OPENCLAW_HOME/bin/postfix-apply"
rm -f "$OPENCLAW_HOME/postfix-pack.json" "$OPENCLAW_HOME/postfix-pack.example.json"

if command -v openclaw >/dev/null 2>&1; then
  openclaw gateway restart >/dev/null 2>&1 || true
fi

echo "openclaw-postfix-pack v2 installed"
