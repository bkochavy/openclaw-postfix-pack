# openclaw-postfix-pack

Stamp every OpenClaw message with the actual model that sent it.

`anK/s46-1m@A` -> anthropic, API key, sonnet-4-6, agent "A"

## Why

OpenClaw's `/status` can be wrong. This pack patches the runtime directly so the
truth appears at the end of every message. It also installs a self-heal that
re-applies after gateway restarts.

## Install (one command)

```bash
curl -fsSL https://raw.githubusercontent.com/USERNAME/openclaw-postfix-pack/main/install.sh | bash
```

Install flags:

```bash
bash install.sh --setup   # force setup wizard
bash install.sh --quiet   # non-interactive defaults
bash install.sh --check   # verify only
```

## Re-apply after OpenClaw update

```bash
~/.openclaw/bin/postfix-apply
```

Or tell your OpenClaw agent: `run ~/.openclaw/bin/postfix-apply`

## Customize

Edit `~/.openclaw/postfix-pack.json` or re-run:

```bash
bash install.sh --setup
```

## Format Options

1. Compact (recommended): `anK/s46-1m@A`
2. Bracket: `[anK|s46-1m|A]`
3. Model only: `s46-1m@A`
4. Custom: user-defined format string

## Stamp Decoder

| Segment | Meaning |
| --- | --- |
| `an` | Provider alias (example: anthropic) |
| `K` | Auth mode (`K` API key, `O` OAuth/token, `T` Vercel token path) |
| `s46-1m` | Model alias |
| `@A` | Identity shorthand |

## File Layout

```text
openclaw-postfix-pack/
├── install.sh
├── uninstall.sh
├── postfix-pack.example.json
├── README.md
├── scripts/
│   ├── patch.py
│   ├── setup-wizard.py
│   ├── selfheal.sh
│   └── wrapper.sh
└── templates/
    ├── launchd/
    └── systemd/
```

## Uninstall

```bash
bash uninstall.sh
```
