.PHONY: install lock migrate run worker beat test lint typecheck format check

PYTHON_BOOTSTRAP ?= python3.10
VENV_DIR ?= ../.venv
PYTHON ?= $(VENV_DIR)/bin/python
PIP ?= $(PYTHON) -m pip
PIP_INSTALL_ARGS ?=
UPGRADE_PIP ?= false
LOCAL_ENV ?= DJANGO_SETTINGS_MODULE=config.settings.local DB_ENGINE=mysql MYSQL_HOST=$${MYSQL_HOST:-127.0.0.1} MYSQL_PORT=$${MYSQL_PORT:-3306} MYSQL_DATABASE=$${MYSQL_DATABASE:-alkaid_dev} MYSQL_USER=$${MYSQL_USER:-workflow} MYSQL_PASSWORD=$${MYSQL_PASSWORD:-workflow} MYSQL_SSL_DISABLED=$${MYSQL_SSL_DISABLED:-true} CELERY_BROKER_URL=$${CELERY_BROKER_URL:-amqp://workflow:workflow@127.0.0.1:5672//} CELERY_QUEUE=$${CELERY_QUEUE:-alkaid-local} CELERY_TASK_ALWAYS_EAGER=$${CELERY_TASK_ALWAYS_EAGER:-false}
TEST_ENV ?= DJANGO_SETTINGS_MODULE=config.settings.test CELERY_TASK_ALWAYS_EAGER=true

install:
	$(PYTHON_BOOTSTRAP) -m venv $(VENV_DIR)
	$(PYTHON) -m ensurepip --upgrade
	if [ "$(UPGRADE_PIP)" = "true" ]; then $(PIP) install $(PIP_INSTALL_ARGS) --upgrade pip; fi
	$(PIP) install $(PIP_INSTALL_ARGS) -r requirements-dev.lock

lock:
	uv pip compile pyproject.toml --extra dev --python-version 3.10 -o requirements-dev.lock

migrate:
	$(LOCAL_ENV) $(PYTHON) manage.py migrate

run:
	$(LOCAL_ENV) $(PYTHON) -m uvicorn config.asgi:application --host 127.0.0.1 --port 8000 --reload

worker:
	$(LOCAL_ENV) $(PYTHON) -m celery -A config worker --loglevel=INFO --pool=solo --queues=$${CELERY_QUEUE:-alkaid-local}

beat:
	$(LOCAL_ENV) $(PYTHON) -m celery -A config beat --loglevel=INFO

test:
	$(TEST_ENV) $(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy

format:
	$(PYTHON) -m ruff format .

check:
	$(TEST_ENV) $(PYTHON) manage.py check
	$(TEST_ENV) $(PYTHON) manage.py makemigrations --check --dry-run
	$(TEST_ENV) $(PYTHON) scripts/compile_product_config.py --check
	$(PYTHON) scripts/check_architecture.py
	$(TEST_ENV) $(PYTHON) -m pytest
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m mypy
