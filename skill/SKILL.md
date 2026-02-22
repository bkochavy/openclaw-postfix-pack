---
name: openclaw-postfix-pack
description: "Full operational runbook for openclaw-postfix-pack. Use when: user wants to manage, customize, or troubleshoot the model stamp that appears at the end of every OpenClaw message. Covers: changing stamp format, renaming model codes, adding new models, fixing a broken stamp after update, understanding what the stamp means, re-applying after OpenClaw update, and complete alias management."
---

# openclaw-postfix-pack — Agent Runbook

This pack stamps every OpenClaw reply with the actual model that sent it.
The stamp appears at the **end** of each message.

```
Your reply text here...

anK/s46-1m@A
```

Decoded:
```
an   — Anthropic          (provider alias)
K    — API Key            (auth type)
s46-1m — Sonnet 4.6 1M   (model alias)
@A   — Ava                (agent identity initial)
```

> **Auto-sync note:** Since v1.1.0, the gateway wrapper automatically runs
> `--sync-models` on every restart. New models in `openclaw.json` get aliases
> derived automatically. You only need this skill for manual overrides,
> format changes, or troubleshooting.

---

## Quick reference — what the user might say and what to do

| User says | What to do |
|-----------|------------|
| "change my stamp format" | → [Change the stamp format](#change-the-stamp-format) |
| "rename the model code for X" | → [Override a model alias](#override-a-model-alias) |
| "add an alias for my new model" | → [Add a custom alias](#add-a-custom-alias) |
| "my stamp broke after update" | → [Re-apply after OpenClaw update](#re-apply-after-openclaw-update) |
| "stamp shows full model name instead of short code" | → [Sync model aliases](#sync-model-aliases) |
| "what does my stamp mean?" | → [Decode the current stamp](#decode-the-current-stamp) |
| "show me all my aliases" | → [List current aliases](#list-current-aliases) |
| "check if the patch is working" | → [Verify the install](#verify-the-install) |
| "uninstall the stamp" | → [Uninstall](#uninstall) |
| "rerun setup" | → [Re-run the setup wizard](#re-run-the-setup-wizard) |

---

## Change the stamp format

Edit `~/.openclaw/postfix-pack.json` → `response_prefix_template`.

Available tokens: `{provider}` `{model}` `{identityname}` `{modelfull}` `{thinkinglevel}`

Format options:

| Style | Template | Example output |
|-------|----------|----------------|
| Compact (default) | `postfix:{provider}/{model}@{identityname}` | `anK/s46-1m@A` |
| Bracket | `postfix:[{provider}\|{model}\|{identityname}]` | `[anK\|s46-1m\|A]` |
| Model only | `postfix:{model}@{identityname}` | `s46-1m@A` |
| Full model name | `postfix:{modelfull}@{identityname}` | `anthropic/claude-sonnet-4-6@A` |
| With thinking level | `postfix:{model}({thinkinglevel})@{identityname}` | `s46-1m(high)@A` |

After editing, apply:

```bash
~/.openclaw/bin/postfix-apply
```

To run the interactive wizard instead:

```bash
python3 ~/.openclaw/bin/setup-wizard.py
```

---

## Override a model alias

To rename what a model shows as in the stamp — e.g. change `s46-1m` to `son46`:

Edit `~/.openclaw/postfix-pack.json` → `model_aliases`:

```json
{
  "model_aliases": {
    "claude-sonnet-4-6": "son46"
  }
}
```

Custom aliases in `postfix-pack.json` take precedence over built-ins.
After editing, force re-apply with the new alias:

```bash
OPENCLAW_PATCH_FORCE_MODELSTAMP=1 ~/.openclaw/bin/postfix-apply
```

---

## Add a custom alias

For a model not in the built-in list:

1. Find the short model name (strip provider prefix and date suffixes):
   - `openrouter/google/gemini-2.5-pro` → `gemini-2.5-pro`
   - `anthropic/claude-sonnet-4-5-20250929` → `claude-sonnet-4-5`

2. Derive a 2–5 char code (see naming convention below) or pick your own.

3. Add to `~/.openclaw/postfix-pack.json`:

```json
{
  "model_aliases": {
    "gemini-2.5-pro": "g25p",
    "my-custom-model": "mc1"
  }
}
```

4. Apply:

```bash
~/.openclaw/bin/postfix-apply
```

### Alias naming convention

| Family | Prefix | Example |
|--------|--------|---------|
| claude sonnet | `s` | `s46-1m` |
| claude opus | `o` | `o46` |
| claude haiku | `h` | `h45` |
| gemini | `g` | `g25f` |
| qwen | `q` | `q3mt` |
| glm | `g` | `g47` |
| deepseek | `ds` | `dsr1` |
| llama | `l` | `l4m` |
| mistral | `ms` | `ms31` |
| grok | `g` | `g41f` |
| gpt | (version only) | `52`, `53c` |
| minimax | `m` | `m25` |
| kimi | `k` | `k25` |
| seed | `sd` | `sd16` |

Variant suffixes: `f`=flash `p`=pro/plus `t`=thinking `m`=mini/max/maverick `s`=scout/small `c`=coder `1m`=1M context

---

## Sync model aliases

When stamps show full model names (e.g. `gemini-2.5-flash` instead of `g25f`):

```bash
~/.openclaw/bin/postfix-apply --sync-models
```

This reads all models from `openclaw.json` (primary + fallbacks), checks each against built-in and custom aliases, and auto-derives codes for any that are missing. Writes new entries to `postfix-pack.json` and re-applies.

To see what would be derived without writing:

```bash
~/.openclaw/bin/postfix-apply --sync-models --dry-run
```

---

## Re-apply after OpenClaw update

OpenClaw updates overwrite the patched bundles. The self-heal runs every 10 min
and on gateway restart, so it's usually automatic. If you need it immediately:

```bash
~/.openclaw/bin/postfix-apply
```

To force a full re-patch even if markers are present (use after alias map changes):

```bash
OPENCLAW_PATCH_FORCE_MODELSTAMP=1 ~/.openclaw/bin/postfix-apply
```

---

## Decode the current stamp

To see what a stamp segment means, check these tables:

**Auth letters:**

| Letter | Meaning |
|--------|---------|
| `K` | API key |
| `O` | OAuth / Anthropic token |
| `T` | Vercel AI Gateway token |
| `L` | Local model (LM Studio, Ollama) |
| `?` | Unknown / not resolved |

**Provider aliases:**

| Alias | Provider |
|-------|----------|
| `an` | anthropic |
| `or` | openrouter |
| `oa` | openai |
| `oc` | openai-codex |
| `xa` | xai |
| `lm` | lmstudio |
| `ve` | vercel-ai-gateway |

For OpenRouter, the stamp includes a source segment:
`orK.an/s46-1m@A` = OpenRouter → Anthropic, API key, Sonnet 4.6, agent A

---

## List current aliases

To see all active aliases (built-in + custom):

```bash
python3 - <<'PY'
import json, sys
from pathlib import Path

# Built-in aliases from patcher
patcher = Path.home() / '.openclaw/bin/patch.py'
builtin = {}
if patcher.exists():
    sys.path.insert(0, str(patcher.parent))
    try:
        from patch import DEFAULT_CONFIG
        builtin = DEFAULT_CONFIG.get('model_aliases', {})
    except Exception:
        pass

# Custom aliases from config
cfg_path = Path.home() / '.openclaw/postfix-pack.json'
custom = {}
if cfg_path.exists():
    doc = json.loads(cfg_path.read_text())
    custom = doc.get('model_aliases', {})

# Merge (custom overrides built-in)
merged = {**builtin, **custom}

print(f"Built-in: {len(builtin)}  Custom: {len(custom)}  Total: {len(merged)}")
print()
for model, alias in sorted(merged.items()):
    tag = " (custom)" if model in custom else ""
    print(f"  {alias:<10} {model}{tag}")
PY
```

---

## Verify the install

```bash
~/.openclaw/bin/postfix-apply --check-only
```

Exit codes:
- `0` — healthy, all bundles patched and config correct
- `3` — no target bundles found (OpenClaw version changed bundle naming)
- `4` — syntax validation failed on a bundle (reverted automatically)
- `5` — `responsePrefix` not in postfix mode in `openclaw.json`

To see exactly which bundles are patched without writing:

```bash
~/.openclaw/bin/postfix-apply --dry-run
```

---

## Change the identity initial

The `@A` segment comes from the agent's identity name in `openclaw.json`.
It's the first letter, uppercased. To change it, update the identity name
in `openclaw.json` → `agents.defaults.identity.name` (or however it's
configured for your agent), then restart the gateway.

No postfix-apply needed for this — the initial is derived at runtime from
the identity name, not stored in the stamp config.

---

## Add or change a provider alias

Edit `~/.openclaw/postfix-pack.json` → `provider_aliases`:

```json
{
  "provider_aliases": {
    "my-custom-provider": "cp"
  }
}
```

Force re-patch (aliases are baked into the dist bundles):

```bash
OPENCLAW_PATCH_FORCE_MODELSTAMP=1 ~/.openclaw/bin/postfix-apply
```

---

## Re-run the setup wizard

To change format, providers, or auth type interactively:

```bash
bash ~/.openclaw/workspace/projects/openclaw-postfix-pack/install.sh --setup
```

Or if the pack scripts are installed:

```bash
python3 ~/.openclaw/bin/setup-wizard.py
```

---

## Uninstall

From the pack directory:

```bash
bash uninstall.sh
```

This removes the self-heal timer, restores the gateway plist, and removes
installed scripts from `~/.openclaw/bin`. The config at
`~/.openclaw/postfix-pack.json` is preserved unless you pass `--restore-config`.

---

## Config file reference

Location: `~/.openclaw/postfix-pack.json`

Full schema:

```json
{
  "response_prefix_template": "postfix:{provider}/{model}@{identityname}",
  "model_aliases": {
    "my-model": "mm1"
  },
  "provider_aliases": {
    "my-provider": "mp"
  },
  "source_aliases": {
    "my-source": "ms"
  },
  "auth_mode_overrides": {
    "my-provider": { "api_key": "K" }
  },
  "fallback": {
    "provider_length": 2,
    "source_length": 2,
    "model_length": 12
  }
}
```

After any config change:
```bash
~/.openclaw/bin/postfix-apply
```
After alias map changes (forces rebuild of baked-in JS alias tables):
```bash
OPENCLAW_PATCH_FORCE_MODELSTAMP=1 ~/.openclaw/bin/postfix-apply
```

---

## Built-in model aliases (complete list)

These are active without any config changes. Add custom overrides only when
you want a different code than the built-in, or for models not in this list.

```
s46-1m  claude-sonnet-4-6          o46    claude-opus-4-6
s46     claude-sonnet-4.6          o46    claude-opus-4.6
s45     claude-sonnet-4-5          h45    claude-haiku-4-5
h46     claude-haiku-4-6           h46    claude-haiku-4.6
53c     gpt-5.3-codex              53cs   gpt-5.3-codex-spark
52c     gpt-5.2-codex              52     gpt-5.2
4o      gpt-4o                     4om    gpt-4o-mini
o3      o3                         o4m    o4-mini
g31p    gemini-3.1-pro-preview     g3f    gemini-3-flash-preview
g25p    gemini-2.5-pro             g25f   gemini-2.5-flash
g2f     gemini-2-flash             g2ft   gemini-2-flash-thinking
q35p    qwen3.5-plus-02-15         q35    qwen3.5-397b-a17b
q3mt    qwen3-max-thinking         q3cn   qwen3-coder-next
q3      qwen3-235b-a22b            q25c   qwen2.5-coder-32b-instruct
g5      glm-5                      g47    glm-4.7
g47f    glm-4.7-flash              g45    glm-4.5
k25     kimi-k2.5
m25     minimax-m2.5               m21    minimax-m2.1
m2h     minimax-m2-her
g4      grok-4                     g3     grok-3
g3m     grok-3-mini                g41f   grok-4-1-fast
g41fr   grok-4-1-fast-reasoning
dsr1    deepseek-r1                dsr1   deepseek-r1-0528
dsc     deepseek-chat              dsv3   deepseek-v3
dsv3    deepseek-v3-0324
l4m     llama-4-maverick           l4s    llama-4-scout
l33     llama-3.3-70b-instruct     l31    llama-3.1-405b-instruct
ml24    mistral-large-2407         ms31   mistral-small-3.1
mcs     codestral-2501
sd16    seed-1.6                   sd16f  seed-1.6-flash
tri     trinity-large-preview
sf35    step-3.5-flash
oc      opencode
```
