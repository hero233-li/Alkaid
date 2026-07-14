from __future__ import annotations

import hashlib
from datetime import date

from django.db import transaction

from apps.integrations.card_status.models import CardActionResult, CardRecord
from apps.jobs.models import MockToolState
from apps.mock_data.application_generator import (
    birth_date_for_age,
    generate_application_record,
)

NAMESPACE = "card_status"


class CardMockStore:
    def reset(self) -> None:
        MockToolState.objects.filter(namespace=NAMESPACE).delete()

    def search(self, environment: str, customer_no: str) -> tuple[CardRecord, ...]:
        sequence = _customer_sequence(customer_no)
        generated = generate_application_record(
            sequence,
            environment=environment,
            birth_date=birth_date_for_age(date.today(), 40),
            gender="男" if sequence % 2 else "女",
            company_type="91",
        )
        with transaction.atomic():
            state = (
                MockToolState.objects.select_for_update()
                .filter(namespace=NAMESPACE, key=generated.card_no)
                .first()
            )
            if state is None:
                card = CardRecord(
                    environment=environment,
                    customer_no=customer_no,
                    certificate_no=generated.certificate_no,
                    card_no=generated.card_no,
                    balance=10_000.0,
                    status="正常",
                )
                state = MockToolState.objects.create(
                    namespace=NAMESPACE,
                    key=card.card_no,
                    payload=card.model_dump(mode="json", by_alias=True),
                )
            return (CardRecord.model_validate(state.payload),)

    def apply_action(
        self,
        card_no: str,
        action: str,
        *,
        amount: float | None,
        target_card: str | None = None,
    ) -> CardActionResult:
        keys = [card_no]
        if action == "transfer":
            if not target_card:
                raise ValueError("转账需要目标卡号")
            if target_card == card_no:
                raise ValueError("源卡与目标卡不能相同")
            keys.append(target_card)

        with transaction.atomic():
            states = {
                state.key: state
                for state in MockToolState.objects.select_for_update()
                .filter(namespace=NAMESPACE, key__in=sorted(keys))
                .order_by("key")
            }
            source_state = states.get(card_no)
            if source_state is None:
                raise ValueError("卡号不存在，请先查询客户卡片")
            source = CardRecord.model_validate(source_state.payload)
            source_balance = source.balance
            target_state = None

            if action == "deposit":
                source_balance += _positive_amount(amount)
            elif action == "withdraw":
                value = _positive_amount(amount)
                if value > source_balance:
                    raise ValueError("卡余额不足")
                source_balance -= value
            elif action == "transfer":
                value = _positive_amount(amount)
                if value > source_balance:
                    raise ValueError("卡余额不足")
                target_state = states.get(target_card or "")
                if target_state is None:
                    raise ValueError("目标卡不存在，请先查询目标客户卡片")
                target = CardRecord.model_validate(target_state.payload)
                source_balance -= value
                target = target.model_copy(update={"balance": round(target.balance + value, 2)})
                target_state.payload = target.model_dump(mode="json", by_alias=True)
                target_state.save(update_fields=["payload", "updated_at"])
            elif action not in {"card-pin-reset", "login-password-reset"}:
                raise ValueError("不支持的卡片操作")

            updated = source.model_copy(update={"balance": round(source_balance, 2)})
            source_state.payload = updated.model_dump(mode="json", by_alias=True)
            source_state.save(update_fields=["payload", "updated_at"])

            password = None
            if action in {"card-pin-reset", "login-password-reset"}:
                password = str(
                    int(hashlib.sha256(f"{card_no}:{action}".encode()).hexdigest(), 16)
                )[-6:]
            labels = {
                "deposit": "存钱",
                "withdraw": "取现",
                "transfer": "转账",
                "card-pin-reset": "卡密重置",
                "login-password-reset": "登录密码重置",
            }
            return CardActionResult(
                card=updated,
                message=f"{labels[action]}成功",
                password=password,
            )


def _customer_sequence(customer_no: str) -> int:
    value = customer_no.removeprefix("C")
    if not value.isdigit():
        raise ValueError("Mock 客户号格式应为 C + 数字")
    return int(value)


def _positive_amount(value: float | None) -> float:
    if value is None or value <= 0:
        raise ValueError("操作金额必须大于 0")
    return value


CARD_MOCK_STORE = CardMockStore()
