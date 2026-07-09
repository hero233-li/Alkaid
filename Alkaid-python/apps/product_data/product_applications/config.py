import json
from pathlib import Path

from apps.product_data.product_applications.schemas import ProductApplicationConfig

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "product_application.json"


class ProductConfigurationError(ValueError):
    pass


def load_product_application_config() -> ProductApplicationConfig:
    """Load the UI contract on every request so config deployment needs no restart."""
    try:
        content = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return ProductApplicationConfig.model_validate(content)
    except (OSError, ValueError) as exc:
        raise ProductConfigurationError(f"产品申请配置无效：{exc}") from exc
