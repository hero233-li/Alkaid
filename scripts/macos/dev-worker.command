#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_PYTHON="$PROJECT_ROOT/.venv/bin/python"

if [ ! -x "$BACKEND_PYTHON" ]; then
  echo "Backend Python does not exist: $BACKEND_PYTHON" >&2
  exit 1
fi

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.local}"
export DB_ENGINE=mysql
export MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
export MYSQL_PORT="${MYSQL_PORT:-3306}"
export MYSQL_DATABASE="${MYSQL_DATABASE:-alkaid_dev}"
export MYSQL_USER="${MYSQL_USER:-workflow}"
export MYSQL_PASSWORD="${MYSQL_PASSWORD:-workflow}"
export MYSQL_SSL_DISABLED="${MYSQL_SSL_DISABLED:-true}"
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-amqp://workflow:workflow@127.0.0.1:5672//}"
export CELERY_QUEUE="${CELERY_QUEUE:-alkaid-local}"
export CELERY_TASK_ALWAYS_EAGER="${CELERY_TASK_ALWAYS_EAGER:-false}"

mask_secret_url() {
  printf '%s' "$1" | sed -E 's#(://[^:/@]+):[^@]+@#\1:********@#'
}

echo "Starting standalone Celery worker"
echo "  Python: $BACKEND_PYTHON"
echo "  Django settings: $DJANGO_SETTINGS_MODULE"
echo "  Broker: $(mask_secret_url "$CELERY_BROKER_URL")"
echo "  Queue: $CELERY_QUEUE"

cd "$PROJECT_ROOT/Alkaid-python"
exec "$BACKEND_PYTHON" -m celery -A config worker -l info -P solo -Q "$CELERY_QUEUE"
