#!/usr/bin/env python3
"""Interactive setup wizard for OpenClaw postfix-pack configuration."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

from patch import DEFAULT_CONFIG, deep_merge, ensure_postfix_template

PROVIDER_OPTIONS = [
    ("anthropic", "anthropic"),
    ("openai", "openai"),
    ("openrouter", "openrouter"),
    ("xai", "xai"),
    ("lmstudio", "lmstudio"),
    ("other", "other"),
]

PROVIDER_ALIASES = {
    "anthropic": "an",
    "openai": "oa",
    "openrouter": "or",
    "xai": "xa",
    "lmstudio": "lm",
    "vercel-ai-gateway": "ve",
}

AUTH_CHOICES = [
    ("api_key", "API key"),
    ("oauth", "OAuth"),
    ("token", "token"),
]

FORMAT_OPTIONS = {
    "compact": "{provider}/{model}@{identity}",
    "bracket": "[{provider}|{model}|{identity}]",
    "minimal": "{model}@{identity}",
}


def parse_args() -> argparse.Namespace:
    default_cfg = Path.home() / ".openclaw" / "postfix-pack.json"
    parser = argparse.ArgumentParser(description="Guided setup for postfix-pack config")
    parser.add_argument("--config", default=str(default_cfg))
    parser.add_argument("--openclaw-json", help="Path to openclaw.json (default: auto-detect)")
    parser.add_argument("--quiet", action="store_true", help="Use defaults without prompts")
    parser.add_argument("--no-apply", action="store_true", help="Write config but do not apply patch")
    return parser.parse_args()


def prompt_choice(prompt: str, options: list[str], default_index: int = 0) -> int:
    while True:
        print(prompt)
        for idx, item in enumerate(options, start=1):
            default_tag = " (default)" if idx - 1 == default_index else ""
            print(f"  {idx}) {item}{default_tag}")
        raw = input(f"Select [1-{len(options)}] (default {default_index + 1}): ").strip()
        if not raw:
            return default_index
        if raw.isdigit():
            val = int(raw)
            if 1 <= val <= len(options):
                return val - 1
        print("Invalid choice. Try again.\n")


def prompt_multi_select(prompt: str, options: list[tuple[str, str]], default: list[str]) -> list[str]:
    labels = [f"{key} ({label})" for key, label in options]
    default_indexes = [str(i + 1) for i, (key, _) in enumerate(options) if key in default]

    while True:
        print(prompt)
        for idx, label in enumerate(labels, start=1):
            print(f"  {idx}) {label}")
        raw = input(f"Select comma-separated numbers (default {','.join(default_indexes)}): ").strip()
        if not raw:
            return default

        selected: list[str] = []
        ok = True
        for part in raw.split(","):
            item = part.strip()
            if not item.isdigit():
                ok = False
                break
            idx = int(item)
            if idx < 1 or idx > len(options):
                ok = False
                break
            key = options[idx - 1][0]
            if key not in selected:
                selected.append(key)

        if ok and selected:
            return selected

        print("Invalid selection. Try again.\n")


def prompt_text(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw if raw else default


def to_provider_alias(provider: str) -> str:
    if provider in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[provider]
    cleaned = "".join(ch for ch in provider.lower() if ch.isalnum())
    return (cleaned[:2] or "xx")


def auth_letter_for(provider: str, mode: str) -> str:
    if mode == "api_key":
        return "T" if provider == "vercel-ai-gateway" else "K"
    if mode in {"oauth", "token"}:
        return "O"
    return "?"


def build_template(format_key: str, identity_name: str, custom_value: str) -> str:
    identity_token = identity_name.strip() or "{identityname}"
    if format_key == "custom":
        return ensure_postfix_template(custom_value)
    base = FORMAT_OPTIONS[format_key].format(identity=identity_token, provider="{provider}", model="{model}")
    return ensure_postfix_template(base)


def _strip_model_suffixes(model_name: str) -> str:
    model = model_name.strip()
    if not model:
        return model
    model = model.split(":", 1)[0]
    while True:
        next_model = re.sub(r"-(?:\d{8}|latest)$", "", model, flags=re.IGNORECASE)
        if next_model == model:
            break
        model = next_model
    if model.startswith("claude-"):
        model = re.sub(r"-(\d+)\.(\d+)$", r"-\1-\2", model)
    return model


def _preview_model_alias(model_name: str) -> str:
    model_aliases = DEFAULT_CONFIG.get("model_aliases", {})
    if isinstance(model_aliases, dict):
        alias = model_aliases.get(model_name)
        if isinstance(alias, str) and alias.strip():
            return alias
    cleaned = "".join(ch for ch in model_name.lower() if ch.isalnum())
    return (cleaned[:12] or "model")


def _resolve_openclaw_json_path(openclaw_json_path: Path | None) -> Path:
    if openclaw_json_path is not None:
        return openclaw_json_path.expanduser()
    openclaw_home = os.getenv("OPENCLAW_HOME")
    if openclaw_home:
        return Path(openclaw_home).expanduser() / "openclaw.json"
    return Path.home() / ".openclaw" / "openclaw.json"


def detect_primary_model(openclaw_json_path: Path | None = None) -> tuple[str, str] | None:
    """
    Read openclaw.json and return (provider, short_model_name) for the primary model.
    Returns None if file not found or unreadable.
    """
    try:
        cfg_path = _resolve_openclaw_json_path(openclaw_json_path)
        doc = json.loads(cfg_path.read_text(encoding="utf-8"))
        primary = doc["agents"]["defaults"]["model"]["primary"]
        if not isinstance(primary, str):
            return None

        parts = [segment for segment in primary.split("/") if segment]
        if len(parts) < 2:
            return None

        provider = parts[0]
        if provider in {"openrouter", "vercel-ai-gateway"}:
            model = parts[-1]
        else:
            model = "/".join(parts[1:])

        model = _strip_model_suffixes(model)
        if not provider or not model:
            return None
        return provider, model
    except Exception:
        return None


def _default_provider_selection(detected_provider: str | None) -> list[str]:
    if not detected_provider:
        return ["anthropic"]

    provider_map = {
        "openai-codex": "openai",
        "vercel-ai-gateway": "openai",
    }
    mapped = provider_map.get(detected_provider, detected_provider)
    valid_options = {key for key, _ in PROVIDER_OPTIONS}
    if mapped in valid_options:
        return [mapped]
    return ["anthropic"]


def preview_stamp(
    template: str,
    provider: str,
    auth_mode: str,
    identity_name: str,
    model_override: str | None = None,
) -> str:
    stamp = template
    if stamp.startswith("postfix:"):
        stamp = stamp[8:]

    provider_alias = f"{to_provider_alias(provider)}{auth_letter_for(provider, auth_mode)}"
    identity = identity_name.strip() or socket.gethostname().split(".")[0][:1].upper() or "A"
    model_name = model_override or "claude-sonnet-4-6"
    model_alias = _preview_model_alias(model_name)

    values = {
        "{provider}": provider_alias,
        "{model}": model_alias,
        "{modelfull}": f"{provider}/{model_name}",
        "{identityname}": identity,
    }
    for token, value in values.items():
        stamp = stamp.replace(token, value)
    return stamp


def write_config(path: Path, template: str, providers: list[tuple[str, str]]) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))

    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            cfg = deep_merge(cfg, data)

    cfg["response_prefix_template"] = template

    provider_aliases = dict(cfg.get("provider_aliases", {}))
    auth_overrides = dict(cfg.get("auth_mode_overrides", {}))

    for provider, mode in providers:
        provider_aliases[provider] = to_provider_alias(provider)
        mode_overrides = dict(auth_overrides.get(provider, {}))
        mode_overrides[mode] = auth_letter_for(provider, mode)
        auth_overrides[provider] = mode_overrides

    cfg["provider_aliases"] = provider_aliases
    cfg["auth_mode_overrides"] = auth_overrides

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return cfg


def run_apply(config_path: Path) -> int:
    patch_path = Path(__file__).with_name("patch.py")
    cmd = [sys.executable, str(patch_path), "--config", str(config_path)]
    return subprocess.run(cmd).returncode


STAMP_EXPLAINER = """
─────────────────────────────────────────────────────
  openclaw-postfix-pack setup
