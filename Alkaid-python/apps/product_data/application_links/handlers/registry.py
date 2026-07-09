from apps.product_data.application_links.handlers.base import BaseApplicationLinkHandler
from apps.product_data.application_links.handlers.products import (
    ProductADynamicLinkHandler,
    ProductASunCodeHandler,
    ProductBSunCodeHandler,
    ProductCDynamicLinkHandler,
)

HANDLERS: dict[str, type[BaseApplicationLinkHandler]] = {
    handler.code: handler
    for handler in (
        ProductADynamicLinkHandler,
        ProductASunCodeHandler,
        ProductBSunCodeHandler,
        ProductCDynamicLinkHandler,
    )
}


def get_application_link_handler(code: str) -> BaseApplicationLinkHandler:
    try:
        handler = HANDLERS[code]
    except KeyError:
        raise ValueError(f"申请链接处理器未注册：{code}") from None
    return handler()
