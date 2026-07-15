from __future__ import annotations

import time
from typing import Any

from django.db import OperationalError, transaction

from apps.jobs.models import MockToolState


def get_or_create_locked_mock_state(
    namespace: str,
    key: str,
    payload: dict[str, Any],
    *,
    lock_retries: int = 5,
) -> MockToolState:
    """Create once under a unique key and tolerate short SQLite/MySQL lock races."""
    for attempt in range(lock_retries):
        try:
            with transaction.atomic():
                state, created = MockToolState.objects.get_or_create(
                    namespace=namespace,
                    key=key,
                    defaults={"payload": payload},
                )
                if not created:
                    state = MockToolState.objects.select_for_update().get(pk=state.pk)
                return state
        except OperationalError as exc:
            if "lock" not in str(exc).lower() or attempt + 1 == lock_retries:
                raise
            time.sleep(0.01 * (attempt + 1))
    raise RuntimeError("unreachable")
