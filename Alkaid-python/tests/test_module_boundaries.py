import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_public_layers_are_recursively_free_of_feature_dependencies() -> None:
    forbidden = (
        "apps.product_applications",
        "apps.jobs",
        "apps.workbench",
    )
    violations: list[str] = []
    for root in (ROOT / "apps/integrations", ROOT / "apps/product_data"):
        for path in root.rglob("*.py"):
            if any(
                name == prefix or name.startswith(prefix + ".")
                for name in _imports(path)
                for prefix in forbidden
            ):
                violations.append(str(path.relative_to(ROOT)))
    assert violations == []


def test_workflow_does_not_depend_on_cjdk_implementation() -> None:
    imports = _imports(ROOT / "apps/product_applications/workflow.py")
    assert not any(
        name == "apps.product_applications.cjdk"
        or name.startswith("apps.product_applications.cjdk.")
        for name in imports
    )
    assert not (ROOT / "apps/product_applications/ports.py").exists()
    assert not (ROOT / "apps/product_applications/cjdk/application.py").exists()
