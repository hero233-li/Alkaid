from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductOption(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=128)


class ProductBranch(ProductOption):
    outlets: tuple[ProductOption, ...]


class ProductLocation(ProductOption):
    branches: tuple[ProductBranch, ...]


class ProductDefinition(ProductOption):
    environments: tuple[str, ...]
    locations: tuple[ProductLocation, ...]
    fieldSets: tuple[str, ...] = Field(min_length=1)
    requiredFields: tuple[str, ...] = ()


class ProductField(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    label: str | None = None
    control: Literal["input", "select", "switch"] = "input"
    span: int = Field(default=8, ge=1, le=24)
    required: bool = False
    editable: bool = True
    submit: bool = True
    searchable: bool = False
    placeholder: str | None = None
    defaultValue: str | bool | None = None
    options: tuple[ProductOption, ...] | None = None
    checkedLabel: str | None = None
    uncheckedLabel: str | None = None
    switchWidth: int | None = Field(default=None, ge=1, le=500)
    persistDraft: bool = False


class ProductApplicationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    version: int = Field(ge=1)
    environments: tuple[ProductOption, ...] = Field(min_length=1)
    products: tuple[ProductDefinition, ...] = Field(min_length=1)
    fieldSets: dict[str, tuple[str, ...]] = Field(min_length=1)
    fields: tuple[ProductField, ...] = Field(min_length=1)
    cascadeResetMap: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    def field_names_for(self, product: ProductDefinition) -> set[str]:
        return {
            field_name
            for field_set_name in product.fieldSets
            for field_name in self.fieldSets[field_set_name]
        }

    @model_validator(mode="after")
    def validate_references(self) -> "ProductApplicationConfig":
        environment_values = {item.value for item in self.environments}
        product_values = [item.value for item in self.products]
        if len(product_values) != len(set(product_values)):
            raise ValueError("产品配置值不能重复")
        field_names = [item.name for item in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("字段配置名称不能重复")
        known_fields = set(field_names)
        for field_set_name, configured_fields in self.fieldSets.items():
            if not configured_fields:
                raise ValueError(f"字段组 {field_set_name} 不能为空")
            unknown_fields = set(configured_fields) - known_fields
            if unknown_fields:
                raise ValueError(
                    f"字段组 {field_set_name} 引用了未知字段："
                    f"{', '.join(sorted(unknown_fields))}"
                )
        for product in self.products:
            unknown_environments = set(product.environments) - environment_values
            if unknown_environments:
                raise ValueError(f"产品 {product.value} 引用了未知环境")
            unknown_field_sets = set(product.fieldSets) - self.fieldSets.keys()
            if unknown_field_sets:
                raise ValueError(
                    f"产品 {product.value} 引用了未知字段组："
                    f"{', '.join(sorted(unknown_field_sets))}"
                )
            active_fields = self.field_names_for(product)
            unavailable_required_fields = set(product.requiredFields) - active_fields
            if unavailable_required_fields:
                raise ValueError(
                    f"产品 {product.value} 的必填字段未包含在字段组中："
                    f"{', '.join(sorted(unavailable_required_fields))}"
                )
        for source, targets in self.cascadeResetMap.items():
            if source not in known_fields or set(targets) - known_fields:
                raise ValueError("级联重置配置引用了未知字段")
        return self


class ProductApplicationSubmission(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    product: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any]


class CustomerType(str, Enum):
    FARMER = "farmer"
    LEGAL_PERSON = "legal_person"
    SHAREHOLDER = "shareholder"
