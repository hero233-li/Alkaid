import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.integrations.cjdk_jyrc.application_link_contract import (
    ApplicationLinkCategory,
    FrozenApplicationLinkRoute,
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
    valueType: Literal["string", "boolean", "integer", "decimal", "enum"] = "string"
    nullable: bool = False
    minLength: int | None = Field(default=None, ge=0)
    maxLength: int | None = Field(default=None, ge=0)
    pattern: str | None = None
    strip: bool = True
    minimum: int | float | None = None
    maximum: int | float | None = None
    allowedValues: tuple[str | int | bool, ...] = ()

    @model_validator(mode="after")
    def validate_constraints(self) -> "CatalogField":
        import re

        if (
            self.minLength is not None
            and self.maxLength is not None
            and self.minLength > self.maxLength
        ):
            raise ValueError(f"字段 {self.name} minLength 不能大于 maxLength")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError(f"字段 {self.name} minimum 不能大于 maximum")
        if self.pattern:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"字段 {self.name} pattern 无效：{exc}") from exc
        if self.valueType == "enum" and not self.allowedValues:
            raise ValueError(f"枚举字段 {self.name} 必须配置 allowedValues")
        return self

    def enabled_for(self, method_code: str) -> bool:
        return ALL_METHODS in self.enabledFor or method_code in self.enabledFor

    def required_for(self, method_code: str) -> bool:
        return ALL_METHODS in self.requiredFor or method_code in self.requiredFor

    def as_ui_field(self) -> ProductField:
        """Return product-neutral control metadata.

        Requiredness belongs to ProductDefinition.requiredFields and the frozen
        ProductExecutionSnapshot, never to the shared field descriptor.
        """
        content = self.model_dump(
            exclude={
                "group", "enabledFor", "requiredFor", "expose", "execution",
                "valueType", "nullable", "minLength", "maxLength", "pattern",
                "strip", "minimum", "maximum", "allowedValues",
            }
        )
        content["required"] = False
        return ProductField.model_validate(content)


class CatalogApplicationMethod(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)


class ApplicationLinkRoute(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    route_id: str = Field(alias="routeId", min_length=1, max_length=255)
    environment: str = Field(min_length=1, max_length=128)
    application_methods: tuple[str, ...] = Field(
        alias="applicationMethods",
        min_length=1,
    )
    category_code: ApplicationLinkCategory = Field(alias="categoryCode")
    integration_profile_id: str = Field(
        alias="integrationProfileId",
        min_length=1,
        max_length=255,
    )
    integration_profile_version: int = Field(alias="integrationProfileVersion", ge=1)
    required_fields: tuple[str, ...] = Field(default_factory=tuple, alias="requiredFields")
    request_template: dict[str, Any] = Field(alias="requestTemplate")
    payload_bindings: dict[str, str] = Field(default_factory=dict, alias="payloadBindings")

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "ApplicationLinkRoute":
        normalized_environment = self.environment.strip().upper()
        if not normalized_environment:
            raise ValueError("申请链接环境不能为空")
        normalized_methods = tuple(method.strip() for method in self.application_methods)
        if any(not method for method in normalized_methods):
            raise ValueError("申请链接申请方式不能为空")
        if len(normalized_methods) != len(set(normalized_methods)):
            raise ValueError("申请链接申请方式不能重复")
        object.__setattr__(self, "environment", normalized_environment)
        object.__setattr__(self, "application_methods", normalized_methods)
        return self


class CatalogFeatures(BaseModel):
    """Strongly typed product feature configuration used by execution."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    product_application: bool = Field(default=True, alias="productApplication")
    application_links: tuple[ApplicationLinkRoute, ...] = Field(
        default_factory=tuple,
        alias="applicationLinks",
    )


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

        for route in self.features.application_links:
            if route.environment not in self.environments:
                raise ValueError(f"申请链接路由 {route.route_id} 引用了产品未支持的环境")
            unknown_route_methods = set(route.application_methods) - known_methods - {ALL_METHODS}
            if unknown_route_methods:
                raise ValueError(f"申请链接路由 {route.route_id} 引用了未知申请方式")
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
    """Complete non-secret execution data frozen into a Job for stable retries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog_version: int = Field(ge=1)
    catalog_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    product_code: str
    product_name: str
    product_type: str
    method_code: str
    method_name: str
    environment: str
    switch_field: str
    fields: tuple[str, ...]
    required_fields: tuple[str, ...]
    normalized_payload: dict[str, Any]
    application_link_route: FrozenApplicationLinkRoute


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
        method_code: str,
        *,
        environment: str,
        normalized_payload: dict[str, Any],
        application_link_route: FrozenApplicationLinkRoute,
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
            environment=environment,
            switch_field=product.switchField,
            fields=tuple(field.name for field in enabled_fields),
            required_fields=tuple(
                field.name for field in enabled_fields if field.required_for(method.code)
            ),
            normalized_payload=normalized_payload,
            application_link_route=application_link_route,
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
                ui_field = field.as_ui_field()
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
        checksum = _checksum({"reference": reference_raw, "products": product_raw})
        catalog = ProductCatalog(reference=reference, products=products, checksum=checksum)
        from apps.product_data.application_link_plan import (
            validate_catalog_application_link_plans,
        )

        validate_catalog_application_link_plans(catalog)
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
