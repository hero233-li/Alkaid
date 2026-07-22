from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.core.errors import ConfigurationError
from apps.product_data.catalog_compat import upgrade_legacy_execution_snapshot
from apps.product_data.catalog_validation import ALL_METHODS, validate_product_source
from apps.product_data.product_applications.schemas import (
    ProductApplicationConfig,
    ProductDefinition,
    ProductField,
    ProductLocation,
    ProductOption,
)


class ProductCatalogError(ConfigurationError):
    pass


class CatalogField(ProductField):
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
    productApplication: bool = True
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
        validate_product_source(self)
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
        return upgrade_legacy_execution_snapshot(value)


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
            if not product.features.productApplication:
                continue
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
