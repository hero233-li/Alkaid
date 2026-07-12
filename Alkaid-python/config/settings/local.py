import os

from config.settings.base import *  # noqa: F403

DEBUG = True
# Deliberately slow this page in local development so the frontend loading
# animation can be inspected. Set the environment variable to 0 to disable.
VERIFICATION_APPROVAL_DEBUG_DELAY_SECONDS = float(
    os.getenv("VERIFICATION_APPROVAL_DEBUG_DELAY_SECONDS", "3")
)
