#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEFAULT_BASE="$(cd "$PROJECT_ROOT/.." && pwd)"

DEV_BACKEND_PORT="${DEV_BACKEND_PORT:-8000}"
DEV_FRONTEND_PORT="${DEV_FRONTEND_PORT:-5174}"
DEV_BIND_ADDRESS="${DEV_BIND_ADDRESS:-0.0.0.0}"
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
CELERY_BROKER_URL="${CELERY_BROKER_URL:-amqp://workflow:workflow@127.0.0.1:5672//}"
CELERY_QUEUE="${CELERY_QUEUE:-alkaid-local}"
CELERY_TASK_ALWAYS_EAGER="${CELERY_TASK_ALWAYS_EAGER:-false}"

detect_lan_ip() {
  local interface_name candidate
  for interface_name in en0 en1 en2; do
    candidate="$(ifconfig "$interface_name" 2>/dev/null | awk '/inet / && $2 != "127.0.0.1" { print $2; exit }')"
    if [ -n "$candidate" ]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  ifconfig 2>/dev/null | awk '
    /inet / && $2 != "127.0.0.1" && $2 !~ /^169\.254\./ && $2 !~ /^198\.18\./ {
      print $2
      exit
    }
  '
}

DEV_LAN_IP="${DEV_LAN_IP:-$(detect_lan_ip)}"
DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1${DEV_LAN_IP:+,$DEV_LAN_IP}}"

is_truthy() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

if [ -z "${DEV_START_WORKER:-}" ]; then
  if is_truthy "$CELERY_TASK_ALWAYS_EAGER"; then
    DEV_START_WORKER=false
  else
    DEV_START_WORKER=true
  fi
fi

BACKEND_PYTHON="$PROJECT_ROOT/.venv/bin/python"

install_backend_deps() {
  cd "$PROJECT_ROOT"
  if [ ! -x "$BACKEND_PYTHON" ]; then
    "$PYTHON_BOOTSTRAP" -m venv .venv
  fi
  "$BACKEND_PYTHON" -m ensurepip --upgrade
  if [ "$UPGRADE_PIP" = "true" ]; then
    # shellcheck disable=SC2086
    "$BACKEND_PYTHON" -m pip install $PIP_INSTALL_ARGS --upgrade pip
  fi
  # shellcheck disable=SC2086
  "$BACKEND_PYTHON" -m pip install $PIP_INSTALL_ARGS -r "$PROJECT_ROOT/Alkaid-python/requirements-dev.lock"
  "$BACKEND_PYTHON" -m pip install -e "$PROJECT_ROOT/Alkaid-python" --no-deps
}

if ! "$BACKEND_PYTHON" -c "import django, uvicorn, pymysql, celery" >/dev/null 2>&1; then
  echo "Preparing backend virtual environment..."
  install_backend_deps
fi

if [ ! -d "$PROJECT_ROOT/Alkaid-react/node_modules" ] || [ ! -x "$PROJECT_ROOT/Alkaid-react/node_modules/.bin/vite" ]; then
  echo "Preparing frontend dependencies..."
  cd "$PROJECT_ROOT/Alkaid-react"
  zsh -lc "$NPM_INSTALL_CMD"
fi

mkdir -p "$ALKAID_RUNTIME_DIR"

if [ "${DEV_SPLIT_WINDOWS:-false}" = "true" ]; then
  BACKEND_RUNNER="$ALKAID_RUNTIME_DIR/dev-backend.command"
  WORKER_RUNNER="$ALKAID_RUNTIME_DIR/dev-worker.command"
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
export CELERY_BROKER_URL="$CELERY_BROKER_URL"
export CELERY_QUEUE="$CELERY_QUEUE"
export CELERY_TASK_ALWAYS_EAGER="$CELERY_TASK_ALWAYS_EAGER"
export DJANGO_ALLOWED_HOSTS="$DJANGO_ALLOWED_HOSTS"
cd "$PROJECT_ROOT/Alkaid-python"
"$BACKEND_PYTHON" manage.py migrate || exit 1
"$BACKEND_PYTHON" -m uvicorn config.asgi:application --host "$DEV_BIND_ADDRESS" --port "$DEV_BACKEND_PORT" --reload
EOF

  cat > "$WORKER_RUNNER" <<EOF
#!/bin/zsh
export DJANGO_SETTINGS_MODULE=config.settings.local
export DB_ENGINE=mysql
export MYSQL_HOST="$MYSQL_HOST"
export MYSQL_PORT="$MYSQL_PORT"
export MYSQL_DATABASE="$MYSQL_DATABASE"
export MYSQL_USER="$MYSQL_USER"
export MYSQL_PASSWORD="$MYSQL_PASSWORD"
export MYSQL_SSL_DISABLED="$MYSQL_SSL_DISABLED"
export CELERY_BROKER_URL="$CELERY_BROKER_URL"
export CELERY_QUEUE="$CELERY_QUEUE"
export CELERY_TASK_ALWAYS_EAGER="$CELERY_TASK_ALWAYS_EAGER"
cd "$PROJECT_ROOT/Alkaid-python"
"$BACKEND_PYTHON" -m celery -A config worker -l info -P solo -Q "$CELERY_QUEUE"
EOF

  cat > "$FRONTEND_RUNNER" <<EOF
