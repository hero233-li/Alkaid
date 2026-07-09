import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.server")
django_application = get_asgi_application()

from apps.jobs.sse import JobLogSSEApplication  # noqa: E402

application = JobLogSSEApplication(django_application)
