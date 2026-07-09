from apps.product_data.handlers.base import BaseProductApplicationHandler
from apps.product_data.handlers.products import (
    CreditApplicationHandler,
    RedShieldApplicationHandler,
    WhitelistApplicationHandler,
)

HANDLERS: dict[str, type[BaseProductApplicationHandler]] = {
    handler.code: handler
    for handler in (
        WhitelistApplicationHandler,
        RedShieldApplicationHandler,
        CreditApplicationHandler,
    )
}


def get_product_handler(code: str) -> BaseProductApplicationHandler:
    try:
        handler = HANDLERS[code]
    except KeyError:
        raise ValueError(f"未注册产品处理器：{code}") from None
    return handler()
