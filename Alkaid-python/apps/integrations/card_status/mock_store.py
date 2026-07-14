from __future__ import annotations

import hashlib
import threading
from datetime import date

from apps.integrations.application_data.generator import generate_application_record
from apps.integrations.card_status.models import CardActionResult, CardRecord


class CardMockStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cards: dict[str, CardRecord] = {}

    def reset(self) -> None:
        with self._lock:
            self._cards.clear()

    def search(self, environment: str, customer_no: str) -> tuple[CardRecord, ...]:
        sequence = _customer_sequence(customer_no)
        generated = generate_application_record(
            sequence,
            environment=environment,
            current_date=date.today(),
            age=40,
            gender="男" if sequence % 2 else "女",
            company_type="91",
        )
        with self._lock:
            card = self._cards.get(generated.card_no)
            if card is None:
                card = CardRecord(
                    environment=environment,
                    customer_no=customer_no,
                    certificate_no=generated.certificate_no,
                    card_no=generated.card_no,
                    balance=10_000.0,
                    status="正常",
                )
                self._cards[card.card_no] = card
            return (card.model_copy(deep=True),)

    def apply_action(
        self,
        card_no: str,
        action: str,
        *,
        amount: float | None,
    ) -> CardActionResult:
        with self._lock:
            card = self._cards.get(card_no)
            if card is None:
                raise ValueError("卡号不存在，请先查询客户卡片")
            balance = card.balance
            if action == "deposit":
                balance += _positive_amount(amount)
            elif action in {"withdraw", "transfer"}:
                value = _positive_amount(amount)
                if value > balance:
                    raise ValueError("卡余额不足")
                balance -= value
            elif action not in {"card-pin-reset", "login-password-reset"}:
                raise ValueError("不支持的卡片操作")
            updated = card.model_copy(update={"balance": round(balance, 2)})
            self._cards[card_no] = updated
            password = None
            if action in {"card-pin-reset", "login-password-reset"}:
                password = str(int(hashlib.sha256(f"{card_no}:{action}".encode()).hexdigest(), 16))[
                    -6:
                ]
            labels = {
                "deposit": "存钱",
                "withdraw": "取现",
                "transfer": "转账",
                "card-pin-reset": "卡密重置",
                "login-password-reset": "登录密码重置",
            }
            return CardActionResult(
                card=updated, message=f"{labels[action]}成功", password=password
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
