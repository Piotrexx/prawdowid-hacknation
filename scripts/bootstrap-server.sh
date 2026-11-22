#!/usr/bin/env bash
# Przygotowanie świeżej Ubuntu 24.04: Docker + compose, narzędzia, swap.
# Uruchom jako zwykły użytkownik z sudo: bash scripts/bootstrap-server.sh
set -euo pipefail

SWAP_SIZE="${SWAP_SIZE:-4G}"

echo "==> Pakiety systemowe"
sudo apt-get update
sudo apt-get install -y ca-certificates curl git jq

if ! command -v docker > /dev/null 2>&1; then
  echo "==> Docker"
  curl -fsSL https://get.docker.com | sudo sh
else
  echo "==> Docker już zainstalowany: $(docker --version)"
fi
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

if ! swapon --show | grep -q '/swapfile'; then
  echo "==> Swap ${SWAP_SIZE}"
  sudo fallocate -l "$SWAP_SIZE" /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
  echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-prawdowid.conf > /dev/null
  sudo sysctl --system > /dev/null
else
  echo "==> Swap już istnieje"
fi

echo
echo "Gotowe. Wyloguj się i zaloguj ponownie (albo: newgrp docker), żeby grupa docker zadziałała."
docker compose version 2> /dev/null || sudo docker compose version
free -h
