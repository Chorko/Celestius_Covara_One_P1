"""Sanity checks for the generated OpenAPI contract."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_openapi_contains_review_workflow_paths():
    spec_path = Path(__file__).resolve().parents[1] / "backend" / "openapi.yaml"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

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
