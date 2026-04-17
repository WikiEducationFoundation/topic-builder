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

echo "==> Installing dependencies"
$SSH_CMD "cd $REMOTE_DIR && python3 -m venv venv 2>/dev/null; $REMOTE_DIR/venv/bin/pip install -q -r $REMOTE_DIR/app/requirements.txt"

echo "==> Installing systemd service"
$SSH_CMD "cat > /etc/systemd/system/topic-builder.service << 'EOF'
[Unit]
Description=Wikipedia Topic Builder MCP Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/topic-builder/app
ExecStart=/opt/topic-builder/venv/bin/python server.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF"

echo "==> Creating data directories"
$SSH_CMD "mkdir -p $REMOTE_DIR/data $REMOTE_DIR/exports $REMOTE_DIR/logs"

echo "==> Configuring nginx"
$SSH_CMD "cat > /etc/nginx/sites-available/topic-builder << 'NGINX'
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
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host 127.0.0.1:8000;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
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

echo "==> Starting service"
$SSH_CMD "systemctl daemon-reload && systemctl enable topic-builder && systemctl restart topic-builder"

echo "==> Checking status"
$SSH_CMD "sleep 2 && systemctl is-active topic-builder && curl -s http://127.0.0.1:8000/mcp/ | head -c 200 || echo 'Service may still be starting...'"

echo "==> Done"
