import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from django.db import close_old_connections

from apps.integrations.card_status.mock_store import CARD_MOCK_STORE, CardMockStore
from apps.integrations.loan_status.mock_store import LOAN_MOCK_STORE, LoanMockStore
from apps.jobs.models import Job, JobStatus, MockToolState
from apps.mock_data.application_generator import (
    generate_application_record,
    validate_social_credit_code,
)


@pytest.fixture(autouse=True)
def reset_mock_tools(db) -> None:
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


def test_generated_mock_fields_are_unique_for_maximum_request_size() -> None:
    names: set[str] = set()
    certificates: set[str] = set()
    cards: set[str] = set()
    phones: set[str] = set()
    companies: set[str] = set()
    credit_codes: set[str] = set()

    for sequence in range(1_000):
        record = generate_application_record(
            sequence,
            environment="UAT1",
            birth_date=date(1986, 7, 14),
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

    assert len(names) == 1_000
    assert len(certificates) == 1_000
    assert len(cards) == 1_000
    assert len(phones) == 1_000
    assert len(companies) == 1_000
    assert len(credit_codes) == 1_000


@pytest.mark.parametrize(
    ("company_type", "name_suffix"),
    [("91", "公司"), ("92", "个体"), ("51", "社会团体")],
)
def test_generated_company_data_matches_selected_subject_type(
    company_type: str,
    name_suffix: str,
) -> None:
    record = generate_application_record(
        1,
        environment="UAT1",
        birth_date=date(1986, 7, 14),
        gender="男",
        company_type=company_type,
    )

    assert record.company_name.endswith(name_suffix)
    assert record.company_credit_code.startswith(company_type)
    assert validate_social_credit_code(record.company_credit_code)


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
            "environment": "UAT1",
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
    assert all(record["tellerNo"] == "3103100" for record in records)
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
        body={"environment": "UAT1", "customerNo": "C000000000123"},
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
    assert action.kind == "card_status"
    assert action.payload["operation"] == "action"
    assert action.result["actionResult"]["card"]["balance"] == 10_500


@pytest.mark.django_db
def test_card_transfer_moves_balance_between_existing_cards(
    client,
    django_capture_on_commit_callbacks,
) -> None:
    source_job = _run_job(
        client,
        django_capture_on_commit_callbacks,
        "/api/product-data/tools/cards/search",
        key="card-transfer-source",
        body={"environment": "UAT1", "customerNo": "C000000000123"},
    )
    target_job = _run_job(
        client,
        django_capture_on_commit_callbacks,
        "/api/product-data/tools/cards/search",
        key="card-transfer-target",
        body={"environment": "UAT1", "customerNo": "C000000000124"},
    )
    source = source_job.result["cards"][0]
    target = target_job.result["cards"][0]

    transfer = _run_job(
        client,
        django_capture_on_commit_callbacks,
        f"/api/product-data/tools/cards/{source['cardNo']}/actions/transfer",
        key="card-transfer",
        body={
            "environment": source["environment"],
            "customerNo": source["customerNo"],
            "cardNo": source["cardNo"],
            "tellerNo": "310310",
            "amount": 500,
            "targetCard": target["cardNo"],
        },
    )

    assert transfer.result["actionResult"]["card"]["balance"] == 9_500
    assert CARD_MOCK_STORE.search(target["environment"], target["customerNo"])[0].balance == 10_500


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("target", "amount", "message"),
    [
        ("same", 100, "源卡与目标卡不能相同"),
        ("missing", 100, "目标卡不存在"),
        ("existing", 20_000, "卡余额不足"),
    ],
)
def test_card_transfer_rejects_invalid_target_or_balance(target, amount, message) -> None:
    source = CARD_MOCK_STORE.search("UAT1", "C000000000123")[0]
    existing = CARD_MOCK_STORE.search("UAT1", "C000000000124")[0]
    target_card = {
        "same": source.card_no,
        "missing": "6222029999999999",
        "existing": existing.card_no,
    }[target]

    with pytest.raises(ValueError, match=message):
        CARD_MOCK_STORE.apply_action(
            source.card_no,
            "transfer",
            environment=source.environment,
            customer_no=source.customer_no,
            amount=amount,
            target_card=target_card,
        )


