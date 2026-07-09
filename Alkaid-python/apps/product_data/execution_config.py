import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.product_data.handler_codes import SUPPORTED_PRODUCT_HANDLERS

CONFIG_ROOT = Path(__file__).with_name("configs") / "execution"
SOURCE_ROOT = CONFIG_ROOT / "source"
COMPILED_PATH = CONFIG_ROOT / "compiled" / "product_catalog.json"
SUPPORTED_NORMALIZERS = {"identity", "strip", "boolean"}
LEGACY_HANDLERS = {
    "product-a": "whitelist_application_v1",
    "product-b": "red_shield_application_v1",
    "product-c": "credit_application_v1",
}


class ExecutionConfigurationError(ValueError):
    pass


class ExecutionField(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(min_length=1)
    required: bool = False
    normalizer: str = "identity"


class ConfigOption(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)


class ApplicationMethodSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=255)
    fields: tuple[str, ...] = ()
    field_sets: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()


class ProductExecutionSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    product_type: str = Field(min_length=1, max_length=128)
    handler: str = Field(min_length=1, max_length=128)
    switch_field: str = Field(min_length=1, max_length=128)
    default_application_method: str = Field(min_length=1, max_length=128)
    ownership_categories: tuple[ConfigOption, ...] = Field(min_length=1)
    organizations: tuple[ConfigOption, ...] = Field(min_length=1)
    common_field_sets: tuple[str, ...] = ()
    application_methods: dict[str, ApplicationMethodSource] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_default_method(self) -> "ProductExecutionSource":
        if self.default_application_method not in self.application_methods:
            raise ValueError("默认申请方式不存在")
        return self


class ManifestSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = Field(ge=1)
    products: tuple[str, ...] = Field(min_length=1)


class FieldsSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fields: dict[str, ExecutionField] = Field(min_length=1)


class FieldSetsSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    field_sets: dict[str, tuple[str, ...]] = Field(min_length=1)


class ProductFileSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    product: ProductExecutionSource


