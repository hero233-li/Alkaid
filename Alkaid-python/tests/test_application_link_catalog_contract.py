import json
import shutil

import pytest

from apps.product_data.catalog import (
    PRODUCT_ROOT,
    REFERENCE_PATH,
    ProductCatalogError,
    load_product_catalog,
)


def _catalog_copy(tmp_path):
    product_root = tmp_path / "products"
    shutil.copytree(PRODUCT_ROOT, product_root)
    reference_path = tmp_path / "reference_data.json"
    shutil.copy2(REFERENCE_PATH, reference_path)
    return product_root, reference_path


def _edit_product(product_root, filename, edit):
    path = product_root / filename
    source = json.loads(path.read_text(encoding="utf-8"))
    edit(source)
    path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")


def _load(product_root, reference_path):
    return load_product_catalog(product_root=product_root, reference_path=reference_path)


def test_application_link_route_requires_request_template(tmp_path) -> None:
    product_root, reference_path = _catalog_copy(tmp_path)
    _edit_product(
        product_root,
        "product_b.json",
        lambda source: source["features"]["applicationLinks"][0].pop("requestTemplate"),
    )
    with pytest.raises(ProductCatalogError, match="requestTemplate"):
        _load(product_root, reference_path)


def test_application_link_route_rejects_unknown_field(tmp_path) -> None:
    product_root, reference_path = _catalog_copy(tmp_path)
    _edit_product(
        product_root,
        "product_b.json",
        lambda source: source["features"]["applicationLinks"][0].update({"unexpected": True}),
    )
    with pytest.raises(ProductCatalogError, match="unexpected"):
        _load(product_root, reference_path)


def test_application_link_route_rejects_unknown_category(tmp_path) -> None:
    product_root, reference_path = _catalog_copy(tmp_path)
    _edit_product(
        product_root,
        "product_b.json",
        lambda source: source["features"]["applicationLinks"][0].update(
            {"categoryCode": "UNKNOWN"}
        ),
    )
    with pytest.raises(ProductCatalogError, match="categoryCode"):
        _load(product_root, reference_path)


def test_application_link_route_rejects_unknown_profile(tmp_path) -> None:
    product_root, reference_path = _catalog_copy(tmp_path)
    _edit_product(
        product_root,
        "product_b.json",
        lambda source: source["features"]["applicationLinks"][0].update(
            {"integrationProfileId": "missing.profile"}
        ),
    )
    with pytest.raises(ProductCatalogError, match="未知 Integration Profile"):
        _load(product_root, reference_path)


def test_application_link_route_id_must_be_globally_unique(tmp_path) -> None:
    product_root, reference_path = _catalog_copy(tmp_path)
    duplicate = "product-a-uat1-dynamic"
    _edit_product(
        product_root,
        "product_b.json",
        lambda source: source["features"]["applicationLinks"][0].update({"routeId": duplicate}),
    )
    with pytest.raises(ProductCatalogError, match="routeId 重复"):
        _load(product_root, reference_path)


def test_product_environment_method_must_match_exactly_one_route(tmp_path) -> None:
    product_root, reference_path = _catalog_copy(tmp_path)

    def duplicate_route(source):
        route = dict(source["features"]["applicationLinks"][0])
        route["routeId"] = "product-b-uat1-normal-second"
        route["applicationMethods"] = ["normal"]
        source["features"]["applicationLinks"].append(route)

    _edit_product(product_root, "product_b.json", duplicate_route)
    with pytest.raises(ProductCatalogError, match="匹配到多条"):
        _load(product_root, reference_path)


def test_product_binding_cannot_overwrite_profile_secrets(tmp_path) -> None:
    product_root, reference_path = _catalog_copy(tmp_path)
    _edit_product(
        product_root,
        "product_b.json",
        lambda source: source["features"]["applicationLinks"][0][
            "payloadBindings"
        ].update({"REQ_BODY": "payload"}),
    )
    with pytest.raises(ProductCatalogError, match="不允许覆盖秘密字段"):
        _load(product_root, reference_path)
