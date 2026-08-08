#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = ROOT / "apps"
INTEGRATIONS_ROOT = APPS_ROOT / "integrations"
PRODUCT_DATA_ROOT = APPS_ROOT / "product_data"
APPLICATION_ROOT = APPS_ROOT / "product_applications"

PUBLIC_INTEGRATION_FILES = {"__init__.py", "contracts.py", "http.py", "mock.py"}
PRODUCT_DATA_FILES = {"__init__.py", "apps.py", "catalog.py"}
BUSINESS_PREFIXES = (
    "apps.product_applications",
    "apps.product_data",
    "apps.jobs",
    "apps.workbench",
)
PRODUCT_DATA_FORBIDDEN_PREFIXES = (
    "apps.product_applications",
    "apps.integrations",
    "apps.jobs",
    "apps.workbench",
)
LEGACY_PATHS = (
    APPS_ROOT / "integrations" / "cjdk_jyrc",
    APPS_ROOT / "product_data" / "product_applications",
    PRODUCT_DATA_ROOT / "tasks.py",
    PRODUCT_DATA_ROOT / "urls.py",
    PRODUCT_DATA_ROOT / "application_link_plan.py",
)


def imports(path: Path) -> set[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add((node.module, node.lineno))
    return result


def matches(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(prefix + ".") for prefix in prefixes)


def classes(path: Path) -> list[ast.ClassDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [node for node in tree.body if isinstance(node, ast.ClassDef)]


errors: list[str] = []

integration_files = {path.name for path in INTEGRATIONS_ROOT.glob("*.py") if path.is_file()}
if integration_files != PUBLIC_INTEGRATION_FILES:
    errors.append(
        "apps/integrations Python 文件必须固定为 "
        f"{sorted(PUBLIC_INTEGRATION_FILES)}，实际为 {sorted(integration_files)}"
    )

product_data_files = {path.name for path in PRODUCT_DATA_ROOT.glob("*.py") if path.is_file()}
if product_data_files != PRODUCT_DATA_FILES:
    errors.append(
        "apps/product_data Python 文件必须固定为 "
        f"{sorted(PRODUCT_DATA_FILES)}，实际为 {sorted(product_data_files)}"
    )

for legacy_path in LEGACY_PATHS:
    has_legacy_code = (
        any(legacy_path.rglob("*.py")) if legacy_path.is_dir() else legacy_path.exists()
    )
    if has_legacy_code:
        errors.append(f"旧业务路径仍存在：{legacy_path.relative_to(ROOT)}")

for path in INTEGRATIONS_ROOT.rglob("*.py"):
    for module, line in imports(path):
        if matches(module, BUSINESS_PREFIXES):
            errors.append(f"{path.relative_to(ROOT)}:{line}: 公共基础层导入业务模块 {module}")

for path in PRODUCT_DATA_ROOT.rglob("*.py"):
    for module, line in imports(path):
        if matches(module, PRODUCT_DATA_FORBIDDEN_PREFIXES):
            errors.append(f"{path.relative_to(ROOT)}:{line}: 产品目录反向依赖功能模块 {module}")

workflow_path = APPLICATION_ROOT / "workflow.py"
for module, line in imports(workflow_path):
    if module == "apps.product_applications.cjdk" or module.startswith(
        "apps.product_applications.cjdk."
    ):
        errors.append(
            f"{workflow_path.relative_to(ROOT)}:{line}: workflow 导入 CJDK 私有实现 {module}"
        )

for path in APPS_ROOT.rglob("*.py"):
    for module, line in imports(path):
        if module == "requests" or module.startswith("requests."):
            errors.append(
                f"{path.relative_to(ROOT)}:{line}: 禁止使用未安装的 requests，请使用 httpx"
            )

application_classes = [
    (path, node) for path in APPLICATION_ROOT.rglob("*.py") for node in classes(path)
]
if len(application_classes) > 35:
    errors.append(f"product_applications 类数量不得超过 35，实际为 {len(application_classes)}")

if (APPLICATION_ROOT / "ports.py").exists():
    errors.append("单实现模式不保留 ports.py；运行期类型应放在实际使用模块")

config_classes = {node.name for node in classes(APPLICATION_ROOT / "cjdk" / "config.py")}
expected_config_classes = {
    "CjdkJyrcSettings",
    "EnvironmentSettings",
    "IdentitySettings",
    "PhotoEnvironmentSettings",
    "DcppEnvironmentSettings",
}
if config_classes != expected_config_classes:
    errors.append(
        "CJDK 配置只能保留五个领域模型；"
        f"期望 {sorted(expected_config_classes)}，实际 {sorted(config_classes)}"
    )

for path, node in application_classes:
    if node.name != "CjdkEnvelope" and node.name.endswith(("Gateway", "Result", "Envelope")):
        errors.append(f"{path.relative_to(ROOT)}:{node.lineno}: 禁止逐接口类 {node.name}")
    public_methods = [
        child
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not child.name.startswith("_")
    ]
    state_fields = [child for child in node.body if isinstance(child, ast.AnnAssign)]
    has_initializer = any(
        isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == "__init__"
        for child in node.body
    )
    if len(public_methods) == 1 and not state_fields and not has_initializer:
        errors.append(
            f"{path.relative_to(ROOT)}:{node.lineno}: 无状态单公开方法类 {node.name} 应改为函数"
        )

if errors:
    print("\n".join(errors))
    sys.exit(1)

print("Architecture checks passed")
