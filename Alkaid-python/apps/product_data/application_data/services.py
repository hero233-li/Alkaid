import json
import logging

from django.conf import settings

from apps.jobs.commands import parse_menu_command
from apps.jobs.models import Job
from apps.mock_data.application_generator import generate_application_record
from apps.product_data.application_data.schemas import (
    ApplicationDataCommand,
    ApplicationDataOperation,
    ApplicationDataRecord,
    ApplicationDataSubmission,
)

logger = logging.getLogger(__name__)
APPLICATION_DATA_ENVIRONMENTS = ("环境1", "环境2", "环境3")


def execute_application_data_generation(job: Job) -> dict[str, object]:
    _, data = parse_menu_command(
        job,
        prefix="application_data",
        command_model=ApplicationDataCommand,
        operation_enum=ApplicationDataOperation,
    )
    submission = ApplicationDataSubmission.model_validate(data)
    if submission.environment not in APPLICATION_DATA_ENVIRONMENTS:
        raise ValueError("申请数据生成环境无效")
    start = job.id * 100_000
    logger.info(
        "application_data_generation_started",
        extra={"job_id": job.id, "trace_id": job.trace_id, "count": submission.count},
    )
    records = []
    result_bytes = 2  # JSON array brackets.
    for index in range(submission.count):
        value = generate_application_record(
            start + index,
            environment=submission.environment,
            birth_date=submission.birth_date,
            gender=submission.gender,
            company_type=submission.company_type,
            teller_no=submission.teller_no,
        )
        record = ApplicationDataRecord(id=index + 1, **value.__dict__).model_dump(
            mode="json", by_alias=True
        )
        result_bytes += len(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ) + (1 if records else 0)
        if result_bytes > settings.APPLICATION_DATA_MAX_RESULT_BYTES:
            raise ValueError("申请数据生成结果超过安全大小限制，请减少生成数量")
        records.append(record)
    return {"records": records}


def get_application_data_config() -> dict[str, object]:
    return {
        "environments": list(APPLICATION_DATA_ENVIRONMENTS),
        "companyTypes": [
            {"label": "公司", "value": "91"},
            {"label": "个体", "value": "92"},
        ],
        "genders": ["男", "女"],
        "maxCount": 1_000,
    }
