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


def test_product_application_business_layer_does_not_import_cjdk_models() -> None:
    root = ROOT / "apps/product_data/product_applications"
    violations = [
        str(path.relative_to(ROOT))
        for path in root.glob("*.py")
        if "apps.integrations.cjdk_jyrc.models" in _imports(path)
    ]
    assert violations == []


def test_cjdk_integration_does_not_import_catalog_configs_or_jobs() -> None:
    root = ROOT / "apps/integrations/cjdk_jyrc"
    forbidden = (
        "apps.product_data.catalog",
        "apps.product_data.configs",
        "apps.jobs.models",
        "apps.jobs.services",
    )
    violations: list[str] = []
    for path in root.glob("*.py"):
        imports = _imports(path)
        if any(
            any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
            for name in imports
        ):
            violations.append(str(path.relative_to(ROOT)))
    assert violations == []
