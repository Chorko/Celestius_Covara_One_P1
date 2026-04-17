"""Sanity checks for the generated OpenAPI contract."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _load_openapi_spec() -> dict:
    spec_path = Path(__file__).resolve().parents[1] / "backend" / "openapi.yaml"
    return json.loads(spec_path.read_text(encoding="utf-8"))


def test_openapi_contains_review_workflow_paths():
    spec = _load_openapi_spec()

    paths = spec.get("paths", {})
    assert "/claims" in paths
    assert "/claims/{claim_id}" in paths
    assert "/claims/{claim_id}/assign" in paths
    assert "/claims/{claim_id}/review" in paths
    assert "/payouts/claims/{claim_id}/initiate" in paths
    assert "/payouts/claims/{claim_id}/retry" in paths
    assert "/payouts/webhooks/{provider_key}" in paths
    assert "/policies/quote" in paths
    assert "/events/outbox/status" in paths
    assert "/ready" in paths
    assert "/ops/metrics" in paths
    assert "/ops/status" in paths
    assert "/ops/slo" in paths


def test_openapi_review_response_includes_trust_adjustment_contract():
    spec = _load_openapi_spec()

    review_post = spec["paths"]["/claims/{claim_id}/review"]["post"]
    response_schema = (
        review_post["responses"]["200"]["content"]["application/json"]["schema"]
    )
    assert response_schema["$ref"] == "#/components/schemas/AdminReviewResponse"

    components = spec.get("components", {}).get("schemas", {})
    review_response_schema = components.get("AdminReviewResponse", {})
    required_response_fields = set(review_response_schema.get("required", []))
    assert {"status", "claim_id", "decision"}.issubset(required_response_fields)

    trust_adjustment_property = (
        review_response_schema.get("properties", {}).get("trust_adjustment", {})
    )
    trust_adjustment_any_of = trust_adjustment_property.get("anyOf", [])
    trust_adjustment_refs = {
        item.get("$ref")
        for item in trust_adjustment_any_of
        if isinstance(item, dict) and item.get("$ref")
    }
    assert "#/components/schemas/TrustAdjustmentResponse" in trust_adjustment_refs
    assert any(
        isinstance(item, dict) and item.get("type") == "null"
        for item in trust_adjustment_any_of
    )

    trust_adjustment_schema = components.get("TrustAdjustmentResponse", {})
    trust_required_fields = set(trust_adjustment_schema.get("required", []))
    assert {
        "worker_profile_id",
        "previous_trust_score",
        "delta",
        "new_trust_score",
        "event_type",
    }.issubset(trust_required_fields)
