from config.settings.base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "*")  # noqa: F405
WORKBENCH_ENABLED = env_bool("WORKBENCH_ENABLED", True)  # noqa: F405
