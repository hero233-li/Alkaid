import json
from datetime import date

import pytest

from apps.integrations.application_data.generator import (
    generate_application_record,
    validate_social_credit_code,
)
from apps.integrations.card_status.mock_store import CARD_MOCK_STORE
from apps.integrations.loan_status.mock_store import LOAN_MOCK_STORE
from apps.jobs.models import Job, JobStatus


@pytest.fixture(autouse=True)
def reset_mock_tools() -> None:
    CARD_MOCK_STORE.reset()
    LOAN_MOCK_STORE.reset()


def _run_job(client, capture, path: str, *, key: str, body: dict[str, object]) -> Job:
    with capture(execute=True):
        response = client.post(
            path,
            data=json.dumps(body),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY=key,
            HTTP_X_TRACE_ID=f"trace-{key}",
        )
    assert response.status_code == 202, response.content
    job = Job.objects.get(id=response.json()["data"]["id"])
    assert job.status == JobStatus.SUCCESS, job.error_message
    return job


def test_generated_mock_fields_are_unique_for_one_hundred_thousand_records() -> None:
    names: set[str] = set()
    certificates: set[str] = set()
    cards: set[str] = set()
    phones: set[str] = set()
    companies: set[str] = set()
    credit_codes: set[str] = set()

    for sequence in range(100_000):
        record = generate_application_record(
            sequence,
            environment="环境1",
            current_date=date(2026, 7, 14),
            age=40,
            gender="男",
            company_type="91" if sequence % 2 else "92",
        )
        names.add(record.customer_name)
        certificates.add(record.certificate_no)
        cards.add(record.card_no)
        phones.add(record.phone)
        companies.add(record.company_name)
        credit_codes.add(record.company_credit_code)
        assert validate_social_credit_code(record.company_credit_code)

    assert len(names) == 100_000
    assert len(certificates) == 100_000
    assert len(cards) == 100_000
    assert len(phones) == 100_000
    assert len(companies) == 100_000
    assert len(credit_codes) == 100_000


@pytest.mark.django_db
def test_application_data_generation_runs_as_job(
    client,
    django_capture_on_commit_callbacks,
) -> None:
    job = _run_job(
        client,
        django_capture_on_commit_callbacks,
        "/api/product-data/tools/application-data/generate",
        key="application-data",
        body={
            "environment": "环境1",
            "currentDate": "2026-07-14",
            "birthDate": "1986-07-14",
            "age": 40,
            "gender": "男",
            "tellerNo": "3103100",
            "companyType": "91",
            "count": 3,
        },
    )
    records = job.result["records"]
    assert len(records) == 3
    assert len({record["certificateNo"] for record in records}) == 3
    assert all(record["companyName"].endswith("公司") for record in records)
    assert all(validate_social_credit_code(record["companyCreditCode"]) for record in records)


@pytest.mark.django_db
def test_card_search_and_action_use_dedicated_jobs(
    client,
    django_capture_on_commit_callbacks,
) -> None:
    search = _run_job(
        client,
        django_capture_on_commit_callbacks,
        "/api/product-data/tools/cards/search",
        key="card-search",
        body={"environment": "环境1", "customerNo": "C000000000123"},
    )
    card = search.result["cards"][0]
    action = _run_job(
        client,
        django_capture_on_commit_callbacks,
        f"/api/product-data/tools/cards/{card['cardNo']}/actions/deposit",
        key="card-deposit",
        body={
            "environment": card["environment"],
            "customerNo": card["customerNo"],
            "certificateNo": card["certificateNo"],
            "cardNo": card["cardNo"],
            "tellerNo": "310310",
            "amount": 500,
        },
    )
    assert action.kind == "card_status.action"
    assert action.result["actionResult"]["card"]["balance"] == 10_500


@pytest.mark.django_db
def test_loan_search_and_action_use_dedicated_jobs(
    client,
    django_capture_on_commit_callbacks,
) -> None:
    search = _run_job(
        client,
        django_capture_on_commit_callbacks,
        "/api/product-data/tools/loans/search",
        key="loan-search",
        body={"environment": "环境1", "customerNo": "C000000000456"},
    )
    card = search.result["cards"][0]
    loan = card["loans"][0]
    action = _run_job(
        client,
        django_capture_on_commit_callbacks,
        f"/api/product-data/tools/loans/{loan['contractNo']}/actions/freeze",
        key="loan-freeze",
        body={
            "environment": card["environment"],
            "customerNo": card["customerNo"],
            "certificateNo": card["certificateNo"],
            "cardNo": card["cardNo"],
            "contractNo": loan["contractNo"],
            "tellerNo": "310310",
            "quotaNo": loan["quotaNo"],
        },
    )
    result = action.result["actionResult"]
    assert action.kind == "loan_status.action"
    assert result["card"]["loans"][0]["freezeStatus"] == "是"
