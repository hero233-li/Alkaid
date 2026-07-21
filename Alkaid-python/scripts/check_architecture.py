#!/usr/bin/env python3
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = ROOT / "apps"
FORBIDDEN_IMPORTS = {"requests", "httpx"}
FRAMEWORK_MUTABLE_GLOBALS = {"urlpatterns"}
FORBIDDEN_PRODUCT_DATA_CLASS_SUFFIXES = ("Flow", "Context", "Handler", "Adapter")
REMOVED_THIN_ADAPTERS = (
    "integrations/application_link/adapter.py",
    "integrations/business_access/adapter.py",
    "integrations/card_status/adapter.py",
    "integrations/loan_status/adapter.py",
    "integrations/verification_approval/adapter.py",
    "integrations/mock_product/adapters/application.py",
    "integrations/example_system/adapter.py",
)
errors: list[str] = []

for relative_path in REMOVED_THIN_ADAPTERS:
    if (APPS_ROOT / relative_path).exists():
        errors.append(f"apps/{relative_path}: removed thin adapter was reintroduced")

for path in APPS_ROOT.rglob("*.py"):
    relative = path.relative_to(APPS_ROOT)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    if relative.parts[0] == "integrations":
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("apps.product_data")
            ):
                location = f"{path.relative_to(ROOT)}:{node.lineno}"
                errors.append(f"{location}: integration adapter imports product-data business code")
        continue

    if relative.parts[0] == "product_data":
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith(
                FORBIDDEN_PRODUCT_DATA_CLASS_SUFFIXES
            ):
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: forbidden orchestration class "
                    f"{node.name}"
                )
            if relative.name == "tasks.py" and isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("apps.integrations"):
                    errors.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: task imports integration directly"
                    )
            if relative.name == "views.py" and isinstance(node, ast.ImportFrom):
                if node.module in {"apps.jobs.dispatch", "apps.jobs.services"}:
                    errors.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: "
                        "menu view bypasses submit_async_job"
                    )
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
