#!/usr/bin/env bash
set -euo pipefail
echo "HaslGram / Teamgram VPS preflight (read-only)"
echo "Kernel: $(uname -s) $(uname -m)"
for exe in git python3 docker openssl; do
  if command -v "$exe" >/dev/null 2>&1; then
    echo "OK executable: $exe"
  else
    echo "MISSING executable: $exe"
  fi
done
if command -v docker >/dev/null 2>&1; then
  docker version --format 'Docker server version: {{.Server.Version}}' 2>/dev/null || echo "Docker daemon not available"
  docker compose version 2>/dev/null || echo "Docker Compose v2 not available"
fi
echo "--- Memory ---"
free -h 2>/dev/null || true
echo "--- Free storage ---"
df -h /opt/haslgram 2>/dev/null || df -h .
echo "--- Candidate MTProto ports (should be unused) ---"
if command -v ss >/dev/null 2>&1; then
  ss -ltn | awk 'NR==1 || /:(10443|11443|5222)([[:space:]]|$)/' || true
else
  echo "Cannot check listeners: ss not installed"
fi
echo "--- Existing HaslGram project (read-only) ---"
if [ -d /opt/haslgram/haslgram-gift-engine ]; then
  echo "Existing backend detected, will NOT be modified by stage.sh"
fi
echo "--- Existing Teamgram directory ---"
if [ -e /opt/haslgram/teamgram-server ]; then
  echo "Teamgram directory already exists. stage.sh will refuse to overwrite it."
else
  echo "No staged Teamgram installation yet."
fi
echo "--- Docker network overlap risk ---"
if command -v docker >/dev/null 2>&1; then
  docker network ls --format '{{.Name}}' 2>/dev/null || true
fi
echo "Done. Preflight never changes services, databases, volumes or firewall."
