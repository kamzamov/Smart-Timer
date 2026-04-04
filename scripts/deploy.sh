#!/usr/bin/env bash
set -euo pipefail

SSH_KEY="/home/kamzamov/.ssh/se_toolkit_key"
REMOTE_USER="root"
REMOTE_HOST="10.93.25.19"
REMOTE_DIR="/opt/smart-timer"
SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no"
SCP_CMD="scp -i $SSH_KEY -o StrictHostKeyChecking=no -r"

echo "=== Smart Timer Deploy ==="

# Create remote directory
echo "[1/4] Creating remote directory..."
$SSH_CMD $REMOTE_USER@$REMOTE_HOST "mkdir -p $REMOTE_DIR"

# Copy project files
echo "[2/4] Copying project files..."
$SCP_CMD . "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"

# Copy .env if not exists
echo "[3/4] Setting up .env..."
$SSH_CMD $REMOTE_USER@$REMOTE_HOST "cd $REMOTE_DIR && [ -f .env ] || cp .env.example .env"

# Build and start
echo "[4/4] Building and starting services..."
$SSH_CMD $REMOTE_USER@$REMOTE_HOST "cd $REMOTE_DIR && docker compose up -d --build"

echo ""
echo "=== Deploy complete ==="
echo "Frontend: http://$REMOTE_HOST:3000"
echo "Backend API: http://$REMOTE_HOST:8000/docs"
echo ""
echo "Check logs: $SSH_CMD $REMOTE_USER@$REMOTE_HOST 'cd $REMOTE_DIR && docker compose logs -f'"