@pytest.mark.django_db
def test_application_data_rejects_unsafe_count_and_result_size(
    client,
    django_capture_on_commit_callbacks,
    settings,
) -> None:
    body = {
        "environment": "UAT1",
        "currentDate": "2026-07-14",
        "birthDate": "1986-07-14",
        "age": 40,
        "gender": "男",
        "tellerNo": "3103100",
        "companyType": "91",
        "count": 1_001,
    }
    rejected = client.post(
        "/api/product-data/tools/application-data/generate",
        data=json.dumps(body),
        content_type="application/json",
    )
    assert rejected.status_code == 400

    settings.APPLICATION_DATA_MAX_RESULT_BYTES = 10
    body["count"] = 1
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            "/api/product-data/tools/application-data/generate",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_X_IDEMPOTENCY_KEY="application-data-size-limit",
        )
    job = Job.objects.get(id=response.json()["data"]["id"])
    assert job.status == JobStatus.FAILED
    assert "安全大小限制" in job.error_message


@pytest.mark.django_db
def test_application_data_uses_birth_date_in_certificate_and_validates_age(
    client,
    django_capture_on_commit_callbacks,
) -> None:
    body = {
        "environment": "UAT1",
        "currentDate": "2026-07-15",
        "birthDate": "1986-07-14",
        "age": 40,
        "gender": "男",
        "tellerNo": "3103100",
        "companyType": "91",
        "count": 1,
    }
    job = _run_job(
        client,
        django_capture_on_commit_callbacks,
        "/api/product-data/tools/application-data/generate",
        key="application-data-birth-date",
        body=body,
    )
    assert job.result["records"][0]["certificateNo"][6:14] == "19860714"

    body["age"] = 39
    response = client.post(
        "/api/product-data/tools/application-data/generate",
        data=json.dumps(body),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "出生日期与年龄不一致" in response.json()["message"]


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
        body={"environment": "UAT1", "customerNo": "C000000000456"},
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
    assert action.kind == "loan_status"
    assert action.payload["operation"] == "action"
    assert result["card"]["loans"][0]["freezeStatus"] == "是"


@pytest.mark.django_db
def test_mock_state_is_shared_across_store_instances() -> None:
    card = CARD_MOCK_STORE.search("UAT1", "C000000000777")[0]
    CardMockStore().apply_action(
        card.card_no,
        "deposit",
        environment=card.environment,
        customer_no=card.customer_no,
        amount=250,
    )
    assert CardMockStore().search("UAT1", "C000000000777")[0].balance == 10_250

    loan_card = LOAN_MOCK_STORE.search("UAT1", "C000000000778")[0]
    contract_no = loan_card["loans"][0]["contractNo"]
    LoanMockStore().apply_action("UAT1", "C000000000778", contract_no, "freeze", {})
    assert LoanMockStore().search("UAT1", "C000000000778")[0]["loans"][0]["freezeStatus"] == "是"


@pytest.mark.django_db
def test_mock_state_is_isolated_by_environment_and_validates_owner() -> None:
    env1 = CARD_MOCK_STORE.search("UAT1", "C000000000901")[0]
    env2 = CARD_MOCK_STORE.search("UAT2", "C000000000901")[0]
    CARD_MOCK_STORE.apply_action(
        env1.card_no,
        "deposit",
        environment="UAT1",
        customer_no=env1.customer_no,
        amount=100,
    )
    assert CARD_MOCK_STORE.search("UAT1", env1.customer_no)[0].balance == 10_100
    assert CARD_MOCK_STORE.search("UAT2", env2.customer_no)[0].balance == 10_000
    with pytest.raises(ValueError, match="不存在"):
        CARD_MOCK_STORE.apply_action(
            env1.card_no,
            "deposit",
            environment="UATC",
            customer_no=env1.customer_no,
            amount=100,
        )

    loan1 = LOAN_MOCK_STORE.search("UAT1", "C000000000902")[0]
    loan2 = LOAN_MOCK_STORE.search("UAT2", "C000000000902")[0]
    contract_no = loan1["loans"][0]["contractNo"]
    LOAN_MOCK_STORE.apply_action("UAT1", loan1["customerNo"], contract_no, "freeze", {})
    assert (
        LOAN_MOCK_STORE.search("UAT1", loan1["customerNo"])[0]["loans"][0]["freezeStatus"] == "是"
    )
    assert (
        LOAN_MOCK_STORE.search("UAT2", loan2["customerNo"])[0]["loans"][0]["freezeStatus"] == "否"
    )


@pytest.mark.django_db(transaction=True)
def test_concurrent_first_search_converges_on_one_mock_state() -> None:
    def search() -> str:
        close_old_connections()
        try:
            return CardMockStore().search("UAT1", "C000000000903")[0].card_no
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        cards = list(executor.map(lambda _: search(), range(2)))

    assert cards[0] == cards[1]
    assert (
        MockToolState.objects.filter(namespace="card_status", key=f"UAT1:{cards[0]}").count() == 1
    )
