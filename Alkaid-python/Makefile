.PHONY: install lock migrate run worker beat test lint check

PYTHON_BOOTSTRAP ?= python3.10
PYTHON ?= .venv/bin/python
PIP ?= $(PYTHON) -m pip
PIP_INSTALL_ARGS ?=
UPGRADE_PIP ?= false
LOCAL_ENV ?= DJANGO_SETTINGS_MODULE=config.settings.local DB_ENGINE=mysql MYSQL_HOST=$${MYSQL_HOST:-127.0.0.1} MYSQL_PORT=$${MYSQL_PORT:-3306} MYSQL_DATABASE=$${MYSQL_DATABASE:-alkaid_dev} MYSQL_USER=$${MYSQL_USER:-workflow} MYSQL_PASSWORD=$${MYSQL_PASSWORD:-workflow} MYSQL_SSL_DISABLED=$${MYSQL_SSL_DISABLED:-true} CELERY_TASK_ALWAYS_EAGER=true
TEST_ENV ?= DJANGO_SETTINGS_MODULE=config.settings.test CELERY_TASK_ALWAYS_EAGER=true

install:
	$(PYTHON_BOOTSTRAP) -m venv .venv
	$(PYTHON) -m ensurepip --upgrade
	if [ "$(UPGRADE_PIP)" = "true" ]; then $(PIP) install $(PIP_INSTALL_ARGS) --upgrade pip; fi
	$(PIP) install $(PIP_INSTALL_ARGS) -r requirements-dev.lock
	$(PIP) install -e . --no-deps

lock:
	uv lock

migrate:
	$(LOCAL_ENV) $(PYTHON) manage.py migrate

run:
	$(LOCAL_ENV) $(PYTHON) -m uvicorn config.asgi:application --host 127.0.0.1 --port 8000 --reload

worker:
	DJANGO_SETTINGS_MODULE=config.settings.local $(PYTHON) -m celery -A config worker --loglevel=INFO --queues=$${CELERY_QUEUE:-workflow-dev}

beat:
	DJANGO_SETTINGS_MODULE=config.settings.local $(PYTHON) -m celery -A config beat --loglevel=INFO

test:
	$(TEST_ENV) $(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

check:
	$(LOCAL_ENV) $(PYTHON) manage.py check
	$(TEST_ENV) $(PYTHON) manage.py makemigrations --check --dry-run
	$(TEST_ENV) $(PYTHON) -m pytest
	$(PYTHON) -m ruff check .
