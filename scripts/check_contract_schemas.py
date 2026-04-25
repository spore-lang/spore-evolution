#!/usr/bin/env -S uv run

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_ROOT = ROOT / "schemas" / "contracts"
CATALOG_PATH = CONTRACTS_ROOT / "catalog.json"
CATALOG_URL = "https://github.com/spore-lang/spore-evolution/schemas/contracts/catalog.json"
CATALOG_VERSION = 1
OWNER = {
    "repository": "spore-lang/spore-evolution",
    "path": "schemas/contracts",
}
JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def load_json(path: Path) -> tuple[object | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except OSError as exc:
        return None, f"{path}: failed to read JSON file ({exc})"
    except json.JSONDecodeError as exc:
        return (
            None,
            f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
        )


def require_string(entry: dict[str, object], key: str, errors: list[str], scope: str) -> str | None:
    value = entry.get(key)
    if isinstance(value, str) and value:
        return value
    errors.append(f"{scope}: `{key}` must be a non-empty string")
    return None


def require_int(entry: dict[str, object], key: str, errors: list[str], scope: str) -> int | None:
    value = entry.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    errors.append(f"{scope}: `{key}` must be an integer")
    return None


def main() -> int:
    errors: list[str] = []

    if not CATALOG_PATH.exists():
        print(f"Contract schema catalog is missing: {CATALOG_PATH}", file=sys.stderr)
        return 1

    catalog, load_error = load_json(CATALOG_PATH)
    if load_error is not None:
        print(load_error, file=sys.stderr)
        return 1

    if not isinstance(catalog, dict):
        print("Contract schema catalog must be a JSON object.", file=sys.stderr)
        return 1

    if catalog.get("version") != CATALOG_VERSION:
        errors.append(f"{CATALOG_PATH}: `version` must be {CATALOG_VERSION}")

    if catalog.get("catalog") != CATALOG_URL:
        errors.append(f"{CATALOG_PATH}: `catalog` must be `{CATALOG_URL}`")

    if catalog.get("owner") != OWNER:
        errors.append(
            f"{CATALOG_PATH}: `owner` must be {json.dumps(OWNER, ensure_ascii=False, sort_keys=True)}"
        )

    schemas = catalog.get("schemas")
    if not isinstance(schemas, list) or not schemas:
        errors.append(f"{CATALOG_PATH}: `schemas` must be a non-empty array")
        schemas = []

    seen_ids: set[str] = set()
    for index, entry in enumerate(schemas, start=1):
        scope = f"{CATALOG_PATH} schema #{index}"
        if not isinstance(entry, dict):
            errors.append(f"{scope}: entry must be a JSON object")
            continue

        name = require_string(entry, "name", errors, scope)
        title = require_string(entry, "title", errors, scope)
        file_name = require_string(entry, "file", errors, scope)
        schema_id = require_string(entry, "schema_id", errors, scope)
        version = require_int(entry, "version", errors, scope)

        if schema_id is not None:
            if schema_id in seen_ids:
                errors.append(f"{scope}: duplicate `schema_id` `{schema_id}`")
            seen_ids.add(schema_id)

        if version is not None and file_name is not None and f".v{version}." not in file_name:
            errors.append(f"{scope}: file `{file_name}` must include `.v{version}.`")

        if file_name is None:
            continue

        schema_path = CONTRACTS_ROOT / file_name
        if not schema_path.exists():
            errors.append(f"{scope}: schema file does not exist: {schema_path}")
            continue

        schema, load_error = load_json(schema_path)
        if load_error is not None:
            errors.append(load_error)
            continue

        if not isinstance(schema, dict):
            errors.append(f"{schema_path}: schema file must be a JSON object")
            continue

        if schema.get("$schema") != JSON_SCHEMA_DRAFT:
            errors.append(f"{schema_path}: `$schema` must be `{JSON_SCHEMA_DRAFT}`")

        if schema_id is not None and schema.get("$id") != schema_id:
            errors.append(f"{schema_path}: `$id` must match catalog `schema_id`")

        if title is not None and schema.get("title") != title:
            errors.append(f"{schema_path}: `title` must match catalog entry")

        properties = schema.get("properties")
        if not isinstance(properties, dict):
            errors.append(f"{schema_path}: `properties` must be a JSON object")
            continue

        version_prop = properties.get("version")
        if not isinstance(version_prop, dict) or version_prop.get("const") != version:
            errors.append(f"{schema_path}: `properties.version.const` must match catalog version")

        schema_prop = properties.get("schema")
        if not isinstance(schema_prop, dict) or schema_prop.get("const") != schema_id:
            errors.append(f"{schema_path}: `properties.schema.const` must match `$id`")

        catalog_prop = properties.get("schema_catalog")
        if not isinstance(catalog_prop, dict) or catalog_prop.get("const") != CATALOG_URL:
            errors.append(f"{schema_path}: `properties.schema_catalog.const` must be catalog URL")

        if name is not None:
            expected_prefix = f"{name}.v"
            if not file_name.startswith(expected_prefix):
                errors.append(f"{scope}: file `{file_name}` must start with `{expected_prefix}`")

    if errors:
        print("Contract schema validation failed:\n", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(schemas)} contract schema(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
