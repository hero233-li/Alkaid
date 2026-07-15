import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.product_data.application_links.schemas import (
    ApplicationLinkSubmission,
    LinkCategory,
)
from apps.product_data.product_applications.schemas import (
    ProductApplicationConfig,
    ProductDefinition,
    ProductField,
    ProductLocation,
    ProductOption,
)

CONFIG_ROOT = Path(__file__).with_name("configs")
PRODUCT_ROOT = CONFIG_ROOT / "products"
REFERENCE_PATH = CONFIG_ROOT / "reference_data.json"
ALL_METHODS = "*"


class ProductCatalogError(ValueError):
    pass


class CatalogField(ProductField):
    """One product-local field definition used by both UI and execution validation."""

    group: str | None = Field(default=None, min_length=1, max_length=128)
    enabledFor: tuple[str, ...] = (ALL_METHODS,)
    requiredFor: tuple[str, ...] = ()
    expose: bool = True
    execution: bool = True

    def enabled_for(self, method_code: str) -> bool:
        return ALL_METHODS in self.enabledFor or method_code in self.enabledFor

    def required_for(self, method_code: str) -> bool:
        return ALL_METHODS in self.requiredFor or method_code in self.requiredFor

    def as_ui_field(self, method_code: str) -> ProductField:
        content = self.model_dump(
            exclude={"group", "enabledFor", "requiredFor", "expose", "execution"}
        )
        content["required"] = self.required_for(method_code)
        return ProductField.model_validate(content)


class CatalogApplicationMethod(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)


class CatalogApplicationLinkRoute(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    environment: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=32)
    requiredFields: tuple[str, ...] = ()


