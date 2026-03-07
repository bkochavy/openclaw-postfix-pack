#!/usr/bin/env python3
"""Keep OpenClaw Telegram postfix model stamps working across OpenClaw updates.

This patcher is intentionally narrow and idempotent. It modifies installed
OpenClaw dist bundles to support `responsePrefix: "postfix:..."` suffix mode
and compact provider/model/identity stamp rendering.
"""

from __future__ import annotations

import argparse
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
PREFIX_ALIAS_TEMPLATE_MARKER = "__PREFIX_ALIAS_TEMPLATE_V1__"
TARGET_PATTERNS = ("reply-*.js", "pi-embedded-*.js", "subagent-registry-*.js")

DEFAULT_CONFIG = {
    "response_prefix_template": "postfix:{provideralias}/{alias}@{identityname}",
    "model_aliases": {
        "claude-opus-4-6": "o46",
        "claude-opus-4.6": "o46",
        "opus-4.6": "o46",
        "claude-sonnet-4-6": "s46",
        "claude-sonnet-4.6": "s46",
        "sonnet-4.6": "s46",
        "claude-sonnet-4-5": "s45",
        "claude-haiku-4-5": "h45",
        "gpt-5.4": "gpt54",
        "gpt-5.3-codex": "gpt53c",
        "gpt-5.3-codex-spark": "gpt53s",
        "gpt-5.2-codex": "gpt52c",
        "gpt-5.2": "gpt52",
        "minimax-m2.5": "m25",
        "glm-5": "g5",
        "kimi-k2.5": "k25",
        "grok-4-1-fast": "g41f",
        "grok-4-1-fast-reasoning": "g41fr",
        "claude-haiku-4-6": "h46",
        "claude-haiku-4.6": "h46",
        "haiku-4.6": "h46",
        "claude-haiku-4-5-20251001": "h45",
        "claude-sonnet-4-5-20250929": "s45"
    },
    "provider_aliases": {
        "anthropic": "anO",
        "claude-cli": "ancli",
        "openrouter": "orK",
        "openai-codex": "opK",
        "codex-cli": "opcli",
        "openai": "opK",
        "vercel-ai-gateway": "veT",
        "opencode": "ocK",
        "xai": "xaK",
        "lmstudio": "lmL"
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
        "xai": "xa"
    },
    "fallback": {
        "provider_length": 2,
        "source_length": 2,
        "model_length": 12,
    },
    "auth_mode_overrides": {
        "anthropic": {"token": "O", "oauth": "O", "api_key": "K"},
        "claude-cli": {"token": "O", "oauth": "O", "api_key": "O"},
        "openai": {"token": "K", "oauth": "K", "api_key": "K"},
        "openai-codex": {"token": "K", "oauth": "K", "api_key": "K"},
        "codex-cli": {"token": "K", "oauth": "K", "api_key": "K"},
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

    # When force is set and the file is already patched, do an in-place update
    # of the alias maps and provider/auth blocks instead of re-injecting the
    # entire stamp block (which causes duplicate-declaration syntax errors
    # because declarations outside the regex capture survive replacement).
    if force and MODELSTAMP_V3_MARKER in js:
        updated = False
        new_model_map = to_js_obj(cfg.get("model_aliases", {}))
        new_provider_map = to_js_obj(cfg.get("provider_aliases", {}))
        new_source_map = to_js_obj(cfg.get("source_aliases", {}))
        new_auth_map = to_js_obj(cfg.get("auth_mode_overrides", {}))
        # Update MODEL_ALIAS_MAP inline
        js, n = re.subn(
            r"const __MODEL_ALIAS_MAP = \{[^}]*\};",
            f"const __MODEL_ALIAS_MAP = {new_model_map};",
            js, count=1,
        )
        if n: updated = True
        # Update PROVIDER_ALIAS_MAP inline
        js, n = re.subn(
            r"const __PROVIDER_ALIAS_MAP = \{[^}]*\};",
            f"const __PROVIDER_ALIAS_MAP = {new_provider_map};",
            js, count=1,
        )
        if n: updated = True
        # Update SOURCE_ALIAS_MAP inline
        js, n = re.subn(
            r"const __SOURCE_ALIAS_MAP = \{[^}]*\};",
            f"const __SOURCE_ALIAS_MAP = {new_source_map};",
            js, count=1,
        )
        if n: updated = True
        # Update AUTH_OVERRIDES inline
        js, n = re.subn(
            r"const __AUTH_OVERRIDES = \{[^}]*\};",
            f"const __AUTH_OVERRIDES = {new_auth_map};",
            js, count=1,
        )
        if n: updated = True
        return js, ("patched" if updated else "already")

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


def patch_reply_prefix_alias_template(js: str) -> tuple[str, str]:
    if PREFIX_ALIAS_TEMPLATE_MARKER in js:
        return js, "already"

    if "function resolveResponsePrefixTemplate(template, context)" not in js or "function createReplyPrefixContext(params)" not in js:
        return js, "no-match"

    working = js

    imports_pat = re.compile(r"((?:import [^\n]+;\n)+)(\n//#region src/agents/identity\.ts)")
    imports_block = (
        'import { readFileSync } from "node:fs";\n'
        'import { homedir } from "node:os";\n'
        'import { join } from "node:path";\n'
    )
    if 'import { readFileSync } from "node:fs";' not in working:
        working, imports_n = imports_pat.subn(r"\1" + imports_block + r"\2", working, count=1)
        if imports_n != 1:
            return js, "no-match"

    template_const = r"const TEMPLATE_VAR_PATTERN = /\{([a-zA-Z][a-zA-Z0-9.]*)\}/g;"
    template_patch = (
        "const TEMPLATE_VAR_PATTERN = /\\{([a-zA-Z][a-zA-Z0-9.]*)\\}/g;\n"
        'const __POSTFIX_PACK_CONFIG_PATH = process.env.OPENCLAW_POSTFIX_CONFIG || join(homedir(), ".openclaw", "postfix-pack.json");\n'
        "let __postfixPrefixAliasCache;\n"
        "function __normalizeAliasMap(value) {\n"
        "\treturn typeof value === \"object\" && value !== null ? value : {};\n"
        "}\n"
        "function __loadPostfixPrefixAliasCache() {\n"
        "\tif (__postfixPrefixAliasCache) return __postfixPrefixAliasCache;\n"
        "\tlet parsed = {};\n"
        "\ttry {\n"
        "\t\tconst raw = readFileSync(__POSTFIX_PACK_CONFIG_PATH, \"utf8\");\n"
        "\t\tconst data = JSON.parse(raw);\n"
        "\t\tif (typeof data === \"object\" && data !== null) parsed = data;\n"
        "\t} catch {}\n"
        "\t__postfixPrefixAliasCache = {\n"
        "\t\tmodelAliases: __normalizeAliasMap(parsed.model_aliases),\n"
        "\t\tproviderAliases: __normalizeAliasMap(parsed.provider_aliases)\n"
        "\t};\n"
        "\treturn __postfixPrefixAliasCache;\n"
        "}\n"
        "function resolveModelAlias(modelName) {\n"
        "\tconst shortModel = extractShortModelName(String(modelName ?? \"\")).trim();\n"
        "\tif (!shortModel) return shortModel;\n"
        "\tconst aliases = __loadPostfixPrefixAliasCache().modelAliases;\n"
        "\tconst alias = aliases[shortModel];\n"
        "\treturn typeof alias === \"string\" && alias.trim() ? alias.trim() : shortModel;\n"
        "}\n"
        "function resolveProviderAlias(providerName) {\n"
        "\tconst provider = String(providerName ?? \"\").trim();\n"
        "\tif (!provider) return provider;\n"
        "\tconst aliases = __loadPostfixPrefixAliasCache().providerAliases;\n"
        "\tconst alias = aliases[provider];\n"
        "\treturn typeof alias === \"string\" && alias.trim() ? alias.trim() : provider;\n"
        "}\n"
        f"/* {PREFIX_ALIAS_TEMPLATE_MARKER} */"
    )
    if template_const not in working:
        return js, "no-match"
    working = working.replace(template_const, template_patch, 1)

    old_model_case = 'case "model": return context.model ?? match;'
    new_model_case = (
        'case "model": return context.model ?? match;\n'
        '\t\t\tcase "alias": return context.alias ?? resolveModelAlias(context.model ?? context.modelFull);'
    )
    if old_model_case not in working:
        return js, "no-match"
    working = working.replace(old_model_case, new_model_case, 1)

    old_provider_case = 'case "provider": return context.provider ?? match;'
    new_provider_case = (
        'case "provider": return context.provider ?? match;\n'
        '\t\t\tcase "provideralias": return context.providerAlias ?? resolveProviderAlias(context.provider);'
    )
    if old_provider_case not in working:
        return js, "no-match"
    working = working.replace(old_provider_case, new_provider_case, 1)

    on_model_old = (
        "\tconst onModelSelected = (ctx) => {\n"
        "\t\tprefixContext.provider = ctx.provider;\n"
        "\t\tprefixContext.model = extractShortModelName(ctx.model);\n"
        "\t\tprefixContext.modelFull = `${ctx.provider}/${ctx.model}`;\n"
        "\t\tprefixContext.thinkingLevel = ctx.thinkLevel ?? \"off\";\n"
        "\t};"
    )
    on_model_new = (
        "\tconst onModelSelected = (ctx) => {\n"
        "\t\tprefixContext.provider = ctx.provider;\n"
        "\t\tprefixContext.providerAlias = resolveProviderAlias(ctx.provider);\n"
        "\t\tprefixContext.model = extractShortModelName(ctx.model);\n"
        "\t\tprefixContext.alias = resolveModelAlias(prefixContext.model);\n"
        "\t\tprefixContext.modelFull = `${ctx.provider}/${ctx.model}`;\n"
        "\t\tprefixContext.thinkingLevel = ctx.thinkLevel ?? \"off\";\n"
        "\t};"
    )
    if on_model_old not in working:
        return js, "no-match"
    working = working.replace(on_model_old, on_model_new, 1)

    return working, ("patched" if working != js else "already")


def bump(summary: dict, key: str, status: str) -> None:
    if status == "patched":
        summary[f"{key}_patched"] += 1
    elif status == "already":
        summary[f"{key}_already"] += 1
    else:
        summary[f"{key}_no_match"] += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch OpenClaw dist bundles for postfix suffix stamps")
    parser.add_argument("--config", default=os.getenv("OPENCLAW_POSTFIX_CONFIG", str(Path.home() / ".openclaw" / "postfix-pack.json")))
    parser.add_argument("--openclaw-pkg-dir", default="", help="OpenClaw package dir that contains dist/")
    parser.add_argument("--check-only", action="store_true", help="Do not write files")
    parser.add_argument("--force-modelstamp", action="store_true", help="Force repatching model stamp logic")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    force_modelstamp = args.force_modelstamp or os.getenv("OPENCLAW_PATCH_FORCE_MODELSTAMP", "").lower() in {"1", "true", "yes"}

    cfg_path = Path(args.config).expanduser()
    cfg = load_config(cfg_path)

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
        "prefix_alias_template_patched": 0,
        "prefix_alias_template_already": 0,
        "prefix_alias_template_no_match": 0,
        "syntax_fail": 0,
    }

    for path in bundle_files:
        js = path.read_text(encoding="utf-8")
        if path.name.startswith("reply-prefix-"):
            js2, st1 = js, "already"
            js3, st2 = js2, "already"
            js4, st3 = js3, "already"
            js5, st4 = patch_reply_prefix_alias_template(js4)
        else:
            js2, st1 = patch_postfix_support(js)
            js3, st2 = patch_identity_short(js2)
            js4, st3 = patch_modelstamp_v3(js3, cfg, force_modelstamp)
            js5, st4 = js4, "already"

        bump(summary, "postfix", st1)
        bump(summary, "idshort", st2)
        bump(summary, "modelstamp", st3)
        if path.name.startswith("reply-prefix-"):
            bump(summary, "prefix_alias_template", st4)

        if args.check_only:
            continue

        if js5 != js:
            original = js
            path.write_text(js5, encoding="utf-8")
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
