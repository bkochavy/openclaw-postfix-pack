#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX="$(mktemp -d)"
OPENCLAW_HOME="${SANDBOX}/.openclaw"
OPENCLAW_JSON="${OPENCLAW_HOME}/openclaw.json"
PKG_DIR="${SANDBOX}/openclaw"
DIST_DIR="${PKG_DIR}/dist"

FAIL=0
ERRORS=()

record_fail() {
  FAIL=1
  ERRORS+=("$1")
}

cleanup() {
  rm -rf "${SANDBOX}"
}
trap cleanup EXIT

mkdir -p "${OPENCLAW_HOME}" "${DIST_DIR}" "${SANDBOX}/bin"
export OPENCLAW_HOME

cat > "${SANDBOX}/bin/node" <<'NODE'
#!/usr/bin/env bash
if [[ "${1:-}" == "--check" ]]; then
  exit 0
fi
exit 0
NODE
chmod +x "${SANDBOX}/bin/node"
export PATH="${SANDBOX}/bin:${PATH}"

cat > "${OPENCLAW_JSON}" <<'JSON'
{
  "channels": {
    "telegram": {
      "responsePrefix": "{provider}/{model}@{identityname}"
    }
  }
}
JSON

cat > "${PKG_DIR}/package.json" <<'JSON'
{
  "name": "openclaw",
  "version": "test-0.0.0"
}
JSON

cat > "${DIST_DIR}/reply-TEST.js" <<'JS'
const HEARTBEAT_TOKEN = "__hb__";
function assemble(text, effectivePrefix) {
  if (effectivePrefix && text && text.trim() !== HEARTBEAT_TOKEN && !text.startsWith(effectivePrefix)) text = `${effectivePrefix} ${text}`;
  return text;
}
module.exports = { assemble };
JS

cat > "${DIST_DIR}/reply-prefix-TEST.js" <<'JS'
function extractShortModelName(model) {
  return model;
}

function createReplyPrefixContext(cfg, agentId, responsePrefix) {
  const prefixContext = { identityName: resolveIdentityName(cfg, agentId) };
  const onModelSelected = (ctx) => {
    prefixContext.provider = ctx.provider;
    prefixContext.model = extractShortModelName(ctx.model);
    prefixContext.modelFull = `${ctx.provider}/${ctx.model}`;
    prefixContext.thinkingLevel = ctx.thinkLevel ?? "off";
  };
  return { prefixContext, responsePrefix, responsePrefixContextProvider: () => prefixContext, onModelSelected };
}

module.exports = { createReplyPrefixContext };
JS

set +e
PATCH_OUTPUT="$(python3 "${ROOT_DIR}/scripts/patch.py" --config "${ROOT_DIR}/postfix-pack.example.json" --openclaw-json "${OPENCLAW_JSON}" --openclaw-pkg-dir "${PKG_DIR}" 2>&1)"
PATCH_RC=$?
set -e

printf '%s\n' "${PATCH_OUTPUT}"

POSTFIX_COUNT="$(rg -l "__POSTFIX_PATCHED__" "${DIST_DIR}"/*.js 2>/dev/null | wc -l | tr -d ' ')"
MODELSTAMP_COUNT="$(rg -l "__MODELSTAMP_V3__" "${DIST_DIR}"/reply-prefix-*.js 2>/dev/null | wc -l | tr -d ' ')"

if [[ "${PATCH_RC}" -ne 0 && ( "${POSTFIX_COUNT}" -lt 1 || "${MODELSTAMP_COUNT}" -lt 1 ) ]]; then
  record_fail "patch.py exited ${PATCH_RC} before producing expected markers"
fi

RESPONSE_PREFIX="$(python3 - "${OPENCLAW_JSON}" <<'PY'
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
print(doc.get('channels', {}).get('telegram', {}).get('responsePrefix', ''))
PY
)"

if [[ "${RESPONSE_PREFIX}" != "postfix:{provider}/{model}@{identityname}" ]]; then
  record_fail "openclaw.json responsePrefix is '${RESPONSE_PREFIX}'"
fi

if [[ "${POSTFIX_COUNT}" -lt 1 ]]; then
  record_fail "no bundle contains __POSTFIX_PATCHED__"
fi

if [[ "${MODELSTAMP_COUNT}" -lt 1 ]]; then
  record_fail "no reply-prefix bundle contains __MODELSTAMP_V3__"
fi

if [[ "${FAIL}" -eq 0 ]]; then
  echo "PASS: sandbox install patch test succeeded"
  exit 0
fi

echo "FAIL: sandbox install patch test failed"
for err in "${ERRORS[@]}"; do
  echo "  - ${err}"
done
exit 1
