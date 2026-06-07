#!/bin/bash
# Point local repo at fpheromones/growth and push.
set -euo pipefail
cd "$(dirname "$0")/.."

OWNER="${1:-fpheromones}"
REPO="${2:-growth}"
REMOTE_URL="https://github.com/${OWNER}/${REPO}.git"

echo "Target: ${REMOTE_URL}"
git remote remove origin 2>/dev/null || true
git remote add origin "${REMOTE_URL}"

if gh repo view "${OWNER}/${REPO}" &>/dev/null; then
  git push -u origin main
  echo "✅ Pushed to ${REMOTE_URL}"
  exit 0
fi

echo "Repo not found. Creating under ${OWNER}..."
if ! gh auth refresh -h github.com -s repo,delete_repo,read:org 2>/dev/null; then
  echo "⚠️  gh auth refresh failed. At https://github.com/login/device choose account: ${OWNER}"
fi

gh repo create "${REPO}" --private --source=. --remote=origin --push
echo "✅ Created and pushed to ${REMOTE_URL}"