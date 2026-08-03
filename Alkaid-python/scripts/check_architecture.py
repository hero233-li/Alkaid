#!/usr/bin/env python3
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = ROOT / "apps"
FORBIDDEN_IMPORTS = {"requests", "httpx"}
FRAMEWORK_MUTABLE_GLOBALS = {"urlpatterns"}
INTEGRATION_FORBIDDEN_PREFIXES = {
    "apps.product_data.catalog",
    "apps.product_data.configs",
    "apps.jobs.models",
    "apps.jobs.services",
}
PUBLIC_INTEGRATION_FILES = {
    Path("integrations/contracts.py"),
    Path("integrations/http.py"),
}
PUBLIC_INTEGRATION_FORBIDDEN_PREFIXES = {
    "apps.integrations.cjdk_jyrc",
    "apps.product_data",
    "apps.jobs",
    "apps.workbench",
}
PRIVATE_INTEGRATION_PREFIXES = {"apps.integrations.cjdk_jyrc"}
PRIVATE_INTEGRATION_CONNECTOR_FILES = {
    Path("core/readiness.py"),
    Path("core/views.py"),
    Path("jobs/dispatch.py"),
    Path("product_data/application_link_plan.py"),
    Path("product_data/product_applications/tasks.py"),
}
errors: list[str] = []


def imported_modules(tree: ast.AST) -> set[tuple[str, int]]:
    modules: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add((node.module, node.lineno))
    return modules


def matches_prefix(module: str, prefixes: set[str]) -> bool:
    return any(module == prefix or module.startswith(prefix + ".") for prefix in prefixes)


for path in APPS_ROOT.rglob("*.py"):
    relative = path.relative_to(APPS_ROOT)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = imported_modules(tree)
    if relative in PUBLIC_INTEGRATION_FILES:
        for module, lineno in modules:
            if matches_prefix(module, PUBLIC_INTEGRATION_FORBIDDEN_PREFIXES):
                errors.append(
                    f"{path.relative_to(ROOT)}:{lineno}: public integration imports "
                    f"private dependency {module}"
                )
    if relative == Path("product_data/catalog.py"):
        for module, lineno in modules:
            if module == "apps.integrations.cjdk_jyrc" or module.startswith(
                "apps.integrations.cjdk_jyrc."
            ):
                errors.append(
                    f"{path.relative_to(ROOT)}:{lineno}: product catalog imports CJDK private code"
                )
    if (
        relative.parts[:2] != ("integrations", "cjdk_jyrc")
        and relative not in PRIVATE_INTEGRATION_CONNECTOR_FILES
    ):
        for module, lineno in modules:
            if matches_prefix(module, PRIVATE_INTEGRATION_PREFIXES):
                errors.append(
                    f"{path.relative_to(ROOT)}:{lineno}: non-composition module imports "
                    f"private integration {module}"
                )
    if relative.parts[0] == "integrations":
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and any(
                    node.module == prefix or node.module.startswith(prefix + ".")
                    for prefix in INTEGRATION_FORBIDDEN_PREFIXES
                )
            ):
                location = f"{path.relative_to(ROOT)}:{node.lineno}"
                errors.append(
                    f"{location}: integration imports forbidden catalog/config/job dependency"
                )
        continue
    for node in ast.walk(tree):
        imported: set[str] = set()
        if isinstance(node, ast.Import):
            imported = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported = {node.module.split(".")[0]}
        forbidden = imported & FORBIDDEN_IMPORTS
        if forbidden:
            location = f"{path.relative_to(ROOT)}:{node.lineno}"
            errors.append(f"{location}: direct HTTP import {sorted(forbidden)}")

    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, (ast.Dict, ast.List, ast.Set)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Name)
                and not target.id.isupper()
                and target.id not in FRAMEWORK_MUTABLE_GLOBALS
            ):
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: mutable module global {target.id}"
                )

if errors:
    print("\n".join(errors))
    sys.exit(1)

print("Architecture checks passed")
