---
name: postfix-aliases
description: "Manage OpenClaw postfix stamp model aliases. Use when: user adds a new model to openclaw.json and wants the stamp to show a short code instead of the full model name, or when the stamp shows an unrecognized model string."
---

# postfix-aliases

Use this skill when model stamps show long/unrecognized model IDs and the user wants short postfix codes.

## What this skill does

1. Detect model IDs used in `~/.openclaw/openclaw.json`
2. Compare them to built-in + custom aliases
3. Generate short aliases for missing models
4. Save custom aliases in `~/.openclaw/postfix-pack.json`
5. Apply and verify with `postfix-apply`

## Important rule: built-in vs custom aliases

Built-in aliases are shipped in the patcher (`scripts/patch.py` / `DEFAULT_CONFIG`) and already work without adding anything to `postfix-pack.json`.

Only add **custom aliases** to `~/.openclaw/postfix-pack.json` when a model is missing from built-ins.

## Detect the gap

Read models from OpenClaw config:

- Primary model: `agents.defaults.model.primary`
- Fallbacks: `agents.defaults.model.fallbacks[]`

Suggested command:

```bash
python3 - <<'PY'
import json
from pathlib import Path

cfg = json.loads(Path.home().joinpath('.openclaw/openclaw.json').read_text(encoding='utf-8'))
model_cfg = cfg.get('agents', {}).get('defaults', {}).get('model', {})
primary = model_cfg.get('primary')
fallbacks = model_cfg.get('fallbacks', [])

models = []
if isinstance(primary, str):
    models.append(primary)
if isinstance(fallbacks, list):
    models.extend([m for m in fallbacks if isinstance(m, str)])

print('\n'.join(models))
PY
```

Read current custom alias map:

```bash
python3 - <<'PY'
import json
from pathlib import Path

path = Path.home().joinpath('.openclaw/postfix-pack.json')
if path.exists():
    doc = json.loads(path.read_text(encoding='utf-8'))
else:
    doc = {}

aliases = doc.get('model_aliases', {})
if not isinstance(aliases, dict):
    aliases = {}

for k, v in sorted(aliases.items()):
    print(f"{k} -> {v}")
PY
```

Then find models with no alias in either:

- Built-in aliases (table below)
- `~/.openclaw/postfix-pack.json` -> `model_aliases`

## Derive a short code (2-6 chars)

Naming convention:

1. Start from model family shorthand, not full provider name.
2. Keep version numbers compact (`4.6 -> 46`, `3.5 -> 35`, `2.5 -> 25`).
3. Add a short variant suffix only if useful:
   - `f` = flash
   - `p` = pro / plus
   - `t` = thinking
   - `m` = mini / medium (if needed to disambiguate)
   - `1m` = 1M context
4. Prefer lowercase alphanumerics.
5. Keep it memorable and avoid collisions with existing aliases.

### Examples (breakdowns)

1. `claude-sonnet-4-6` -> `s46-1m` (`s` sonnet + `46` + `1m` context)
2. `claude-opus-4-6` -> `o46` (`o` opus + `46`)
3. `gemini-3.1-pro-preview` -> `g31p` (`g` gemini + `31` + `p` pro)
4. `gemini-2.5-flash` -> `g25f` (`g` + `25` + `f` flash)
5. `qwen3.5-plus-02-15` -> `q35p` (`q` + `35` + `p` plus)
6. `qwen3-max-thinking` -> `q3mt` (`q3` + `m` max + `t` thinking)
7. `glm-4.7-flash` -> `g47f` (`g` + `47` + `f`)
8. `deepseek-r1` -> `dsr1` (`ds` deepseek + `r1`)
9. `llama-4-maverick` -> `l4m` (`l` llama + `4` + `m` maverick)
10. `mistral-small-3.1` -> `ms31` (`ms` mistral-small + `31`)
11. `seed-1.6-flash` -> `sd16f` (`sd` seed + `16` + `f`)
12. `grok-3-mini` -> `g3m` (`g` grok + `3` + `m` mini)

## Add the alias

Write custom aliases to `~/.openclaw/postfix-pack.json` under `model_aliases`.

Example edit shape:

```json
{
  "model_aliases": {
    "gemini-2-flash": "g2f",
    "my-custom-v3": "mc3"
  }
}
```

If file already exists, merge instead of overwriting unrelated keys.

## Apply

```bash
~/.openclaw/bin/postfix-apply
```

## Verify

```bash
~/.openclaw/bin/postfix-apply --dry-run
```

Confirm the model now resolves to the short alias and appears correctly in dry-run output/stamp preview.

## Built-in model alias table (from DEFAULT_CONFIG)

```json
{
  "claude-haiku-4-5": "h45",
  "claude-haiku-4-6": "h46",
  "claude-haiku-4.6": "h46",
  "claude-opus-4-6": "o46",
  "claude-opus-4.6": "o46",
  "claude-sonnet-4-5": "s45",
  "claude-sonnet-4-6": "s46-1m",
  "claude-sonnet-4.6": "s46",
  "codestral-2501": "mcs",
  "deepseek-chat": "dsc",
  "deepseek-r1": "dsr1",
  "deepseek-r1-0528": "dsr1",
  "deepseek-v3": "dsv3",
  "deepseek-v3-0324": "dsv3",
  "gemini-2-flash": "g2f",
  "gemini-2-flash-thinking": "g2ft",
  "gemini-2.5-flash": "g25f",
  "gemini-2.5-pro": "g25p",
  "gemini-3-flash-preview": "g3f",
  "gemini-3.1-pro-preview": "g31p",
  "glm-4.5": "g45",
  "glm-4.7": "g47",
  "glm-4.7-flash": "g47f",
  "glm-5": "g5",
  "gpt-4o": "4o",
  "gpt-4o-mini": "4om",
  "gpt-5.2": "52",
  "gpt-5.2-codex": "52c",
  "gpt-5.3-codex": "53c",
  "gpt-5.3-codex-spark": "53cs",
  "grok-3": "g3",
  "grok-3-mini": "g3m",
  "grok-4": "g4",
  "grok-4-1-fast": "g41f",
  "grok-4-1-fast-reasoning": "g41fr",
  "kimi-k2.5": "k25",
  "llama-3.1-405b-instruct": "l31",
  "llama-3.3-70b-instruct": "l33",
  "llama-4-maverick": "l4m",
  "llama-4-scout": "l4s",
  "minimax-m2-her": "m2h",
  "minimax-m2.1": "m21",
  "minimax-m2.5": "m25",
  "mistral-large-2407": "ml24",
  "mistral-small-3.1": "ms31",
  "o3": "o3",
  "o4-mini": "o4m",
  "opencode": "oc",
  "qwen2.5-coder-32b-instruct": "q25c",
  "qwen3-235b-a22b": "q3",
  "qwen3-coder-next": "q3cn",
  "qwen3-max-thinking": "q3mt",
  "qwen3.5-397b-a17b": "q35",
  "qwen3.5-plus-02-15": "q35p",
  "seed-1.6": "sd16",
  "seed-1.6-flash": "sd16f",
  "step-3.5-flash": "sf35",
  "trinity-large-preview": "tri"
}
```

## Operational note

For OpenRouter/Anthropic Claude naming differences, normalize thoughtfully:

- OpenRouter often uses dot versions (`claude-sonnet-4.6`)
- Anthropic direct often uses dash versions (`claude-sonnet-4-6`)

When adding custom aliases, include both forms if your environment emits both.