─────────────────────────────────────────────────────
This pack stamps every OpenClaw reply with the actual
model that sent it — not what /status says, but what
the runtime actually used.

The stamp appears at the END of each message.

  anK/s46-1m@A
  └┬┘└┬┘└──┬──┘└┬┘
   │  │    │   └── @Identity: your agent's initial
   │  │    └────── Model alias  (s46-1m = claude-sonnet-4-6)
   │  └─────────── Auth: K=API key  O=OAuth/token  T=Vercel
   └────────────── Provider alias  (an = anthropic)

Model aliases (built-in, all customizable):
  claude-sonnet-4-6 → s46-1m    claude-opus-4-6    → o46
  claude-sonnet-4-5 → s45       claude-haiku-4-5   → h45
  gpt-5.3-codex     → 53c       gpt-5.2-codex      → 52c
  gpt-5.2           → 52        minimax-m2.5        → m25
  glm-5             → g5        kimi-k2.5           → k25
  grok-4-1-fast     → g41f

Provider aliases:
  anthropic → an    openrouter → or    openai → oa
  xai       → xa    lmstudio   → lm

To add or change any alias after setup:
  Edit ~/.openclaw/postfix-pack.json → model_aliases / provider_aliases
  Then run: ~/.openclaw/bin/postfix-apply
