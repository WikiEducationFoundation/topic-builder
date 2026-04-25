#!/bin/bash
# Deploy the MCP server to the remote host.
# Usage: bash mcp_server/deploy.sh
#
# Expects .env to contain:
#   DEPLOY_HOST=...
#   DEPLOY_USER=...
#   DEPLOY_KEY=...

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env
set -a
source "$PROJECT_DIR/.env"
set +a

SSH_CMD="ssh -i $PROJECT_DIR/$DEPLOY_KEY $DEPLOY_USER@$DEPLOY_HOST"
SCP_CMD="scp -i $PROJECT_DIR/$DEPLOY_KEY"

REMOTE_DIR="/opt/topic-builder"

echo "==> Syncing mcp_server/ to $DEPLOY_HOST:$REMOTE_DIR/app/"
$SSH_CMD "mkdir -p $REMOTE_DIR/app $REMOTE_DIR/static"
$SCP_CMD "$SCRIPT_DIR/server.py" "$SCRIPT_DIR/wikipedia_api.py" "$SCRIPT_DIR/db.py" "$SCRIPT_DIR/server_instructions.md" "$SCRIPT_DIR/requirements.txt" "$DEPLOY_USER@$DEPLOY_HOST:$REMOTE_DIR/app/"
$SCP_CMD "$SCRIPT_DIR/landing.html" "$DEPLOY_USER@$DEPLOY_HOST:$REMOTE_DIR/static/index.html"

echo "==> Syncing admin scripts to $REMOTE_DIR/bin/"
$SSH_CMD "mkdir -p $REMOTE_DIR/bin"
$SCP_CMD "$PROJECT_DIR/scripts/session_status.py" "$DEPLOY_USER@$DEPLOY_HOST:$REMOTE_DIR/bin/status.py"

echo "==> Installing dependencies"
$SSH_CMD "cd $REMOTE_DIR && python3 -m venv venv 2>/dev/null; $REMOTE_DIR/venv/bin/pip install -q -r $REMOTE_DIR/app/requirements.txt"

echo "==> Retiring legacy single-worker service if present"
# The pre-multi-worker deploy used a single 'topic-builder.service'.
# Stop and remove it so the new template instances are the sole live
# workers. Idempotent (no-op when the legacy unit isn't installed).
$SSH_CMD "systemctl stop topic-builder.service 2>/dev/null || true"
$SSH_CMD "systemctl disable topic-builder.service 2>/dev/null || true"
$SSH_CMD "rm -f /etc/systemd/system/topic-builder.service"

echo "==> Installing systemd template unit"
# Template unit: %i is the port (e.g. topic-builder@8000.service runs
# the server with PORT=8000). Two instances (8000 + 8001) run behind
# nginx with sticky session-header routing — see nginx upstream block
# below. Each worker is a separate Python process with its own asyncio
# event loop, so a heavy tool call on one session can't block
# handshakes on the other worker.
$SSH_CMD "cat > /etc/systemd/system/topic-builder@.service << 'EOF'
[Unit]
Description=Wikipedia Topic Builder MCP Server (port %i)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/topic-builder/app
ExecStart=/opt/topic-builder/venv/bin/python server.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=PORT=%i

[Install]
WantedBy=multi-user.target
EOF"

echo "==> Creating data directories"
$SSH_CMD "mkdir -p $REMOTE_DIR/data $REMOTE_DIR/exports $REMOTE_DIR/logs"

echo "==> Configuring nginx"
$SSH_CMD "cat > /etc/nginx/sites-available/topic-builder << 'NGINX'
upstream topic_builder_backend {
    # Sticky session routing. MCP keeps per-session state in an
    # in-memory dict per worker process (StreamableHTTPSessionManager
    # ._server_instances), keyed by the Mcp-Session-Id header.
    # Without consistent hashing on this header, a session started
    # on worker A could land on worker B for follow-up requests and
    # 404 with 'unknown session id'.
    #
    # New sessions (no Mcp-Session-Id yet) all hash to the same
    # bucket — imbalanced but harmless until load grows. If session-
    # establishment becomes a bottleneck, add a request-id-based
    # second-level discriminator here.
    hash \$http_mcp_session_id consistent;
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
}

server {
    server_name topic-builder.wikiedu.org;

    root /opt/topic-builder/static;

    location = / {
        try_files /index.html =404;
    }

    location /exports/ {
        alias /opt/topic-builder/exports/;
        add_header Content-Disposition 'attachment';
        add_header Content-Type 'text/csv; charset=utf-8';
    }

    location /mcp {
        proxy_pass http://topic_builder_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;

        # Absorb heavy tool calls that hold a worker's event loop
        # past the 60s default. Multi-worker means one busy session
        # doesn't stall the other worker's handshakes, but a single
        # tool call can still take 5 minutes. Internal Python tool
        # budgets are 300s on the longest runners.
        proxy_connect_timeout 30s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/topic-builder.wikiedu.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/topic-builder.wikiedu.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    if (\$host = topic-builder.wikiedu.org) {
        return 301 https://\$host\$request_uri;
    }
    listen 80;
    server_name topic-builder.wikiedu.org;
    return 404;
}
NGINX
nginx -t && systemctl reload nginx"

echo "==> Starting workers"
$SSH_CMD "systemctl daemon-reload && systemctl enable topic-builder@8000.service topic-builder@8001.service && systemctl restart topic-builder@8000.service topic-builder@8001.service"

echo "==> Checking status"
$SSH_CMD "sleep 2 && systemctl is-active topic-builder@8000.service && systemctl is-active topic-builder@8001.service && curl -s http://127.0.0.1:8000/mcp/ | head -c 100 && echo && curl -s http://127.0.0.1:8001/mcp/ | head -c 100 || echo 'Workers may still be starting...'"

echo "==> Done"
