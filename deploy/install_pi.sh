#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/whale-watch}"
SERVICE_USER="${SERVICE_USER:-pi}"
SERVICE_GROUP="${SERVICE_GROUP:-pi}"

sudo mkdir -p "$APP_DIR" /etc/whale-watch
sudo rsync -a --delete --exclude ".git" --exclude ".venv" ./ "$APP_DIR/"
sudo chown -R "$SERVICE_USER:$SERVICE_GROUP" "$APP_DIR"

if [ ! -f /etc/whale-watch/config.toml ]; then
  sudo cp "$APP_DIR/config.example.toml" /etc/whale-watch/config.toml
fi

sudo python3 -m venv "$APP_DIR/.venv"
sudo "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
sudo "$APP_DIR/.venv/bin/python" -m pip install -e "$APP_DIR"

sudo cp "$APP_DIR/deploy/whale-watch.service" /etc/systemd/system/whale-watch.service
sudo sed -i "s/User=pi/User=$SERVICE_USER/" /etc/systemd/system/whale-watch.service
sudo sed -i "s/Group=pi/Group=$SERVICE_GROUP/" /etc/systemd/system/whale-watch.service
sudo systemctl daemon-reload
sudo systemctl enable whale-watch.service

echo "Installed. Edit /etc/whale-watch/config.toml and /etc/whale-watch.env, then run:"
echo "  sudo systemctl restart whale-watch"
echo "  journalctl -u whale-watch -f"
