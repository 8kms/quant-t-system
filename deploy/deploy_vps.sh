#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: bash deploy/deploy_vps.sh user@host /remote/path"
  exit 1
fi

REMOTE="$1"
REMOTE_DIR="$2"

echo "Syncing project to $REMOTE:$REMOTE_DIR"
bash "$(dirname "$0")/sync_to_vps.sh" "$REMOTE" "$REMOTE_DIR"

echo "Starting Docker Compose on VPS"
ssh "$REMOTE" "cd '$REMOTE_DIR' && docker compose up -d --build"

echo "Deployment finished"

