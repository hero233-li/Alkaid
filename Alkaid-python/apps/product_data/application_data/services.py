import logging

from apps.integrations.application_data.generator import generate_application_record
from apps.jobs.models import Job
from apps.product_data.application_data.schemas import (
    ApplicationDataRecord,
    ApplicationDataSubmission,
)

logger = logging.getLogger(__name__)
APPLICATION_DATA_ENVIRONMENTS = ("环境1", "环境2", "环境3")


def execute_application_data_generation(job: Job) -> dict[str, object]:
    submission = ApplicationDataSubmission.model_validate(job.payload)
    if submission.environment not in APPLICATION_DATA_ENVIRONMENTS:
        raise ValueError("申请数据生成环境无效")
    start = job.id * 100_000
    logger.info(
        "application_data_generation_started",
        extra={"job_id": job.id, "trace_id": job.trace_id, "count": submission.count},
    )
    records = []
    for index in range(submission.count):
        value = generate_application_record(
            start + index,
            environment=submission.environment,
            current_date=submission.current_date,
            age=submission.age,
            gender=submission.gender,
            company_type=submission.company_type,
        )
        records.append(
            ApplicationDataRecord(id=index + 1, **value.__dict__).model_dump(
                mode="json", by_alias=True
            )
        )
    return {"records": records}


def get_application_data_config() -> dict[str, object]:
    return {
        "environments": list(APPLICATION_DATA_ENVIRONMENTS),
        "companyTypes": [
            {"label": "公司", "value": "91"},
            {"label": "个体", "value": "92"},
        ],
        "maxCount": 100_000,
    }