─────────────────────────────────────────────────────
"""


def interactive_flow(args: argparse.Namespace, default_providers: list[str] | None = None) -> tuple[str, str, list[tuple[str, str]]]:
    if args.quiet:
        template = ensure_postfix_template(FORMAT_OPTIONS["compact"].format(identity="{identityname}", provider="{provider}", model="{model}"))
        return template, "", [("anthropic", "api_key")]

    print(STAMP_EXPLAINER)

    format_idx = prompt_choice(
        "Pick a stamp format:",
        [
            "Compact:    anK/s46-1m@A       ← provider+auth / model @ identity (recommended)",
            "Bracket:    [anK|s46-1m|A]     ← same info, bracket style",
            "Model only: s46-1m@A           ← skip provider, just model + identity",
            "Custom:     enter your own format string",
        ],
        default_index=0,
    )

    format_key = ["compact", "bracket", "minimal", "custom"][format_idx]
    identity_name = prompt_text("What's your agent's identity name? (leave blank for hostname shorthand)", "")

    custom_value = ""
    if format_key == "custom":
        custom_value = prompt_text(
            "Enter custom format (tokens: {provider}, {model}, {identityname}, {modelfull})",
            "postfix:{provider}/{model}@{identityname}",
        )

    selected_provider_keys = prompt_multi_select(
        "Which providers do you use?",
        PROVIDER_OPTIONS,
        default=default_providers or ["anthropic"],
    )

    provider_auth: list[tuple[str, str]] = []
    for provider_key in selected_provider_keys:
        provider_name = provider_key
        if provider_key == "other":
            provider_name = prompt_text("Enter provider id for 'other'", "other")

        auth_idx = prompt_choice(
            f"For provider '{provider_name}', what auth type do you use?",
            ["API key", "OAuth", "token"],
            default_index=0,
        )
        provider_auth.append((provider_name, AUTH_CHOICES[auth_idx][0]))

    template = build_template(format_key, identity_name, custom_value)
    return template, identity_name, provider_auth


def main() -> int:
    args = parse_args()
    cfg_path = Path(args.config).expanduser()
    detected = detect_primary_model(Path(args.openclaw_json).expanduser() if args.openclaw_json else None)
    default_providers = _default_provider_selection(detected[0] if detected else None)

    try:
        template, identity_name, provider_auth = interactive_flow(args, default_providers=default_providers)
    except KeyboardInterrupt:
        print("\nsetup canceled")
        return 130

    preview = preview_stamp(
        template,
        provider_auth[0][0],
        provider_auth[0][1],
        identity_name,
        model_override=(detected[1] if detected else None),
    )

    print()
    print("─────────────────────────────────────────────────────")
    print(f"  Preview stamp:  {preview}")
    if detected:
        print(f"  (detected your primary model: {detected[0]}/{detected[1]})")
    else:
        print("  (example only — could not read openclaw.json)")
    print()

    # Decode the preview so the user knows exactly what each segment means
    stamp_raw = preview
    prov, rest = (stamp_raw.split("/", 1) + ["?"])[:2]
    model_part, identity_part = (rest.split("@", 1) + ["?"])[:2] if "@" in rest else (rest, "?")

    provider_key = provider_auth[0][0]
    auth_mode    = provider_auth[0][1]
    auth_name    = {"api_key": "API key", "oauth": "OAuth", "token": "token"}.get(auth_mode, auth_mode)

    print(f"  {prov:<8}  ← {provider_key} ({auth_name})")
    print(f"  {model_part:<8}  ← model alias (edit model_aliases in config to change)")
    print(f"  @{identity_part:<7}  ← identity initial")
    print()
    print("  To add a model not in the built-in list, edit:")
    print(f"    ~/.openclaw/postfix-pack.json → model_aliases")
    print("  Example:  \"my-custom-model-v2\": \"mcm2\"")
    print("  Then run: ~/.openclaw/bin/postfix-apply")
    print("─────────────────────────────────────────────────────")
    print()

    if not args.quiet:
        confirm = input("Write this config and apply? [Y/n]: ").strip().lower()
        if confirm in {"n", "no"}:
            print("setup canceled")
            return 1

    write_config(cfg_path, template, provider_auth)
    print(f"\n✅ Config written: {cfg_path}")
    print("   Edit that file any time to add models, providers, or change the format.")
    print("   Re-apply with: ~/.openclaw/bin/postfix-apply")
    print()

    if args.no_apply:
        return 0

    rc = run_apply(cfg_path)
    if rc != 0:
        print("setup: patch apply failed", file=sys.stderr)
        return rc

    print("\n✅ Patch applied. Every reply will now end with the model stamp.")
    print("   If OpenClaw updates and the stamp breaks, run: ~/.openclaw/bin/postfix-apply")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
