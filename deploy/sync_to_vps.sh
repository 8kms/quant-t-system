#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: bash deploy/sync_to_vps.sh user@host /remote/path"
  exit 1
fi

REMOTE="$1"
REMOTE_DIR="$2"

ssh "$REMOTE" "mkdir -p '$REMOTE_DIR'"
rsync -az --delete \
  --exclude ".git" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  --exclude ".DS_Store" \
  ./ "$REMOTE:$REMOTE_DIR/"

echo "Synced to $REMOTE:$REMOTE_DIR"

