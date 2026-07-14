#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/spark-ui.service"

if [ ! -f "$SERVICE_FILE" ]; then
  echo "Error: spark-ui.service not found in $SCRIPT_DIR"
  exit 1
fi

echo "Installing Spark UI service..."
echo "Make sure you've edited spark-ui.service with your username and paths first!"
echo ""

sudo cp "$SERVICE_FILE" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable spark-ui
sudo systemctl start spark-ui
sudo systemctl status spark-ui
