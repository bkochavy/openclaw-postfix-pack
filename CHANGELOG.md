# Changelog

## v1.1.1 — 2026-02-24
- Fix auth-letter fallback detection to respect `cfg.auth.order[provider]` before `${provider}:default` when runtime auth store lookup is unavailable

## v1.1.0 — 2026-02-22
- `--sync-models`: auto-derives aliases for new models on every gateway restart
- `--dry-run` flag: preview what would be patched without writing
- `--check-only` flag: verify install health, exit code indicates status
- Setup wizard: auto-detects primary model from openclaw.json
- Setup wizard: acronym-style stamp decoder at first run
- Redesigned onboarding explainer with auth letter definitions
- Expanded built-in model aliases: 50+ models including top OpenRouter picks
- Hardened `resolve_openclaw_pkg_dir()`: pnpm + npm fallback chains
- Exit code 3 escape hatch: prints copy-paste Claude Code/Codex prompt when bundle layout changes
- `postfix-aliases` skill: full operational runbook for agents
- Sandbox test suite (`tests/test_install.sh`, `tests/test_stamp.mjs`)

## v1.0.0 — 2026-02-21
- Initial release
- Postfix stamp on every OpenClaw Telegram message
- Marker-based idempotent patcher (reply, pi-embedded, subagent-registry bundles)
- macOS launchd + Linux systemd self-heal
- Setup wizard with provider/auth/format selection
- One-liner install (`curl | bash`)
