#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.product_data.execution_config import (  # noqa: E402
    COMPILED_PATH,
    compile_execution_catalog,
    load_execution_catalog,
    render_compiled_catalog,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and compile product execution config")
    parser.add_argument("--check", action="store_true", help="Fail when compiled output is stale")
    args = parser.parse_args()
    rendered = render_compiled_catalog(compile_execution_catalog())
    if args.check:
        source_catalog = compile_execution_catalog()
        try:
            compiled_catalog = load_execution_catalog()
        except ValueError:
            compiled_catalog = None
        if compiled_catalog != source_catalog:
            print("Compiled product execution config is stale")
            return 1
        print("Product execution config is valid and current")
        return 0
    COMPILED_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMPILED_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {COMPILED_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
