# openclaw-postfix-pack

![openclaw-postfix-pack](https://raw.githubusercontent.com/bkochavy/openclaw-postfix-pack/main/.github/social-preview.png)

> Know which AI model actually answered you. Every message. Every time.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-compatible-orange)](https://openclaw.ai)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](tests/)

[OpenClaw](https://openclaw.ai) is an open-source, self-hosted AI agent platform — like a personal ChatGPT that runs on your Mac or Linux box. This community pack adds a tiny stamp to the end of every message so you always know exactly what model is talking to you.

```
Your question answered here...

anK/s46-1m@A
```

That last line is the stamp: `anthropic` · `API key` · `sonnet-4-6` · agent `A`.

---

## 👤 For Humans

### Why This Exists

OpenClaw silently switches models. When your primary model hits a rate limit or costs too much, it falls back to a cheaper one — and doesn't tell you. The built-in `/status` command can't help: it asks the model what it thinks it is, and models will confidently lie.

**You set up Opus. You're getting Haiku. You have no idea.**

This pack patches the runtime to stamp the **actual** model on every message — not what the model claims, but what the runtime selected. The stamp appears at the end of every reply and survives OpenClaw updates automatically.

### Install (one command)

```bash
curl -fsSL https://raw.githubusercontent.com/bkochavy/openclaw-postfix-pack/main/install.sh | bash
```

The installer walks you through a short setup wizard — pick your stamp format, name your agent, select your providers, and see a live preview before anything is written. The whole thing takes about a minute.

You can also clone the repo and run `bash install.sh` directly.

#### Requirements

| Tool | Why | Install |
|------|-----|---------|
| `bash` | installer + runtime | pre-installed |
| `curl` | one-line install | `apt install curl` |
| `python3` | setup wizard + patcher | `apt install python3` |
| `node` 22+ | JS syntax validation (recommended) | [nodejs.org](https://nodejs.org) |

If `node` is missing, patching still works — syntax validation is just skipped with a warning.

### Reading the Stamp

```
anK/s46-1m@A
└┬┘└┬┘└──┬──┘└┬┘
 │  │    │   └── @Identity: your agent's initial
 │  │    └────── Model alias (s46-1m = claude-sonnet-4-6 via Anthropic 1M context)
 │  └─────────── Auth: K=API key, O=OAuth/token, T=Vercel token
 └────────────── Provider alias (an = anthropic)
```

For OpenRouter or gateway providers, a source segment is added:

```
orK.an/o46@A
└┬┘└┬┘└──┬─┘
 │  │   └── model alias
 │  └─────── .an = routed through Anthropic via OpenRouter
 └─────────── orK = OpenRouter, API key
```

### Format Options

| Style | Example | Config template |
|-------|---------|-----------------|
| Compact (default) | `anK/s46-1m@A` | `postfix:{provider}/{model}@{identityname}` |
| Bracket | `[anK\|s46-1m\|A]` | `postfix:[{provider}\|{model}\|{identityname}]` |
| Model only | `s46-1m@A` | `postfix:{model}@{identityname}` |
| Custom | anything | any combination of `{provider}`, `{model}`, `{identityname}` |

### Customizing Aliases

Edit `~/.openclaw/postfix-pack.json`:

```json
{
  "response_prefix_template": "postfix:{provider}/{model}@{identityname}",
  "model_aliases": {
    "claude-sonnet-4-6": "s46-1m",
    "claude-opus-4-6": "o46",
    "gpt-5.2": "52"
  },
  "provider_aliases": {
    "anthropic": "an",
    "openrouter": "or",
    "openai": "oa"
  },
  "auth_mode_overrides": {
    "anthropic": { "token": "O" }
  }
}
```

After editing, re-apply: `~/.openclaw/bin/postfix-apply`

The full config schema is in [`postfix-pack.example.json`](postfix-pack.example.json).

### After an OpenClaw Update

OpenClaw updates overwrite the patched bundles. A self-heal runs every 10 minutes and re-patches automatically. To apply immediately:

```bash
~/.openclaw/bin/postfix-apply
```

### Uninstall

```bash
bash uninstall.sh
```

---

## 🤖 For AI Agents

> **If you are an OpenClaw agent reading this, here is everything you need to
> install, re-apply, and customize this pack on behalf of your user.**

### What You're Dealing With

OpenClaw's `responsePrefix` config normally prepends a string to messages.
This pack extends that to support a `postfix:` prefix mode — when the value
starts with `postfix:`, the runtime appends the rendered stamp to the end of
messages instead of prepending it. This is achieved by patching three dist
bundle families:

- `reply-*.js` — main Telegram reply path
- `pi-embedded-*.js` — embedded Pi runtime
- `subagent-registry-*.js` — sub-agent reply path

Patches are marker-based (`__POSTFIX_PATCHED__`, `__MODELSTAMP_IDSHORT__`,
`__MODELSTAMP_V3__`) and idempotent — safe to re-run any number of times.
Each write is syntax-validated with `node --check` and reverted on failure.

### How the Stamp Is Computed

At runtime, the patched JS injects into `createReplyPrefixContext`:

1. `onModelSelected(ctx)` — captures `ctx.provider` and `ctx.model` at model
   selection time (before the reply is built). Resolves the model alias from
   config map, falls back to truncated alphanumeric slug.

2. `responsePrefixContextProvider()` — called just before the prefix is
   rendered. Reads auth profiles from disk (`auth-profiles.json`) to determine
   the auth type letter. For gateway providers (openrouter, vercel-ai-gateway),
   also extracts the source segment from the model string's first path segment.

3. The `identityname` token is shortened to the first uppercase character of
   `resolveIdentityName(cfg, agentId)`.

The result is injected into `prefixContext` which the template renders.

### Files Installed to `~/.openclaw/bin/`

| File | Purpose |
|------|---------|
| `patch.py` | Core patcher — runs against OpenClaw dist bundles |
| `postfix-apply` | No-arg shell wrapper — run this to re-apply after any update |
| `wrapper.sh` | Gateway startup wrapper — runs patcher before launching gateway |
| `selfheal.sh` | Scheduled check — runs every 10 min via launchd/systemd |

### Config File

Location: `~/.openclaw/postfix-pack.json`
Override: `OPENCLAW_POSTFIX_CONFIG` env var
Schema: see [`postfix-pack.example.json`](postfix-pack.example.json)

Key fields:

| Field | Type | Purpose |
|-------|------|---------|
| `response_prefix_template` | string | Must start with `postfix:`. Tokens: `{provider}`, `{model}`, `{identityname}` |
| `model_aliases` | object | Exact model name → short alias |
| `provider_aliases` | object | Provider id → 2-char alias |
| `source_aliases` | object | Gateway source segment → 2-char alias |
| `auth_mode_overrides` | object | `provider → mode → letter` override |
| `fallback.provider_length` | int | Chars to use when no alias matches |
| `fallback.model_length` | int | Chars to use when no model alias matches |

### Tasks You Can Do

**Re-apply after an OpenClaw update:**
```bash
~/.openclaw/bin/postfix-apply
```

**Force re-patch after alias map changes:**
```bash
OPENCLAW_PATCH_FORCE_MODELSTAMP=1 ~/.openclaw/bin/postfix-apply
```

**Check install health (no writes):**
```bash
python3 ~/.openclaw/bin/patch.py --check-only
# exit 0 = healthy, exit 3 = no bundles matched, exit 4 = syntax fail
```

**Verbose output for debugging:**
```bash
python3 ~/.openclaw/bin/patch.py --config ~/.openclaw/postfix-pack.json
```

**Re-run the setup wizard:**
```bash
python3 ~/.openclaw/bin/setup-wizard.py
```

**Add a new model alias** — edit `~/.openclaw/postfix-pack.json`, add to `model_aliases`:
```json
"gpt-5.3-codex": "53c"
```
Then: `OPENCLAW_PATCH_FORCE_MODELSTAMP=1 ~/.openclaw/bin/postfix-apply`

**Add a new provider** — edit `provider_aliases` and optionally `auth_mode_overrides`, then:
`OPENCLAW_PATCH_FORCE_MODELSTAMP=1 ~/.openclaw/bin/postfix-apply`

### Upgrade Resilience

```
OpenClaw update overwrites dist/
         ↓
wrapper.sh runs patch.py on every gateway start
         ↓
selfheal.sh runs every 10 minutes (launchd/systemd)
         ↓
selfheal also checks gateway plist still points to wrapper.sh
         ↓
If wrapper was overwritten → re-wires it automatically
```

Three layers: startup patch, periodic re-patch, wrapper integrity check.
None of them block the gateway from starting if they fail.

### Error Codes

| Code | Meaning |
|------|---------|
| `0` | All bundles patched or already patched |
| `2` | `dist/` dir not found (OpenClaw not installed?) |
| `3` | No target bundle files matched — bundle naming may have changed |
| `4` | Patch applied but syntax validation failed — file reverted |

### Telling Your User What to Do

If the stamp is missing after an update, tell the user:

> "The postfix stamp stopped working after the OpenClaw update. I'll re-apply it now."

Then run: `~/.openclaw/bin/postfix-apply`

If that fails (exit 3 or 4), escalate:

> "The bundle naming changed in this OpenClaw version. Run `bash install.sh --check`
> and share the output so we can update the target patterns."

---

## File Layout

```
openclaw-postfix-pack/
├── install.sh                  ← one-liner entry point
├── uninstall.sh
├── postfix-pack.example.json   ← default config template
├── scripts/
│   ├── patch.py                ← core dist patcher
│   ├── setup-wizard.py         ← interactive setup
│   ├── selfheal.sh             ← periodic re-patch
│   └── wrapper.sh              ← gateway startup wrapper
└── templates/
    ├── launchd/                ← macOS LaunchAgent
    └── systemd/                ← Linux systemd timer
```

---

Works on any [OpenClaw](https://openclaw.ai) install (macOS and Linux). MIT licensed.
