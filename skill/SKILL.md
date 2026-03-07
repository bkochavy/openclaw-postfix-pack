# openclaw-postfix-pack v2

Use this tool when the user wants compact provider/model suffix stamps in OpenClaw replies without patching the upstream dist bundle.

## Core paths

- Plugin: `~/.openclaw/extensions/message-stamp-suffix/`
- Config: `~/.openclaw/openclaw.json`

## Core checks

```bash
openclaw plugins list | grep message-stamp-suffix
python3 - <<'PY'
import json, pathlib
p = pathlib.Path.home()/'.openclaw'/'openclaw.json'
obj = json.loads(p.read_text())
print(obj.get('messages', {}))
print(obj.get('plugins', {}).get('entries', {}).get('message-stamp-suffix'))
PY
```