#!/bin/zsh
export ALIOTH_API_TARGET="http://127.0.0.1:$DEV_BACKEND_PORT"
cd "$PROJECT_ROOT/Alkaid-react"
npm run dev -- --host "$DEV_BIND_ADDRESS" --port "$DEV_FRONTEND_PORT"
EOF

  chmod +x "$BACKEND_RUNNER" "$WORKER_RUNNER" "$FRONTEND_RUNNER"

  echo "Starting dev backend on http://${DEV_LAN_IP:-127.0.0.1}:$DEV_BACKEND_PORT"
  open -a Terminal "$BACKEND_RUNNER"

  if is_truthy "$DEV_START_WORKER" && ! is_truthy "$CELERY_TASK_ALWAYS_EAGER"; then
    echo "Starting Celery worker for queue $CELERY_QUEUE"
    open -a Terminal "$WORKER_RUNNER"
  fi

  echo "Starting dev frontend on http://${DEV_LAN_IP:-127.0.0.1}:$DEV_FRONTEND_PORT"
  open -a Terminal "$FRONTEND_RUNNER"

  echo "Dev services are starting in separate Terminal windows."
  exit 0
fi

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

assert_port_free() {
  local port="$1"
  local name="$2"
  if port_in_use "$port"; then
    echo "$name port $port is already in use. Stop the old service or set DEV_${name}_PORT." >&2
    exit 1
  fi
}

mask_secret_url() {
  printf '%s' "$1" | sed -E 's#(://[^:/@]+):[^@]+@#\1:********@#'
}

stop_tree() {
  local pid="$1"
  local name="$2"
  if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
    echo "Stopping $name..."
    pkill -TERM -P "$pid" >/dev/null 2>&1 || true
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    pkill -KILL -P "$pid" >/dev/null 2>&1 || true
    kill -KILL "$pid" >/dev/null 2>&1 || true
  fi
}

assert_port_free "$DEV_BACKEND_PORT" BACKEND
assert_port_free "$DEV_FRONTEND_PORT" FRONTEND

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.local}"
export DB_ENGINE=mysql
export MYSQL_HOST="$MYSQL_HOST"
export MYSQL_PORT="$MYSQL_PORT"
export MYSQL_DATABASE="$MYSQL_DATABASE"
export MYSQL_USER="$MYSQL_USER"
export MYSQL_PASSWORD="$MYSQL_PASSWORD"
export MYSQL_SSL_DISABLED="$MYSQL_SSL_DISABLED"
export CELERY_BROKER_URL="$CELERY_BROKER_URL"
export CELERY_QUEUE="$CELERY_QUEUE"
export CELERY_TASK_ALWAYS_EAGER="$CELERY_TASK_ALWAYS_EAGER"
export DJANGO_ALLOWED_HOSTS="$DJANGO_ALLOWED_HOSTS"

echo "Runtime config:"
echo "  Python: $BACKEND_PYTHON"
echo "  Django settings: $DJANGO_SETTINGS_MODULE"
echo "  Bind address: $DEV_BIND_ADDRESS"
echo "  Local frontend: http://127.0.0.1:$DEV_FRONTEND_PORT"
echo "  Local backend: http://127.0.0.1:$DEV_BACKEND_PORT"
if [ -n "$DEV_LAN_IP" ]; then
  echo "  LAN frontend: http://$DEV_LAN_IP:$DEV_FRONTEND_PORT"
  echo "  LAN backend: http://$DEV_LAN_IP:$DEV_BACKEND_PORT"
fi
echo "  Celery broker: $(mask_secret_url "$CELERY_BROKER_URL")"
echo "  Celery queue: $CELERY_QUEUE"
echo "  Celery eager: $CELERY_TASK_ALWAYS_EAGER"
echo "  Start worker: $DEV_START_WORKER"

echo "Migrating backend database..."
cd "$PROJECT_ROOT/Alkaid-python"
"$BACKEND_PYTHON" manage.py migrate

cleanup() {
  stop_tree "${BACKEND_PID:-}" backend
  stop_tree "${WORKER_PID:-}" worker
}
trap cleanup EXIT INT TERM

if is_truthy "$DEV_START_WORKER" && ! is_truthy "$CELERY_TASK_ALWAYS_EAGER"; then
  (
    cd "$PROJECT_ROOT/Alkaid-python"
    exec "$BACKEND_PYTHON" -m celery -A config worker -l info -P solo -Q "$CELERY_QUEUE"
  ) &
  WORKER_PID=$!
  echo "Starting Celery worker for queue $CELERY_QUEUE"
fi

(
  cd "$PROJECT_ROOT/Alkaid-python"
  exec "$BACKEND_PYTHON" -m uvicorn config.asgi:application --host "$DEV_BIND_ADDRESS" --port "$DEV_BACKEND_PORT" --reload
) &
BACKEND_PID=$!

echo "Starting dev backend on http://${DEV_LAN_IP:-127.0.0.1}:$DEV_BACKEND_PORT"
echo "Starting dev frontend on http://${DEV_LAN_IP:-127.0.0.1}:$DEV_FRONTEND_PORT"

export ALIOTH_API_TARGET="http://127.0.0.1:$DEV_BACKEND_PORT"
cd "$PROJECT_ROOT/Alkaid-react"
npm run dev -- --host "$DEV_BIND_ADDRESS" --port "$DEV_FRONTEND_PORT"
