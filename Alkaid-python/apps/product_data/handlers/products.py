from apps.integrations.mock_product.api import PRODUCT_CHECKS
from apps.product_data.handler_codes import (
    CREDIT_APPLICATION_V1,
    RED_SHIELD_APPLICATION_V1,
    WHITELIST_APPLICATION_V1,
)
from apps.product_data.handlers.base import BaseProductApplicationHandler


class WhitelistApplicationHandler(BaseProductApplicationHandler):
    code = WHITELIST_APPLICATION_V1
    product_type = "whitelist_product"
    switch_name = "whitelistEnabled"
    check_endpoint = PRODUCT_CHECKS["product-a"]


class RedShieldApplicationHandler(BaseProductApplicationHandler):
    code = RED_SHIELD_APPLICATION_V1
    product_type = "red_shield_product"
    switch_name = "redShieldEnabled"
    check_endpoint = PRODUCT_CHECKS["product-b"]


class CreditApplicationHandler(BaseProductApplicationHandler):
    code = CREDIT_APPLICATION_V1
    product_type = "credit_product"
    switch_name = "creditEnabled"
    check_endpoint = PRODUCT_CHECKS["product-c"]
