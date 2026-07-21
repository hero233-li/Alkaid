from enum import Enum
from typing import Any

from pydantic import BaseModel

from apps.jobs.models import Job

LEGACY_DOTTED_KIND_SUPPORT_UNTIL = "2026-10-31"


def parse_menu_command(
    job: Job,
    *,
    prefix: str,
    command_model: type[BaseModel],
    operation_enum: type[Enum],
) -> tuple[Any, dict[str, Any]]:
    """Read canonical commands; dotted kinds expire after the documented retention window."""
    if "operation" in job.payload:
        command = command_model.model_validate(job.payload)
        return command.operation, command.data
    legacy_operation = operation_enum(job.kind.removeprefix(f"{prefix}."))
    return legacy_operation, job.payload
