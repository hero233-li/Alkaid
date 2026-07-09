#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEFAULT_BASE="$(cd "$PROJECT_ROOT/.." && pwd)"

DEV_BACKEND_PORT="${DEV_BACKEND_PORT:-8000}"
DEV_FRONTEND_PORT="${DEV_FRONTEND_PORT:-5174}"
ALKAID_RUNTIME_DIR="${ALKAID_RUNTIME_DIR:-$DEFAULT_BASE/Alkaid-runtime}"
PYTHON_BOOTSTRAP="${PYTHON_BOOTSTRAP:-python3.10}"
NPM_INSTALL_CMD="${NPM_INSTALL_CMD:-npm ci}"
UPGRADE_PIP="${UPGRADE_PIP:-false}"
PIP_INSTALL_ARGS="${PIP_INSTALL_ARGS:-}"
MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_DATABASE="${MYSQL_DATABASE:-alkaid_dev}"
MYSQL_USER="${MYSQL_USER:-workflow}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-workflow}"
MYSQL_SSL_DISABLED="${MYSQL_SSL_DISABLED:-true}"

BACKEND_PYTHON="$PROJECT_ROOT/Alkaid-python/.venv/bin/python"

install_backend_deps() {
  cd "$PROJECT_ROOT/Alkaid-python"
  if [ ! -x "$BACKEND_PYTHON" ]; then
    "$PYTHON_BOOTSTRAP" -m venv .venv
  fi
  "$BACKEND_PYTHON" -m ensurepip --upgrade
  if [ "$UPGRADE_PIP" = "true" ]; then
    # shellcheck disable=SC2086
    "$BACKEND_PYTHON" -m pip install $PIP_INSTALL_ARGS --upgrade pip
  fi
  # shellcheck disable=SC2086
  "$BACKEND_PYTHON" -m pip install $PIP_INSTALL_ARGS -r requirements-dev.lock
  "$BACKEND_PYTHON" -m pip install -e . --no-deps
}

if ! "$BACKEND_PYTHON" -c "import django, uvicorn, pymysql" >/dev/null 2>&1; then
  echo "Preparing backend virtual environment..."
  install_backend_deps
fi

if [ ! -d "$PROJECT_ROOT/Alkaid-react/node_modules" ]; then
  echo "Preparing frontend dependencies..."
  cd "$PROJECT_ROOT/Alkaid-react"
  zsh -lc "$NPM_INSTALL_CMD"
fi

mkdir -p "$ALKAID_RUNTIME_DIR"

if [ "${DEV_SPLIT_WINDOWS:-false}" = "true" ]; then
  BACKEND_RUNNER="$ALKAID_RUNTIME_DIR/dev-backend.command"
  FRONTEND_RUNNER="$ALKAID_RUNTIME_DIR/dev-frontend.command"

  cat > "$BACKEND_RUNNER" <<EOF
#!/bin/zsh
export DJANGO_SETTINGS_MODULE=config.settings.local
export DB_ENGINE=mysql
export MYSQL_HOST="$MYSQL_HOST"
export MYSQL_PORT="$MYSQL_PORT"
export MYSQL_DATABASE="$MYSQL_DATABASE"
export MYSQL_USER="$MYSQL_USER"
export MYSQL_PASSWORD="$MYSQL_PASSWORD"
export MYSQL_SSL_DISABLED="$MYSQL_SSL_DISABLED"
export CELERY_TASK_ALWAYS_EAGER=true
cd "$PROJECT_ROOT/Alkaid-python"
"$BACKEND_PYTHON" manage.py migrate || exit 1
"$BACKEND_PYTHON" -m uvicorn config.asgi:application --host 127.0.0.1 --port "$DEV_BACKEND_PORT" --reload
EOF

  cat > "$FRONTEND_RUNNER" <<EOF
#!/bin/zsh
export ALIOTH_API_TARGET="http://127.0.0.1:$DEV_BACKEND_PORT"
cd "$PROJECT_ROOT/Alkaid-react"
npm run dev -- --port "$DEV_FRONTEND_PORT"
EOF

  chmod +x "$BACKEND_RUNNER" "$FRONTEND_RUNNER"

  echo "Starting dev backend on http://127.0.0.1:$DEV_BACKEND_PORT"
  open -a Terminal "$BACKEND_RUNNER"

  echo "Starting dev frontend on http://127.0.0.1:$DEV_FRONTEND_PORT"
  open -a Terminal "$FRONTEND_RUNNER"

  echo "Dev services are starting in separate Terminal windows."
  exit 0
fi

BACKEND_LOG="$ALKAID_RUNTIME_DIR/dev-backend.log"

export DJANGO_SETTINGS_MODULE=config.settings.local
export DB_ENGINE=mysql
export MYSQL_HOST="$MYSQL_HOST"
export MYSQL_PORT="$MYSQL_PORT"
export MYSQL_DATABASE="$MYSQL_DATABASE"
export MYSQL_USER="$MYSQL_USER"
export MYSQL_PASSWORD="$MYSQL_PASSWORD"
export MYSQL_SSL_DISABLED="$MYSQL_SSL_DISABLED"
export CELERY_TASK_ALWAYS_EAGER=true

echo "Migrating backend database..."
cd "$PROJECT_ROOT/Alkaid-python"
"$BACKEND_PYTHON" manage.py migrate

cleanup() {
  if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    echo "Stopping backend..."
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

(
  cd "$PROJECT_ROOT/Alkaid-python"
  exec "$BACKEND_PYTHON" -m uvicorn config.asgi:application --host 127.0.0.1 --port "$DEV_BACKEND_PORT" --reload
) > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "Starting dev backend on http://127.0.0.1:$DEV_BACKEND_PORT"
echo "Backend log: $BACKEND_LOG"
echo "Starting dev frontend on http://127.0.0.1:$DEV_FRONTEND_PORT"

export ALIOTH_API_TARGET="http://127.0.0.1:$DEV_BACKEND_PORT"
cd "$PROJECT_ROOT/Alkaid-react"
npm run dev -- --port "$DEV_FRONTEND_PORT"
