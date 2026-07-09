#!/usr/bin/env python3
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = ROOT / "apps"
FORBIDDEN_IMPORTS = {"requests", "httpx"}
FRAMEWORK_MUTABLE_GLOBALS = {"urlpatterns"}
errors: list[str] = []

for path in APPS_ROOT.rglob("*.py"):
    relative = path.relative_to(APPS_ROOT)
    if relative.parts[0] == "integrations":
        continue
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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
