#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = ROOT / "apps"
UTILS_ROOT = APPS_ROOT / "utils"
HTTP_UTILS_ROOT = UTILS_ROOT / "http"
WORKFLOW_ROOT = APPS_ROOT / "workflow"
APPLICATION_LINKS_ROOT = WORKFLOW_ROOT / "application_links"
APPLICATION_ROOT = WORKFLOW_ROOT / "product_applications"

PUBLIC_HTTP_FILES = {"__init__.py", "client.py", "config.py", "contracts.py"}
WORKFLOW_PREFIX = "apps.workflow"
LEGACY_PATHS = (
    APPS_ROOT / "application_links",
    APPS_ROOT / "documents",
    APPS_ROOT / "external_systems",
    APPS_ROOT / "integrations",
    APPS_ROOT / "jobs",
    APPS_ROOT / "portal",
    APPS_ROOT / "product_applications",
    APPS_ROOT / "product_data",
    APPS_ROOT / "workbench",
)
LEGACY_IMPORT_PREFIXES = (
    "apps.application_links",
    "apps.documents",
    "apps.Documents",
    "apps.external_systems",
    "apps.integrations",
    "apps.jobs",
    "apps.Jobs",
    "apps.portal",
    "apps.product_applications",
    "apps.product_data",
    "apps.System_menu",
    "apps.workbench",
    "apps.Apifox",
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

http_files = {path.name for path in HTTP_UTILS_ROOT.glob("*.py") if path.is_file()}
if http_files != PUBLIC_HTTP_FILES:
    errors.append(
        "apps/utils/http Python 文件必须固定为 "
        f"{sorted(PUBLIC_HTTP_FILES)}，实际为 {sorted(http_files)}"
    )

for legacy_path in LEGACY_PATHS:
    has_legacy_code = (
        any(legacy_path.rglob("*.py")) if legacy_path.is_dir() else legacy_path.exists()
    )
    if has_legacy_code:
        errors.append(f"旧业务路径仍存在：{legacy_path.relative_to(ROOT)}")

for path in UTILS_ROOT.rglob("*.py"):
    for module, line in imports(path):
        if module == WORKFLOW_PREFIX or module.startswith(WORKFLOW_PREFIX + "."):
            errors.append(f"{path.relative_to(ROOT)}:{line}: 公共工具层导入工作流模块 {module}")

for path in APPS_ROOT.rglob("*.py"):
    for module, line in imports(path):
        if matches(module, LEGACY_IMPORT_PREFIXES):
            errors.append(f"{path.relative_to(ROOT)}:{line}: 仍在导入旧模块路径 {module}")
        if module == "apps.utils.http.http" or module.startswith("apps.utils.http.http."):
            errors.append(
                f"{path.relative_to(ROOT)}:{line}: "
                "HTTP 客户端已迁移到 apps.utils.http.client"
            )
        if module == "requests" or module.startswith("requests."):
            errors.append(
                f"{path.relative_to(ROOT)}:{line}: 禁止使用未安装的 requests，请使用 httpx"
            )

for left_root, forbidden_prefix in (
    (APPLICATION_LINKS_ROOT, "apps.workflow.product_applications"),
    (APPLICATION_ROOT, "apps.workflow.application_links"),
):
    for path in left_root.rglob("*.py"):
        for module, line in imports(path):
            if module == forbidden_prefix or module.startswith(forbidden_prefix + "."):
                errors.append(f"{path.relative_to(ROOT)}:{line}: 功能模块之间禁止直接依赖 {module}")

workflow_path = APPLICATION_ROOT / "workflow.py"
for module, line in imports(workflow_path):
    if module == "apps.workflow.product_applications.cjdk" or module.startswith(
        "apps.workflow.product_applications.cjdk."
    ):
        errors.append(
            f"{workflow_path.relative_to(ROOT)}:{line}: workflow 导入 CJDK 私有实现 {module}"
        )

application_classes = [
    (path, node) for path in APPLICATION_ROOT.rglob("*.py") for node in classes(path)
]
if len(application_classes) > 35:
    errors.append(f"product_applications 类数量不得超过 35，实际为 {len(application_classes)}")

if (APPLICATION_ROOT / "ports.py").exists():
    errors.append("单实现模式不保留 ports.py；运行期类型应放在实际使用模块")

config_classes = {node.name for node in classes(HTTP_UTILS_ROOT / "config.py")}
expected_config_classes = {
    "CjdkJyrcSettings",
    "DcppEnvironmentSettings",
    "EnvironmentSettings",
    "IdentityEnvironmentSettings",
    "IdentitySettings",
    "PhotoEnvironmentSettings",
}
if config_classes != expected_config_classes:
    errors.append(
        "外部调用配置模型不一致；"
        f"期望 {sorted(expected_config_classes)}，实际 {sorted(config_classes)}"
    )

if not (APPLICATION_ROOT / "loan_application" / "application.py").exists():
    errors.append("缺少贷款申请模块：apps/workflow/product_applications/loan_application/application.py")

if errors:
    print("\n".join(errors))
    sys.exit(1)

print("Architecture checks passed")
