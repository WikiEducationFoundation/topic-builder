#!/bin/bash
# Deploy just the landing page. No service restart needed —
# nginx serves /opt/topic-builder/static/index.html directly.
# Usage: bash mcp_server/deploy_landing.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

set -a
source "$PROJECT_DIR/.env"
set +a

echo "==> Uploading landing.html to $DEPLOY_HOST:/opt/topic-builder/static/index.html"
scp -i "$PROJECT_DIR/$DEPLOY_KEY" "$SCRIPT_DIR/landing.html" \
    "$DEPLOY_USER@$DEPLOY_HOST:/opt/topic-builder/static/index.html"

echo "==> Done"
