from config.settings.base import *  # noqa: F403

DEBUG = True
WORKBENCH_ENABLED = env_bool("WORKBENCH_ENABLED", False)  # noqa: F405
