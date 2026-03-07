# openclaw-postfix-pack

V2 of the model stamp system for OpenClaw.

This version does **not** patch OpenClaw dist files and does **not** rewrite the gateway service. Instead it:
- uses native `messages.responsePrefix` to emit a structured marker with the real provider and model
- installs a tiny local plugin that converts that marker into a compact suffix
- keeps alias maps in one plugin config block inside `openclaw.json`

Example suffixes:
- `codex-cli/gpt-5.4 -> opK/gpt54@A`
- `claude-cli/opus-4.6 -> anO/o46@A`

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/bkochavy/openclaw-postfix-pack/main/install.sh | bash
```

## What V2 installs

- `~/.openclaw/extensions/message-stamp-suffix/`
- `messages.responsePrefix = "[[ocstamp:{provider}:{model}:{identityname}]]"`
- plugin allowlist + plugin config entry in `~/.openclaw/openclaw.json`

## Why V2 is better

- no dist patching
- no wrapper script
- no self-heal daemon
- survives OpenClaw updates cleanly
- suffix uses the real provider/model chosen at runtime

## Uninstall

```bash
bash uninstall.sh
```

## Notes

This package removes legacy postfix-pack v1 artifacts if they are present:
- old patcher scripts
- wrapper scripts
- self-heal launch agent / timer
- `postfix:` responsePrefix config
