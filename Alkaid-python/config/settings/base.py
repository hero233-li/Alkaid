import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-only-unsafe-secret-key")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.jobs",
    "apps.product_data",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

database_engine = os.getenv("DB_ENGINE", "mysql")
if database_engine != "mysql":
    raise ValueError("DB_ENGINE must be mysql outside test settings")

mysql_options = {
    "charset": "utf8mb4",
    "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
}
if env_bool("MYSQL_SSL_DISABLED"):
    mysql_options["ssl_disabled"] = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "workflow"),
        "USER": os.getenv("MYSQL_USER", "workflow"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", "workflow"),
        "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": mysql_options,
    }
}

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
FRONTEND_DIST_DIR = os.getenv("FRONTEND_DIST_DIR", "")

APP_VERSION = os.getenv("APP_VERSION", "dev")
EXTERNAL_SYSTEM_MODE = os.getenv("EXTERNAL_SYSTEM_MODE", "mock").strip().lower()
if EXTERNAL_SYSTEM_MODE not in {"mock", "real"}:
    raise ValueError("EXTERNAL_SYSTEM_MODE must be mock or real")
JOB_RETENTION_HOURS = int(os.getenv("JOB_RETENTION_HOURS", "720"))
JOB_LOG_RETENTION_HOURS = int(os.getenv("JOB_LOG_RETENTION_HOURS", "168"))
JOB_MAX_LOGS = int(os.getenv("JOB_MAX_LOGS", "5000"))
JOB_MAX_HTTP_BODY_BYTES = int(os.getenv("JOB_MAX_HTTP_BODY_BYTES", "65536"))
JOB_RECONCILE_BATCH_SIZE = int(os.getenv("JOB_RECONCILE_BATCH_SIZE", "500"))
JOB_SSE_POLL_SECONDS = float(os.getenv("JOB_SSE_POLL_SECONDS", "1"))
JOB_SSE_HEARTBEAT_SECONDS = float(os.getenv("JOB_SSE_HEARTBEAT_SECONDS", "15"))
PRODUCT_APPLICATION_TIMEOUT_SECONDS = int(os.getenv("PRODUCT_APPLICATION_TIMEOUT_SECONDS", "300"))
APPLICATION_LINK_TIMEOUT_SECONDS = int(os.getenv("APPLICATION_LINK_TIMEOUT_SECONDS", "120"))
BUSINESS_ACCESS_TIMEOUT_SECONDS = int(os.getenv("BUSINESS_ACCESS_TIMEOUT_SECONDS", "120"))
VERIFICATION_APPROVAL_TIMEOUT_SECONDS = int(
    os.getenv("VERIFICATION_APPROVAL_TIMEOUT_SECONDS", "120")
)
APPLICATION_DATA_TIMEOUT_SECONDS = int(os.getenv("APPLICATION_DATA_TIMEOUT_SECONDS", "300"))
CARD_STATUS_TIMEOUT_SECONDS = int(os.getenv("CARD_STATUS_TIMEOUT_SECONDS", "120"))
LOAN_STATUS_TIMEOUT_SECONDS = int(os.getenv("LOAN_STATUS_TIMEOUT_SECONDS", "120"))
MOCK_FIXED_SYSTEM_TOKEN = os.getenv("MOCK_FIXED_SYSTEM_TOKEN", "mock-fixed-token")
MOCK_PRODUCT_BASE_URL = os.getenv("MOCK_PRODUCT_BASE_URL", "").rstrip("/")
APPLICATION_LINK_BASE_URL = os.getenv("APPLICATION_LINK_BASE_URL", "").rstrip("/")
APPLICATION_LINK_API_TOKEN = os.getenv("APPLICATION_LINK_API_TOKEN", "")
APPLICATION_LINK_FORM_SIGN = os.getenv("APPLICATION_LINK_FORM_SIGN", "")
APPLICATION_LINK_SIGN_REQUIRED = env_bool("APPLICATION_LINK_SIGN_REQUIRED")
APPLICATION_LINK_TIMESTAMP_FORMAT = os.getenv(
    "APPLICATION_LINK_TIMESTAMP_FORMAT", "%Y%m%d%H%M%S"
)
BUSINESS_ACCESS_BASE_URL = os.getenv("BUSINESS_ACCESS_BASE_URL", "").rstrip("/")
BUSINESS_ACCESS_API_TOKEN = os.getenv("BUSINESS_ACCESS_API_TOKEN", "")
VERIFICATION_APPROVAL_BASE_URL = os.getenv("VERIFICATION_APPROVAL_BASE_URL", "").rstrip("/")
VERIFICATION_APPROVAL_API_TOKEN = os.getenv("VERIFICATION_APPROVAL_API_TOKEN", "")
# Kept at zero outside local development so production never sleeps in a view.
VERIFICATION_APPROVAL_DEBUG_DELAY_SECONDS = float(
    os.getenv("VERIFICATION_APPROVAL_DEBUG_DELAY_SECONDS", "0")
)
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))
HTTP_CONNECT_TIMEOUT_SECONDS = float(os.getenv("HTTP_CONNECT_TIMEOUT_SECONDS", "5"))
HTTP_WRITE_TIMEOUT_SECONDS = float(os.getenv("HTTP_WRITE_TIMEOUT_SECONDS", "10"))
HTTP_POOL_TIMEOUT_SECONDS = float(os.getenv("HTTP_POOL_TIMEOUT_SECONDS", "5"))
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "2"))
HTTP_RETRY_BACKOFF_SECONDS = float(os.getenv("HTTP_RETRY_BACKOFF_SECONDS", "0.2"))
HTTP_RETRY_MAX_BACKOFF_SECONDS = float(os.getenv("HTTP_RETRY_MAX_BACKOFF_SECONDS", "5"))

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "amqp://workflow:workflow@127.0.0.1:5672//")
CELERY_TASK_DEFAULT_QUEUE = os.getenv("CELERY_QUEUE", "alkaid-local")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER")
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_BACKEND = None
CELERY_TASK_TRACK_STARTED = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "reconcile-expired-jobs-every-minute": {
        "task": "apps.jobs.tasks.reconcile_expired_jobs",
        "schedule": 60.0,
    },
    "cleanup-expired-jobs-hourly": {
        "task": "apps.jobs.tasks.cleanup_expired_jobs",
        "schedule": 3600.0,
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "apps.core.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
