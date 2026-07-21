import hashlib
import hmac
import json
from typing import Any

from django.conf import settings

from apps.core.errors import ContextIntegrityError
from apps.integrations.verification_approval.models import VerificationTask
from apps.jobs.models import Job, JobStatus
from apps.product_data.verification_approval.schemas import VerificationContextProof


def _dump_task(task: VerificationTask) -> dict[str, Any]:
    return task.model_dump(mode="json", by_alias=True)


def _digest(source_job_id: int, version: int, context: dict[str, Any]) -> str:
    serialized = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    message = f"{source_job_id}:{version}:{serialized}".encode()
    signing_key = settings.VERIFICATION_CONTEXT_SIGNING_KEY.encode()
    return hmac.new(signing_key, message, hashlib.sha256).hexdigest()


def build_context_proof(job: Job, task: VerificationTask) -> VerificationContextProof:
    version = settings.VERIFICATION_CONTEXT_PROOF_VERSION
    return VerificationContextProof(
        source_job_id=job.id,
        version=version,
        digest=_digest(job.id, version, _dump_task(task)),
    )


def validate_context_proof(
    proof: VerificationContextProof,
    task: VerificationTask,
) -> None:
    expected_version = settings.VERIFICATION_CONTEXT_PROOF_VERSION
    if proof.version != expected_version:
        raise ContextIntegrityError("核实任务上下文版本已经过期，请重新查询")
    context = _dump_task(task)
    expected = _digest(proof.source_job_id, proof.version, context)
    if not hmac.compare_digest(proof.digest, expected):
        raise ContextIntegrityError("核实任务上下文校验失败，请重新查询")
    source = Job.objects.filter(id=proof.source_job_id, status=JobStatus.SUCCESS).first()
    if source is None or source.result.get("task") != context:
        raise ContextIntegrityError("核实任务上下文来源无效或已经过期，请重新查询")