class CatalogFeatures(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    applicationLinks: tuple[CatalogApplicationLinkRoute, ...] = ()


class ProductCatalogSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    productType: str = Field(min_length=1, max_length=128)
    switchField: str = Field(min_length=1, max_length=128)
    defaultApplicationMethod: str = Field(min_length=1, max_length=128)
    environments: tuple[str, ...] = Field(min_length=1)
    locations: tuple[ProductLocation, ...] = Field(min_length=1)
    applicationMethods: tuple[CatalogApplicationMethod, ...] = Field(min_length=1)
    fields: tuple[CatalogField, ...] = Field(min_length=1)
    features: CatalogFeatures = Field(default_factory=CatalogFeatures)

    @model_validator(mode="after")
    def validate_local_references(self) -> "ProductCatalogSource":
        method_codes = [method.code for method in self.applicationMethods]
        if len(method_codes) != len(set(method_codes)):
            raise ValueError("申请方式代码不能重复")
        if self.defaultApplicationMethod not in method_codes:
            raise ValueError("默认申请方式不存在")

        field_names = [field.name for field in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("产品字段名称不能重复")
        if self.switchField not in field_names:
            raise ValueError("产品开关字段不存在")

        known_methods = set(method_codes)
        for field in self.fields:
            if field.required:
                raise ValueError(f"字段 {field.name} 请使用 requiredFor，不能同时维护 required")
            unknown_enabled = set(field.enabledFor) - known_methods - {ALL_METHODS}
            unknown_required = set(field.requiredFor) - known_methods - {ALL_METHODS}
            if unknown_enabled or unknown_required:
                raise ValueError(f"字段 {field.name} 引用了未知申请方式")
            for required_method in field.requiredFor:
                if required_method == ALL_METHODS:
                    if ALL_METHODS not in field.enabledFor:
                        raise ValueError(f"字段 {field.name} 必填但并非所有申请方式启用")
                elif (
                    ALL_METHODS not in field.enabledFor and required_method not in field.enabledFor
                ):
                    raise ValueError(f"字段 {field.name} 在未启用的申请方式中被设为必填")
            if field.expose and not field.group:
                raise ValueError(f"页面字段 {field.name} 缺少 group")

        route_keys: list[tuple[str, str]] = []
        known_link_fields = set(ApplicationLinkSubmission.model_fields)
        known_categories = {category.value for category in LinkCategory}
        for route in self.features.applicationLinks:
            route_key = (route.environment, route.category)
            route_keys.append(route_key)
            if route.category not in known_categories:
                raise ValueError(f"申请链接类别无效：{route.category}")
            unknown_required_fields = set(route.requiredFields) - known_link_fields
            if unknown_required_fields:
                raise ValueError(
                    f"申请链接路由引用了未知字段：{', '.join(sorted(unknown_required_fields))}"
                )
        if len(route_keys) != len(set(route_keys)):
            raise ValueError("申请链接环境与类别路由不能重复")
        return self

    def method(self, method_code: str | None = None) -> CatalogApplicationMethod:
        selected = method_code or self.defaultApplicationMethod
        for method in self.applicationMethods:
            if method.code == selected:
                return method
        raise ProductCatalogError(f"产品 {self.code} 不支持申请方式：{selected}")

    def enabled_execution_fields(self, method_code: str) -> tuple[CatalogField, ...]:
        return tuple(
            field for field in self.fields if field.execution and field.enabled_for(method_code)
        )


class ProductReferenceData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    version: int = Field(ge=1)
    environments: tuple[ProductOption, ...] = Field(min_length=1)
    cooperationProjects: tuple[ProductOption, ...] = ()
    cascadeResetMap: dict[str, tuple[str, ...]] = Field(default_factory=dict)


class ProductExecutionSnapshot(BaseModel):
    """Minimal product execution data frozen into a Job for stable retries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog_version: int = Field(ge=1)
    catalog_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    product_code: str
    product_name: str
    product_type: str
    method_code: str
    method_name: str
    switch_field: str
    fields: tuple[str, ...]
    required_fields: tuple[str, ...]

    @model_validator(mode="before")
    @classmethod
    def upgrade_legacy_snapshot(cls, value: Any) -> Any:
        """Accept Jobs created before field metadata was flattened."""

        if not isinstance(value, dict):
            return value
        data = dict(value)
        definitions = data.pop("field_definitions", None)
        source_names: dict[str, str] = {}
        definition_required: list[str] = []
        if isinstance(definitions, dict):
            for name, raw_field in definitions.items():
                if not isinstance(raw_field, dict):
                    continue
                source = str(raw_field.get("source") or f"application.{name}")
                source_name = source.rsplit(".", 1)[-1]
                source_names[name] = source_name
                if raw_field.get("required"):
                    definition_required.append(source_name)

        data["fields"] = tuple(
            source_names.get(str(name), str(name)) for name in data.get("fields", ())
        )
        required = data.get("required_fields") or definition_required
        data["required_fields"] = tuple(source_names.get(str(name), str(name)) for name in required)
        data.setdefault("product_type", "legacy")
        data.setdefault("switch_field", data.get("switch_payload_field", ""))
        data.pop("handler", None)
        data.pop("operation", None)
        data.pop("switch_payload_field", None)
        return data


class ProductCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    reference: ProductReferenceData
    products: dict[str, ProductCatalogSource]
    checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def product(self, product_code_or_name: str) -> ProductCatalogSource:
        product = self.products.get(product_code_or_name)
        if product is not None:
            return product
        for candidate in self.products.values():
            if candidate.name == product_code_or_name:
                return candidate
        raise ProductCatalogError(f"未知产品：{product_code_or_name}")

    def snapshot(
        self,
        product_code: str,
        method_code: str | None = None,
    ) -> ProductExecutionSnapshot:
        """Resolve one executable Job snapshot directly from the source catalog."""

        product = self.product(product_code)
        method = product.method(method_code)
        enabled_fields = product.enabled_execution_fields(method.code)
        return ProductExecutionSnapshot(
            catalog_version=self.reference.version,
            catalog_checksum=self.checksum,
            product_code=product.code,
            product_name=product.name,
            product_type=product.productType,
            method_code=method.code,
            method_name=method.name,
            switch_field=product.switchField,
            fields=tuple(field.name for field in enabled_fields),
            required_fields=tuple(
                field.name for field in enabled_fields if field.required_for(method.code)
            ),
        )

    def to_ui_config(self) -> ProductApplicationConfig:
        ui_fields: dict[str, ProductField] = {}
        field_sets: dict[str, list[str]] = {}
        products: list[ProductDefinition] = []

        for product in self.products.values():
            product_groups: list[str] = []
            required_fields: list[str] = []
            for field in product.fields:
                if not field.expose:
                    continue
                ui_field = field.as_ui_field(product.defaultApplicationMethod)
                previous = ui_fields.get(field.name)
                if previous is not None and previous != ui_field:
                    raise ProductCatalogError(f"页面字段 {field.name} 在多个产品中的定义不一致")
                ui_fields.setdefault(field.name, ui_field)
                group = field.group or ""
                if group not in product_groups:
                    product_groups.append(group)
                group_fields = field_sets.setdefault(group, [])
                if field.name not in group_fields:
                    group_fields.append(field.name)
                if field.required_for(product.defaultApplicationMethod):
                    required_fields.append(field.name)

            products.append(
                ProductDefinition(
                    label=product.name,
                    value=product.code,
                    environments=product.environments,
                    locations=product.locations,
                    fieldSets=tuple(product_groups),
                    requiredFields=tuple(required_fields),
                )
            )

        return ProductApplicationConfig(
            id=self.reference.id,
            version=self.reference.version,
            environments=self.reference.environments,
            products=tuple(products),
            fieldSets={name: tuple(fields) for name, fields in field_sets.items()},
            fields=tuple(ui_fields.values()),
            cascadeResetMap=self.reference.cascadeResetMap,
        )


def load_product_catalog(
    product_root: Path | None = None,
    reference_path: Path | None = None,
) -> ProductCatalog:
    if product_root is None and reference_path is None:
        return _load_default_product_catalog()
    return _load_product_catalog(product_root or PRODUCT_ROOT, reference_path or REFERENCE_PATH)


@lru_cache(maxsize=1)
def _load_default_product_catalog() -> ProductCatalog:
    return _load_product_catalog(PRODUCT_ROOT, REFERENCE_PATH)


@lru_cache(maxsize=1)
def load_product_ui_config() -> ProductApplicationConfig:
    return load_product_catalog().to_ui_config()


def clear_product_catalog_cache() -> None:
    _load_default_product_catalog.cache_clear()
    load_product_ui_config.cache_clear()


def _load_product_catalog(
    product_root: Path,
    reference_path: Path,
) -> ProductCatalog:
    try:
        reference_raw = _read_json(reference_path)
        reference = ProductReferenceData.model_validate(reference_raw)
        products: dict[str, ProductCatalogSource] = {}
        product_raw: dict[str, Any] = {}
        for path in sorted(product_root.glob("*.json")):
            raw = _read_json(path)
            product = ProductCatalogSource.model_validate(raw)
            if product.code in products:
                raise ProductCatalogError(f"产品代码重复：{product.code}")
            products[product.code] = product
            product_raw[product.code] = raw
        if not products:
            raise ProductCatalogError("没有找到产品配置")
        known_environments = {option.value for option in reference.environments}
        for product in products.values():
            unknown_product_environments = set(product.environments) - known_environments
            if unknown_product_environments:
                raise ProductCatalogError(
                    f"产品 {product.code} 引用了未知环境代码："
                    f"{', '.join(sorted(unknown_product_environments))}"
                )
            unknown_link_environments = {
                route.environment for route in product.features.applicationLinks
            } - known_environments
            if unknown_link_environments:
                raise ProductCatalogError(
                    f"产品 {product.code} 的申请链接引用了未知环境代码："
                    f"{', '.join(sorted(unknown_link_environments))}"
                )
        checksum = _checksum({"reference": reference_raw, "products": product_raw})
        catalog = ProductCatalog(reference=reference, products=products, checksum=checksum)
        # Build once so cross-product UI definitions and reset references are validated too.
        catalog.to_ui_config()
        return catalog
    except ProductCatalogError:
        raise
    except (OSError, ValueError) as exc:
        raise ProductCatalogError(f"产品目录配置无效：{exc}") from exc


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _checksum(content: dict[str, Any]) -> str:
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
