from apps.product_data.application_links.handlers.base import BaseApplicationLinkHandler
from apps.product_data.application_links.schemas import LinkCategory


class ProductADynamicLinkHandler(BaseApplicationLinkHandler):
    code = "product_a_dynamic_link_v1"
    category = LinkCategory.DYNAMIC_LINK


class ProductASunCodeHandler(BaseApplicationLinkHandler):
    code = "product_a_sun_code_v1"
    category = LinkCategory.SUN_CODE


class ProductBSunCodeHandler(BaseApplicationLinkHandler):
    code = "product_b_sun_code_v1"
    category = LinkCategory.SUN_CODE


class ProductCDynamicLinkHandler(BaseApplicationLinkHandler):
    code = "product_c_dynamic_link_v1"
    category = LinkCategory.DYNAMIC_LINK