class ResolvedApplicationMethod(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    operation: str
    fields: tuple[str, ...]
    required_fields: tuple[str, ...]


class ResolvedProductExecution(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    name: str
    product_type: str
    handler: str
    switch_field: str
    default_application_method: str
    ownership_categories: tuple[ConfigOption, ...]
    organizations: tuple[ConfigOption, ...]
    application_methods: dict[str, ResolvedApplicationMethod]


class ProductExecutionCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: int = Field(ge=1)
    checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    fields: dict[str, ExecutionField]
    products: dict[str, ResolvedProductExecution]

    def snapshot(
        self,
        product_code: str,
        method_code: str | None = None,
    ) -> "ProductExecutionSnapshot":
        try:
            product = self.products[product_code]
        except KeyError:
            raise ExecutionConfigurationError(f"后端执行配置不存在产品：{product_code}") from None
        selected_method = method_code or product.default_application_method
        try:
            method = product.application_methods[selected_method]
        except KeyError:
            raise ExecutionConfigurationError(
                f"产品 {product_code} 不支持申请方式：{selected_method}"
            ) from None
        return ProductExecutionSnapshot(
            catalog_version=self.version,
            catalog_checksum=self.checksum,
            product_code=product.code,
            product_name=product.name,
            product_type=product.product_type,
            handler=product.handler,
            method_code=selected_method,
            method_name=method.name,
            operation=method.operation,
            switch_field=product.switch_field,
            switch_payload_field=self.fields[product.switch_field].source.rsplit(".", 1)[-1],
            fields=method.fields,
            required_fields=method.required_fields,
            field_definitions={name: self.fields[name] for name in method.fields},
        )


class ProductExecutionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    catalog_version: int
    catalog_checksum: str
    product_code: str
    product_name: str
    product_type: str
    handler: str
    method_code: str
    method_name: str
    operation: str
    switch_field: str
    switch_payload_field: str
    fields: tuple[str, ...]
    required_fields: tuple[str, ...]
    field_definitions: dict[str, ExecutionField]

    @model_validator(mode="before")
    @classmethod
    def upgrade_legacy_snapshot(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        definitions = data.get("field_definitions")
        if isinstance(definitions, dict):
            legacy_required: list[str] = []
            upgraded: dict[str, Any] = {}
            for name, raw_field in definitions.items():
                if not isinstance(raw_field, dict):
                    upgraded[name] = raw_field
                    continue
                if raw_field.get("required"):
                    legacy_required.append(name)
                upgraded[name] = {
                    "source": raw_field.get("source"),
                    "required": raw_field.get("required", False),
                    "normalizer": raw_field.get(
                        "normalizer",
                        raw_field.get("transformer", "identity"),
                    ),
                }
            data["field_definitions"] = upgraded
            data.setdefault("required_fields", legacy_required)
        product_code = str(data.get("product_code") or "")
        data.setdefault("required_fields", [])
        data.setdefault("product_type", "legacy")
        data.setdefault("handler", LEGACY_HANDLERS.get(product_code, ""))
        return data


def compile_execution_catalog(source_root: Path = SOURCE_ROOT) -> ProductExecutionCatalog:
    manifest = ManifestSource.model_validate(_load_source(source_root / "manifest.json"))
    fields = FieldsSource.model_validate(_load_source(source_root / "fields.json")).fields
    field_sets = FieldSetsSource.model_validate(
        _load_source(source_root / "field_sets.json")
    ).field_sets
    _validate_fields(fields)
    _validate_field_sets(field_sets, fields)

    products: dict[str, ResolvedProductExecution] = {}
    for relative_path in manifest.products:
        source = ProductFileSource.model_validate(_load_source(source_root / relative_path)).product
        if source.code in products:
            raise ExecutionConfigurationError(f"产品执行配置重复：{source.code}")
        products[source.code] = _resolve_product(source, fields, field_sets)

    content = {
        "version": manifest.version,
        "fields": {name: field.model_dump(mode="json") for name, field in fields.items()},
        "products": {name: product.model_dump(mode="json") for name, product in products.items()},
    }
    return ProductExecutionCatalog(**content, checksum=_checksum(content))


def load_execution_catalog(path: Path = COMPILED_PATH) -> ProductExecutionCatalog:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        catalog = ProductExecutionCatalog.model_validate(raw)
    except (OSError, ValueError) as exc:
        raise ExecutionConfigurationError(f"后端产品执行配置无效：{exc}") from exc
    content = {key: value for key, value in raw.items() if key != "checksum"}
    if catalog.checksum != _checksum(content):
        raise ExecutionConfigurationError("后端产品执行配置 checksum 不一致，请重新编译")
    return catalog


def render_compiled_catalog(catalog: ProductExecutionCatalog) -> str:
    return json.dumps(catalog.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"


def _load_source(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExecutionConfigurationError(f"读取执行配置失败 {path}: {exc}") from exc


def _validate_fields(fields: dict[str, ExecutionField]) -> None:
    for name, field in fields.items():
        if field.normalizer not in SUPPORTED_NORMALIZERS:
            raise ExecutionConfigurationError(
                f"字段 {name} 使用了未注册的 normalizer：{field.normalizer}"
            )


def _validate_field_sets(
    field_sets: dict[str, tuple[str, ...]],
    fields: dict[str, ExecutionField],
) -> None:
    for set_name, field_names in field_sets.items():
        unknown = set(field_names) - fields.keys()
        if unknown:
            raise ExecutionConfigurationError(
                f"字段组 {set_name} 引用了未知字段：{', '.join(sorted(unknown))}"
            )


def _resolve_product(
    source: ProductExecutionSource,
    fields: dict[str, ExecutionField],
    field_sets: dict[str, tuple[str, ...]],
) -> ResolvedProductExecution:
    if source.handler not in SUPPORTED_PRODUCT_HANDLERS:
        raise ExecutionConfigurationError(
            f"产品 {source.code} 引用了未注册处理器：{source.handler}"
        )
    if source.switch_field not in fields:
        raise ExecutionConfigurationError(
            f"产品 {source.code} 引用了未知 Switch 字段：{source.switch_field}"
        )
    common_fields = _expand_field_sets(source.common_field_sets, field_sets, source.code)
    methods: dict[str, ResolvedApplicationMethod] = {}
    for code, method in source.application_methods.items():
        method_fields = _expand_field_sets(method.field_sets, field_sets, source.code)
        resolved_fields = _unique((*common_fields, *method_fields, *method.fields))
        unknown = set(resolved_fields) - fields.keys()
        if unknown:
            raise ExecutionConfigurationError(
                f"产品 {source.code} 的申请方式 {code} 引用了未知字段："
                f"{', '.join(sorted(unknown))}"
            )
        unavailable_required = set(method.required_fields) - set(resolved_fields)
        if unavailable_required:
            raise ExecutionConfigurationError(
                f"产品 {source.code} 的申请方式 {code} 未启用必填字段："
                f"{', '.join(sorted(unavailable_required))}"
            )
        required_fields = _unique(
            tuple(name for name in resolved_fields if fields[name].required)
            + method.required_fields
        )
        methods[code] = ResolvedApplicationMethod(
            name=method.name,
            operation=method.operation,
            fields=resolved_fields,
            required_fields=required_fields,
        )
    return ResolvedProductExecution(
        code=source.code,
        name=source.name,
        product_type=source.product_type,
        handler=source.handler,
        switch_field=source.switch_field,
        default_application_method=source.default_application_method,
        ownership_categories=source.ownership_categories,
        organizations=source.organizations,
        application_methods=methods,
    )


def _expand_field_sets(
    names: tuple[str, ...],
    field_sets: dict[str, tuple[str, ...]],
    product_code: str,
) -> tuple[str, ...]:
    result: list[str] = []
    for name in names:
        try:
            result.extend(field_sets[name])
        except KeyError:
            raise ExecutionConfigurationError(
                f"产品 {product_code} 引用了未知字段组：{name}"
            ) from None
    return tuple(result)


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _checksum(content: dict[str, Any]) -> str:
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
