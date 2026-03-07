#!/usr/bin/env bash
set -euo pipefail

printf "%s\n" "openclaw-postfix-pack is deprecated and is no longer recommended for current OpenClaw installs." >&2
printf "%s\n" "Use a native responsePrefix marker plus a small local suffix plugin instead of dist patching." >&2
printf "%s\n" "No changes were made." >&2
exit 1
