#!/usr/bin/env bash
# Brings the demo up in one container: seed the database if it is empty, start
# the Flask API in the background, then hand the foreground to Shiny.
set -euo pipefail

cd /app/dashboard

echo "==> Checking database"
python seed_database.py

echo "==> Starting Flask API on 127.0.0.1:${API_PORT:-5000}"
gunicorn api:app \
    --bind "127.0.0.1:${API_PORT:-5000}" \
    --workers 2 \
    --threads 4 \
    --timeout 600 \
    --access-logfile - \
    &

# Give the API a moment so the dashboard's first render finds it listening.
for _ in $(seq 1 30); do
    python -c "import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1', int('${API_PORT:-5000}')))==0 else 1)" && break
    sleep 1
done

echo "==> Starting Shiny dashboard on 0.0.0.0:${PORT:-8000}"
exec shiny run --host 0.0.0.0 --port "${PORT:-8000}" app.py
