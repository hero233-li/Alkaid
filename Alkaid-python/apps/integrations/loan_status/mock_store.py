from __future__ import annotations

import copy
from datetime import date, timedelta
from typing import Any

from django.db import transaction

from apps.jobs.mock_state import get_or_create_locked_mock_state
from apps.jobs.models import MockToolState
from apps.mock_data.application_generator import (
    birth_date_for_age,
    generate_application_record,
)

NAMESPACE = "loan_status"


class LoanMockStore:
    def reset(self) -> None:
        MockToolState.objects.filter(namespace=NAMESPACE).delete()

    def search(self, environment: str, customer_no: str) -> list[dict[str, Any]]:
        sequence = _customer_sequence(customer_no)
        key = _state_key(environment, customer_no)
        card = _build_card(sequence, environment, customer_no)
        state = get_or_create_locked_mock_state(NAMESPACE, key, card)
        return [copy.deepcopy(state.payload)]

    def apply_action(
        self,
        environment: str,
        customer_no: str,
        contract_no: str,
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        with transaction.atomic():
            state, card, loan = self._find_loan(environment, customer_no, contract_no)
            amount = float(payload.get("amount") or 0)
            if action == "freeze":
                loan["freezeStatus"] = "是"
            elif action == "unfreeze":
                loan["freezeStatus"] = "否"
            elif action == "contract-sign":
                loan["status"] = "已生效"
                loan["signDate"] = date.today().isoformat()
            elif action == "loan-draw":
                if amount <= 0:
                    raise ValueError("贷款提用金额必须大于 0")
                if amount > loan["availableCredit"]:
                    raise ValueError("可用额度不足")
                loan["usedCredit"] += amount
                loan["availableCredit"] -= amount
                loan["debt"] += amount
                card["debt"] = loan["debt"]
                loan["vouchers"].append(
                    _build_voucher(contract_no, len(loan["vouchers"]) + 1, amount)
                )
            elif action in {"repayment", "overdue-repayment", "maturity-repayment"}:
                self._repay(card, loan, payload.get("voucherNo"), amount)
            else:
                raise ValueError("不支持的贷款状态操作")
            state.payload = card
            state.save(update_fields=["payload", "updated_at"])
            labels = {
                "freeze": "冻结",
                "unfreeze": "解冻",
                "contract-sign": "合同签署",
                "loan-draw": "贷款提用",
                "repayment": "还款",
                "overdue-repayment": "逾期还款",
                "maturity-repayment": "到期还款",
            }
            return {"card": copy.deepcopy(card), "message": f"{labels[action]}成功"}

    def _find_loan(
        self, environment: str, customer_no: str, contract_no: str
    ) -> tuple[MockToolState, dict[str, Any], dict[str, Any]]:
        try:
            state = MockToolState.objects.select_for_update().get(
                namespace=NAMESPACE,
                key=_state_key(environment, customer_no),
            )
        except MockToolState.DoesNotExist as exc:
            raise ValueError("贷款合同不存在，请先查询") from exc
        card = copy.deepcopy(state.payload)
        if card.get("environment") != environment or card.get("customerNo") != customer_no:
            raise ValueError("贷款所属环境或客户不匹配，请重新查询")
        for loan in card["loans"]:
            if loan["contractNo"] == contract_no:
                return state, card, loan
        raise ValueError("贷款合同不存在，请先查询")

    @staticmethod
    def _repay(
        card: dict[str, Any], loan: dict[str, Any], voucher_no: object, amount: float
    ) -> None:
        voucher = next(
            (item for item in loan["vouchers"] if item["voucherNo"] == voucher_no),
            loan["vouchers"][0] if loan["vouchers"] else None,
        )
        if voucher is None:
            raise ValueError("没有可还款的借款凭证")
        value = amount if amount > 0 else voucher["outstandingAmount"]
        value = min(value, voucher["outstandingAmount"])
        voucher["outstandingAmount"] = round(voucher["outstandingAmount"] - value, 2)
        voucher["outstandingPrincipal"] = voucher["outstandingAmount"]
        voucher["repaidPrincipal"] = round(voucher["repaidPrincipal"] + value, 2)
        if voucher["outstandingAmount"] == 0:
            voucher["status"] = "已结清"
            for item in voucher["repaymentPlan"]:
                item["status"] = "已结清"
        loan["debt"] = round(max(0, loan["debt"] - value), 2)
        loan["usedCredit"] = round(max(0, loan["usedCredit"] - value), 2)
        loan["availableCredit"] = round(loan["creditLimit"] - loan["usedCredit"], 2)
        card["debt"] = loan["debt"]


def _build_card(sequence: int, environment: str, customer_no: str) -> dict[str, Any]:
    generated = generate_application_record(
        sequence,
        environment=environment,
        birth_date=birth_date_for_age(date.today(), 40),
        gender="男" if sequence % 2 else "女",
        company_type="91",
    )
    contract_no = f"LN{sequence:016d}"
    credit_limit = 500_000.0
    used = 100_000.0
    loan = {
        "contractNo": contract_no,
        "quotaNo": f"QT{sequence:014d}",
        "signDate": (date.today() - timedelta(days=30)).isoformat(),
        "organizationNo": "310001",
        "relationshipManager": "RM001",
        "accountingDate": date.today().isoformat(),
        "graceDays": 3,
        "coreRate": 3.45,
        "generalAccountingDate": date.today().isoformat(),
        "parameterAccountingDate": date.today().isoformat(),
        "debt": used,
        "overdueDebt": 0.0,
        "creditLimit": credit_limit,
        "usedCredit": used,
        "availableCredit": credit_limit - used,
        "status": "已生效",
        "freezeStatus": "否",
        "overdueStatus": "否",
        "vouchers": [_build_voucher(contract_no, 1, used)],
    }
    return {
        "environment": environment,
        "customerNo": customer_no,
        "customerName": generated.customer_name,
        "certificateNo": generated.certificate_no,
        "phone": generated.phone,
        "cardNo": generated.card_no,
        "balance": 10_000.0,
        "status": "正常",
        "freezeStatus": "否",
        "loans": [loan],
        "linkedLoan": [contract_no],
        "debt": used,
        "overdueDebt": 0.0,
        "quotaNo": loan["quotaNo"],
    }


def _state_key(environment: str, customer_no: str) -> str:
    return f"{environment}:{customer_no}"


def _build_voucher(contract_no: str, index: int, amount: float) -> dict[str, Any]:
    repayment_date = (date.today() + timedelta(days=30)).isoformat()
    return {
        "voucherNo": f"{contract_no}-V{index:02d}",
        "drawAmount": amount,
        "outstandingAmount": amount,
        "overdueAmount": 0.0,
        "nextRepaymentDate": repayment_date,
        "dueDate": repayment_date,
        "status": "使用中",
        "repaidPrincipal": 0.0,
        "repaidInterest": 0.0,
        "outstandingPrincipal": amount,
        "outstandingInterest": 0.0,
        "repaymentPlan": [
            {
                "installmentNo": 1,
                "repaymentDate": repayment_date,
                "principal": amount,
                "interest": 0.0,
                "totalAmount": amount,
                "status": "使用中",
            }
        ],
    }


def _customer_sequence(customer_no: str) -> int:
    value = customer_no.removeprefix("C")
    if not value.isdigit():
        raise ValueError("Mock 客户号格式应为 C + 数字")
    return int(value)


LOAN_MOCK_STORE = LoanMockStore()
