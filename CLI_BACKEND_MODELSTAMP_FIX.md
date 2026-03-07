# CLI Backend Modelstamp Fix

This repository now defaults to the alias-template stamp shape for CLI backends:

- `codex-cli/gpt-5.4` -> `opcli/gpt54@A`
- `claude-cli/opus-4.6` -> `ancli/o46@A`

## Why

Recent OpenClaw bundles expose raw `{provider}` and `{model}` tokens, but that path does not rebuild the compact CLI-family stamps many OpenClaw setups expect. The reliable fix is:

- use `postfix:{provideralias}/{alias}@{identityname}`
- set `provider_aliases.codex-cli = "opcli"`
- set `provider_aliases.claude-cli = "ancli"`
- keep compact `model_aliases` such as `gpt54`, `gpt53c`, `o46`, and `s46`

## Verification

After patching and restarting the gateway, confirm the rendered stamp map includes:

- `codex-cli/gpt-5.4` -> `opcli/gpt54@A`
- `codex-cli/gpt-5.3-codex` -> `opcli/gpt53c@A`
- `claude-cli/opus-4.6` -> `ancli/o46@A`
- `claude-cli/sonnet-4.6` -> `ancli/s46@A`
