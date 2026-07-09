#!/usr/bin/env bash
# Point this clone at the committed hooks in .githooks/ (run once per clone).
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
git -C "${root}" config core.hooksPath .githooks
chmod +x "${root}/.githooks/pre-commit"
echo "core.hooksPath=.githooks for ${root}"
