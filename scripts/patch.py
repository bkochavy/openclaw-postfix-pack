#!/usr/bin/env python3
"""Public OpenClaw postfix pack patcher.

This tool keeps postfix model stamps active by:
1) ensuring OpenClaw telegram `responsePrefix` is in postfix mode, and
2) patching OpenClaw dist bundles so the postfix stamp is rendered reliably.

The dist patching logic is intentionally narrow and idempotent.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

POSTFIX_MARKER = "__POSTFIX_PATCHED__"
IDSHORT_MARKER = "__MODELSTAMP_IDSHORT__"
MODELSTAMP_V3_MARKER = "__MODELSTAMP_V3__"
TARGET_PATTERNS = ("reply-*.js", "pi-embedded-*.js", "subagent-registry-*.js")

DEFAULT_CONFIG = {
    "response_prefix_template": "postfix:{provider}/{model}@{identityname}",
    "model_aliases": {
        "claude-opus-4-6": "o46",
        "claude-sonnet-4-6": "s46-1m",
        "claude-sonnet-4-5": "s45",
        "claude-haiku-4-5": "h45",
        "gpt-5.3-codex": "53c",
        "gpt-5.2-codex": "52c",
        "gpt-5.2": "52",
        "minimax-m2.5": "m25",
        "glm-5": "g5",
        "kimi-k2.5": "k25",
        "grok-4-1-fast": "g41f",
        "grok-4-1-fast-reasoning": "g41fr",
    },
    "provider_aliases": {
        "anthropic": "an",
        "openrouter": "or",
        "openai-codex": "oc",
        "openai": "oa",
        "vercel-ai-gateway": "ve",
        "opencode": "op",
        "xai": "xa",
        "lmstudio": "lm",
    },
    "source_aliases": {
        "openai": "oa",
        "anthropic": "an",
        "minimax": "mm",
        "mistral": "ms",
        "deepseek": "ds",
        "google": "gg",
        "meta-llama": "ml",
        "moonshotai": "mo",
        "z-ai": "za",
        "zai": "za",
        "xai": "xa",
    },
    "fallback": {
        "provider_length": 2,
        "source_length": 2,
        "model_length": 12,
    },
    "auth_mode_overrides": {
        "anthropic": {"token": "O"},
        "vercel-ai-gateway": {"api_key": "T"},
    },
}


def deep_merge(base: dict, incoming: dict) -> dict:
    out = dict(base)
    for key, value in incoming.items():
        if isinstance(out.get(key), dict) and isinstance(value, dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"config is not an object: {path}")
        cfg = deep_merge(cfg, data)

    fallback = cfg.get("fallback", {})
    for key, default in (("provider_length", 2), ("source_length", 2), ("model_length", 12)):
        val = fallback.get(key, default)
        if not isinstance(val, int) or val <= 0:
            fallback[key] = default
    cfg["fallback"] = fallback

    for map_key in ("model_aliases", "provider_aliases", "source_aliases", "auth_mode_overrides"):
        if not isinstance(cfg.get(map_key), dict):
            cfg[map_key] = {}

    return cfg


def ensure_postfix_template(template: str) -> str:
    text = template.strip()
    if not text:
        raise ValueError("response prefix template is empty")
    if not text.startswith("postfix:"):
        text = f"postfix:{text}"
    return text


def apply_template_to_openclaw_json(doc: dict, template: str) -> int:
    changed = 0

    channels = doc.setdefault("channels", {})
    telegram = channels.setdefault("telegram", {})
    if telegram.get("responsePrefix") != template:
        telegram["responsePrefix"] = template
        changed += 1

    accounts = telegram.get("accounts")
    if isinstance(accounts, dict):
        for value in accounts.values():
            if isinstance(value, dict) and value.get("responsePrefix") != template:
                value["responsePrefix"] = template
                changed += 1

    return changed


def backup_openclaw_json(path: Path) -> Path:
    ts = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    openclaw_home = Path(os.getenv("OPENCLAW_HOME", str(Path.home() / ".openclaw"))).expanduser()
    backup_dir = openclaw_home / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"openclaw.json.postfix-pack.{ts}.bak"
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup


def sync_response_prefix(cfg: dict, openclaw_json_path: Path, check_only: bool) -> bool:
    template = ensure_postfix_template(str(cfg.get("response_prefix_template", DEFAULT_CONFIG["response_prefix_template"])))

    if not openclaw_json_path.is_file():
        print(f"response-prefix: WARNING: openclaw config not found: {openclaw_json_path}")
        return False

    doc = json.loads(openclaw_json_path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"expected object json: {openclaw_json_path}")

    changed = apply_template_to_openclaw_json(doc, template)
    if check_only:
        print(f"response-prefix: template={template}")
        print(f"response-prefix: changed_keys={changed}")
        return changed == 0

    backup = backup_openclaw_json(openclaw_json_path)
    openclaw_json_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"response-prefix: template={template}")
    print(f"response-prefix: backup={backup}")
    print(f"response-prefix: changed_keys={changed}")
    return True


def resolve_openclaw_pkg_dir() -> Path:
    which = shutil.which("openclaw")
    if not which:
        for cand in ("/opt/homebrew/bin/openclaw", "/usr/local/bin/openclaw", "/usr/bin/openclaw"):
            if Path(cand).exists():
                which = cand
                break
    if not which:
        raise SystemExit("openclaw executable not found")
    return Path(which).resolve().parent


def resolve_node_bin() -> str | None:
    node = shutil.which("node")
    if node:
        return node
    for cand in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node"):
        if Path(cand).exists():
            return cand
    return None


def validate_js_syntax(path: Path) -> tuple[bool, str]:
    node = resolve_node_bin()
    if not node:
        return False, "node executable not found for syntax validation"
    proc = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
    if proc.returncode == 0:
        return True, ""
    return False, (proc.stderr or proc.stdout or "").strip()


def patch_postfix_support(js: str) -> tuple[str, str]:
    if POSTFIX_MARKER in js:
        return js, "already"

    postfix_block = (
        f"/* {POSTFIX_MARKER} */ "
        "if (effectivePrefix && text && text.trim() !== HEARTBEAT_TOKEN) { "
        "if (effectivePrefix.startsWith(\"postfix:\")) { "
        "const suffix = effectivePrefix.slice(8); "
        "if (!text.endsWith(suffix)) text = `${text}\\n${suffix}`; "
        "} else if (!text.startsWith(effectivePrefix)) { "
        "text = `${effectivePrefix} ${text}`; "
        "} "
        "}"
    )

    literal_line = "if (effectivePrefix && text && text.trim() !== HEARTBEAT_TOKEN && !text.startsWith(effectivePrefix)) text = `${effectivePrefix} ${text}`;"
    if literal_line in js:
        return js.replace(literal_line, postfix_block, 1), "patched"

    pat = re.compile(
        r"if\s*\(\s*effectivePrefix\s*&&\s*text\s*&&\s*text\.trim\(\)\s*!==\s*HEARTBEAT_TOKEN\s*&&\s*!text\.startsWith\(effectivePrefix\)\s*\)\s*\{?\s*text\s*=\s*`\$\{effectivePrefix\}\s+\$\{text\}`;\s*\}?",
        re.MULTILINE,
    )
    new, n = pat.subn(postfix_block, js, count=1)
    if n == 1:
        return new, "patched"
    return js, "no-match"


def patch_identity_short(js: str) -> tuple[str, str]:
    if IDSHORT_MARKER in js:
        return js, "already"

    pat = re.compile(r"const\s+prefixContext\s*=\s*\{\s*identityName:\s*resolveIdentityName\(cfg,\s*agentId\)\s*\};")
    repl = (
        f"/* {IDSHORT_MARKER} */ const __id0 = resolveIdentityName(cfg, agentId);"
        "const prefixContext = { identityName: __id0 ? __id0.trim().slice(0, 1).toUpperCase() : void 0 };"
    )
    new, n = pat.subn(repl, js, count=1)
    if n != 1:
        return js, "no-match"
    return new, "patched"


def normalize_raw_provider_declaration(js: str) -> tuple[str, bool]:
    pat = re.compile(r"(\n[ \t]*let __rawProvider, __rawModel;\n)(?:[ \t]*let __rawProvider, __rawModel;\n)+", re.MULTILINE)
    new, n = pat.subn(r"\1", js)
    return new, n > 0


def has_safe_provider_auth_logic(js: str) -> bool:
    return (
        "typeof resolveAgentDir === \"function\" && typeof ensureAuthProfileStore === \"function\"" in js
        and "const __profiles = cfg?.auth?.profiles;" in js
    )


def to_js_obj(data: dict) -> str:
    return json.dumps(data, separators=(",", ":"), sort_keys=True)


def patch_modelstamp_v3(js: str, cfg: dict, force: bool) -> tuple[str, str]:
    js, deduped = normalize_raw_provider_declaration(js)
    if MODELSTAMP_V3_MARKER in js and not force and has_safe_provider_auth_logic(js):
        return js, ("patched" if deduped else "already")

    model_alias_map = to_js_obj(cfg.get("model_aliases", {}))
    provider_alias_map = to_js_obj(cfg.get("provider_aliases", {}))
    source_alias_map = to_js_obj(cfg.get("source_aliases", {}))
    auth_override_map = to_js_obj(cfg.get("auth_mode_overrides", {}))

    fb = cfg.get("fallback", {})
    provider_len = int(fb.get("provider_length", 2))
    source_len = int(fb.get("source_length", 2))
    model_len = int(fb.get("model_length", 12))

    on_model_re = re.compile(r"[ \t]*const onModelSelected = \(ctx\) => \{.*?\n[ \t]*\};", re.DOTALL)
    on_model_new = (
        "\tlet __rawProvider, __rawModel;\n"
        f"\tconst __MODEL_ALIAS_MAP = {model_alias_map};\n"
        f"\tconst __MODEL_FALLBACK_LEN = {model_len};\n"
        "\tconst onModelSelected = (ctx) => {\n"
        f"\t/* {MODELSTAMP_V3_MARKER} */ __rawProvider = ctx.provider; __rawModel = ctx.model;\n"
        "\tconst __m0 = extractShortModelName(ctx.model);\n"
        "\tlet __ms = __MODEL_ALIAS_MAP[__m0];\n"
        "\tif (!__ms) __ms = __m0.toLowerCase().replace(/[^a-z0-9]+/g, \"\").slice(0, __MODEL_FALLBACK_LEN);\n"
        "\tprefixContext.model = __ms;\n"
        "\tprefixContext.modelFull = `${ctx.provider}/${ctx.model}`;\n"
        "\tprefixContext.thinkingLevel = ctx.thinkLevel ?? \"off\";\n"
        "\t};"
    )

    newer, n = on_model_re.subn(on_model_new, js, count=1)
    if n != 1:
        if MODELSTAMP_V3_MARKER in js:
            newer = js
        else:
            return js, "no-match"

    rpp_repl = (
        f"const __PROVIDER_ALIAS_MAP = {provider_alias_map};\n"
        f"const __SOURCE_ALIAS_MAP = {source_alias_map};\n"
        f"const __AUTH_OVERRIDES = {auth_override_map};\n"
        f"const __PROVIDER_FALLBACK_LEN = {provider_len};\n"
        f"const __SOURCE_FALLBACK_LEN = {source_len};\n"
        "responsePrefixContextProvider: () => {\n"
        "\tif (__rawProvider) {\n"
        "\t\tconst __base = (__PROVIDER_ALIAS_MAP[__rawProvider] ?? __rawProvider.slice(0, __PROVIDER_FALLBACK_LEN));\n"
        "\t\tlet __auth = __rawProvider === \"lmstudio\" ? \"L\" : \"?\";\n"
        "\t\ttry {\n"
        "\t\t\tif (typeof resolveAgentDir === \"function\" && typeof ensureAuthProfileStore === \"function\") {\n"
        "\t\t\t\tconst __adir = resolveAgentDir(cfg, agentId);\n"
        "\t\t\t\tif (__adir) {\n"
        "\t\t\t\t\tconst __store = ensureAuthProfileStore(__adir, { allowKeychainPrompt: false });\n"
        "\t\t\t\t\tconst __pid = __store.lastGood?.[__rawProvider];\n"
        "\t\t\t\t\tconst __ptype = __pid ? __store.profiles?.[__pid]?.type : void 0;\n"
        "\t\t\t\t\tconst __override = __AUTH_OVERRIDES?.[__rawProvider]?.[__ptype];\n"
        "\t\t\t\t\tif (__override) __auth = __override;\n"
        "\t\t\t\t\telse if (__ptype === \"oauth\") __auth = \"O\";\n"
        "\t\t\t\t\telse if (__ptype === \"api_key\") __auth = (__rawProvider === \"vercel-ai-gateway\" ? \"T\" : \"K\");\n"
        "\t\t\t\t\telse if (__ptype === \"token\") __auth = (__rawProvider === \"anthropic\" ? \"O\" : \"T\");\n"
        "\t\t\t\t}\n"
        "\t\t\t}\n"
        "\t\t\tif (__auth === \"?\") {\n"
        "\t\t\t\tconst __profiles = cfg?.auth?.profiles;\n"
        "\t\t\t\tconst __defaultId = `${__rawProvider}:default`;\n"
        "\t\t\t\tconst __entry = __profiles?.[__defaultId] ?? Object.values(__profiles ?? {}).find((p) => p?.provider === __rawProvider);\n"
        "\t\t\t\tconst __mode = __entry?.mode;\n"
        "\t\t\t\tconst __override = __AUTH_OVERRIDES?.[__rawProvider]?.[__mode];\n"
        "\t\t\t\tif (__override) __auth = __override;\n"
        "\t\t\t\telse if (__mode === \"oauth\") __auth = \"O\";\n"
        "\t\t\t\telse if (__mode === \"api_key\") __auth = (__rawProvider === \"vercel-ai-gateway\" ? \"T\" : \"K\");\n"
        "\t\t\t\telse if (__mode === \"token\") __auth = (__rawProvider === \"anthropic\" ? \"O\" : \"T\");\n"
        "\t\t\t}\n"
        "\t\t} catch {}\n"
        "\t\tlet __src = null;\n"
        "\t\tif (__rawProvider === \"openrouter\" || __rawProvider === \"vercel-ai-gateway\") {\n"
        "\t\t\tconst __seg = String(__rawModel ?? \"\").split(\"/\")[0].toLowerCase();\n"
        "\t\t\tconst __src0 = (__SOURCE_ALIAS_MAP[__seg] ?? __seg.slice(0, __SOURCE_FALLBACK_LEN));\n"
        "\t\t\t__src = __src0 || \"??\";\n"
        "\t\t}\n"
        "\t\tprefixContext.provider = __src ? `${__base}${__auth}.${__src}` : `${__base}${__auth}`;\n"
        "\t}\n"
        "\treturn prefixContext;\n"
        "},"
    )

    literal = "responsePrefixContextProvider: () => prefixContext,"
    if literal in newer:
        newest = newer.replace(literal, rpp_repl, 1)
    else:
        rpp_re = re.compile(r"responsePrefixContextProvider:\s*\(\)\s*=>\s*\{.*?return prefixContext;\s*\},", re.DOTALL)
        newest, rpp_n = rpp_re.subn(rpp_repl, newer, count=1)
        if rpp_n != 1:
            newest, _ = normalize_raw_provider_declaration(newest)
            return newest, ("patched" if newest != js else "already")

    newest, _ = normalize_raw_provider_declaration(newest)
    return newest, ("patched" if newest != js else "already")


def bump(summary: dict, key: str, status: str) -> None:
    if status == "patched":
        summary[f"{key}_patched"] += 1
    elif status == "already":
        summary[f"{key}_already"] += 1
    else:
        summary[f"{key}_no_match"] += 1


def parse_args() -> argparse.Namespace:
    default_openclaw_home = Path(os.getenv("OPENCLAW_HOME", str(Path.home() / ".openclaw"))).expanduser()
    parser = argparse.ArgumentParser(description="Patch OpenClaw dist bundles for postfix suffix stamps")
    parser.add_argument("--config", default=os.getenv("OPENCLAW_POSTFIX_CONFIG", str(Path.home() / ".openclaw" / "postfix-pack.json")))
    parser.add_argument(
        "--openclaw-json",
        default=os.getenv("OPENCLAW_JSON", str(default_openclaw_home / "openclaw.json")),
        help="Path to openclaw.json for responsePrefix synchronization",
    )
    parser.add_argument("--openclaw-pkg-dir", default="", help="OpenClaw package dir that contains dist/")
    parser.add_argument("--check-only", action="store_true", help="Do not write files")
    parser.add_argument("--force-modelstamp", action="store_true", help="Force repatching model stamp logic")
    parser.add_argument("--setup", action="store_true", help="Run setup wizard, then patch")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    force_modelstamp = args.force_modelstamp or os.getenv("OPENCLAW_PATCH_FORCE_MODELSTAMP", "").lower() in {"1", "true", "yes"}

    cfg_path = Path(args.config).expanduser()
    if args.setup:
        wizard_path = Path(__file__).with_name("setup-wizard.py")
        if not wizard_path.is_file():
            print(f"setup wizard not found: {wizard_path}", file=sys.stderr)
            return 6
        cmd = [sys.executable, str(wizard_path), "--config", str(cfg_path)]
        if os.getenv("OPENCLAW_POSTFIX_SETUP_QUIET", "").lower() in {"1", "true", "yes"}:
            cmd.append("--quiet")
        setup_proc = subprocess.run(cmd)
        if setup_proc.returncode != 0:
            return setup_proc.returncode

    cfg = load_config(cfg_path)
    response_prefix_ok = sync_response_prefix(cfg, Path(args.openclaw_json).expanduser(), args.check_only)

    pkg_dir = Path(args.openclaw_pkg_dir).expanduser() if args.openclaw_pkg_dir else resolve_openclaw_pkg_dir()
    dist = pkg_dir / "dist"
    if not dist.is_dir():
        print(f"dist dir not found: {dist}", file=sys.stderr)
        return 2

    bundle_files = sorted({f for pattern in TARGET_PATTERNS for f in dist.glob(pattern)})
    if not bundle_files:
        print(f"no target bundles found in {dist}", file=sys.stderr)
        return 2

    summary = {
        "postfix_patched": 0,
        "postfix_already": 0,
        "postfix_no_match": 0,
        "idshort_patched": 0,
        "idshort_already": 0,
        "idshort_no_match": 0,
        "modelstamp_patched": 0,
        "modelstamp_already": 0,
        "modelstamp_no_match": 0,
        "syntax_fail": 0,
    }

    for path in bundle_files:
        js = path.read_text(encoding="utf-8")
        js2, st1 = patch_postfix_support(js)
        js3, st2 = patch_identity_short(js2)
        js4, st3 = patch_modelstamp_v3(js3, cfg, force_modelstamp)

        bump(summary, "postfix", st1)
        bump(summary, "idshort", st2)
        bump(summary, "modelstamp", st3)

        if args.check_only:
            continue

        if js4 != js:
            original = js
            path.write_text(js4, encoding="utf-8")
            ok, detail = validate_js_syntax(path)
            if not ok:
                summary["syntax_fail"] += 1
                path.write_text(original, encoding="utf-8")
                print(f"postfix-patch: WARNING: syntax check failed in {path.name}; reverted file")
                if detail:
                    print(detail)

    print(
        "postfix-patch:",
        ", ".join(f"{k}={v}" for k, v in summary.items()),
        f"(pkg={pkg_dir}, config={cfg_path})",
    )

    if summary["postfix_patched"] == 0 and summary["postfix_already"] == 0:
        return 3
    if summary["syntax_fail"] > 0:
        return 4
    if args.check_only and not response_prefix_ok:
        return 5

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
