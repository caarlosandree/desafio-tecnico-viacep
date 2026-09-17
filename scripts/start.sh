#!/bin/sh
# Aplica as migrations pendentes e inicia a API.
set -e

echo "Aplicando migrations..."
alembic upgrade head

echo "Iniciando a API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
