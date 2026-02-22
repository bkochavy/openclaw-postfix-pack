#!/usr/bin/env python3
"""Interactive setup wizard for OpenClaw postfix-pack configuration."""

from __future__ import annotations

import argparse
import json
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


def preview_stamp(template: str, provider: str, auth_mode: str, identity_name: str) -> str:
    stamp = template
    if stamp.startswith("postfix:"):
        stamp = stamp[8:]

    provider_alias = f"{to_provider_alias(provider)}{auth_letter_for(provider, auth_mode)}"
    identity = identity_name.strip() or socket.gethostname().split(".")[0][:1].upper() or "A"

    values = {
        "{provider}": provider_alias,
        "{model}": "s46-1m",
        "{modelfull}": "anthropic/claude-sonnet-4-6",
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


def interactive_flow(args: argparse.Namespace) -> tuple[str, str, list[tuple[str, str]]]:
    if args.quiet:
        template = ensure_postfix_template(FORMAT_OPTIONS["compact"].format(identity="{identityname}", provider="{provider}", model="{model}"))
        return template, "", [("anthropic", "api_key")]

    format_idx = prompt_choice(
        "What format do you want for the model stamp?",
        [
            "Compact: anK/s46-1m@A (recommended)",
            "Bracket: [anthropic|sonnet-4-6|A]",
            "Model only: s46-1m@A",
            "Custom: enter your own format string",
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
        default=["anthropic"],
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

    try:
        template, identity_name, provider_auth = interactive_flow(args)
    except KeyboardInterrupt:
        print("\nsetup canceled")
        return 130

    preview = preview_stamp(template, provider_auth[0][0], provider_auth[0][1], identity_name)
    print(f"\nPreview: Your replies will look like: {preview}")

    if not args.quiet:
        confirm = input("Write this configuration and apply now? [Y/n]: ").strip().lower()
        if confirm in {"n", "no"}:
            print("setup canceled")
            return 1

    write_config(cfg_path, template, provider_auth)
    print(f"Wrote config: {cfg_path}")

    if args.no_apply:
        return 0

    rc = run_apply(cfg_path)
    if rc != 0:
        print("setup: patch apply failed", file=sys.stderr)
        return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
