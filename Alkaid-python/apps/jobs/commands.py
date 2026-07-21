from enum import Enum
from typing import Any, Protocol, TypeVar, cast

from pydantic import BaseModel

from apps.jobs.compatibility import ensure_legacy_job_compatibility
from apps.jobs.models import Job

OperationT = TypeVar("OperationT", bound=Enum)


class MenuCommand(Protocol[OperationT]):
    operation: OperationT
    data: dict[str, Any]


def parse_menu_command(
    job: Job,
    *,
    prefix: str,
    command_model: type[BaseModel],
    operation_enum: type[OperationT],
) -> tuple[OperationT, dict[str, Any]]:
    """Read canonical commands; dotted kinds expire after the documented retention window."""
    if "operation" in job.payload:
        command = cast(MenuCommand[OperationT], command_model.model_validate(job.payload))
        return command.operation, command.data
    ensure_legacy_job_compatibility()
    legacy_operation = operation_enum(job.kind.removeprefix(f"{prefix}."))
    return legacy_operation, job.payload
