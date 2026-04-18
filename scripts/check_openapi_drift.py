"""Fail when backend/openapi.yaml drifts from runtime FastAPI schema."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app


def _normalized_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _stabilize_framework_validation_schema(spec: dict) -> dict:
    """Drop non-contract FastAPI/Pydantic validation-schema noise.

    Newer FastAPI/Pydantic releases may add helper fields like ``input`` and
    ``ctx`` to ``ValidationError`` without changing endpoint contracts.
    """
    normalized = copy.deepcopy(spec)
    schemas = normalized.get("components", {}).get("schemas", {})
    validation_error = schemas.get("ValidationError")
    if isinstance(validation_error, dict):
        props = validation_error.get("properties")
        if isinstance(props, dict):
            props.pop("input", None)
            props.pop("ctx", None)
            props.pop("url", None)
    return normalized


def main() -> int:
    contract_path = ROOT / "backend" / "openapi.yaml"
    if not contract_path.exists():
        print(f"ERROR: Contract file not found: {contract_path}")
        return 1

    try:
        existing_spec = json.loads(contract_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(
            "ERROR: backend/openapi.yaml is not valid JSON content. "
            f"Regenerate it with scripts/generate_openapi.py. Detail: {exc}"
        )
        return 1

    runtime_spec = app.openapi()

    existing_spec = _stabilize_framework_validation_schema(existing_spec)
    runtime_spec = _stabilize_framework_validation_schema(runtime_spec)

    if _normalized_json(existing_spec) != _normalized_json(runtime_spec):
        print("ERROR: OpenAPI contract drift detected.")
        print("Run scripts/generate_openapi.py and commit backend/openapi.yaml.")
        return 1

    print("OpenAPI contract is in sync with runtime schema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
