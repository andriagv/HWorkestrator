#!/usr/bin/env bash
# Pushes the current code to a Hugging Face Space (Docker SDK).
# A Space needs a README.md with a YAML header, so a throw-away copy of the repo with that header is pushed.
# Usage: bash deploy/push_to_space.sh <hf-user>/<space-name>
set -euo pipefail
SPACE="${1:?usage: push_to_space.sh <hf-user>/<space-name>}"
cd "$(dirname "$0")/.."
TMP="$(mktemp -d)"
git archive HEAD | tar -x -C "$TMP"
{ printf -- '---\ntitle: HWorkestrator\nemoji: 🎓\ncolorFrom: blue\ncolorTo: indigo\nsdk: docker\napp_port: 7860\npinned: false\n---\n\n'; cat "$TMP/README.md"; } > "$TMP/README.new" && mv "$TMP/README.new" "$TMP/README.md"
cd "$TMP"
git init -q -b main
git add -A
git -c user.name="deploy" -c user.email="deploy@local" commit -q -m "Deploy $(date -u +%Y-%m-%dT%H:%MZ)"
git push --force "https://huggingface.co/spaces/${SPACE}" main
echo "Pushed. Build logs: https://huggingface.co/spaces/${SPACE}"
