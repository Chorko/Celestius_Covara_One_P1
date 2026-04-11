"""
Tests for the 5-Layer Ghost Shift Detector (fraud engine).

Validates:
  - Layer 1: Event truth scoring
  - Layer 2: Worker truth + route plausibility slot
  - Layer 3-5: Composite scoring
  - Decision band thresholds
  - Feature vector completeness
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.services.fraud_engine import evaluate_fraud_risk, SIGNAL_WEIGHTS


def _base_worker():
    return {
        "active_days": 6,
        "shift_overlap_ratio": 0.9,
        "orders_before_disruption": 3,
        "prior_claim_rate": 0.0,
        "gps_consistency_score": 0.85,
    }

def _base_trigger():
    return {
        "trigger_family": "heavy_rain",
        "trigger_code": "T01",
        "source_reliability": 0.90,
    }


class TestSignalWeights:
    """Verify signal weights sum to 1.0."""

    def test_weights_sum_to_one(self):
        total = sum(SIGNAL_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Signal weights sum to {total}, expected 1.0"

    def test_route_plausibility_weight_exists(self):
        assert "route_plausibility" in SIGNAL_WEIGHTS, \
            "route_plausibility weight missing — TomTom integration not wired"

    def test_no_network_context_duplicate(self):
        # network_context was replaced by route_plausibility
        assert "network_context" not in SIGNAL_WEIGHTS


class TestEventTruth:
    """Layer 1: Event Truth."""

    def test_valid_trigger_high_score(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
        )
        event_score = result["layers"]["event_truth"]["score"]
        assert event_score >= 0.8, f"Valid trigger should score >= 0.8, got {event_score}"

    def test_no_trigger_low_score(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context={},  # No trigger
        )
        event_score = result["layers"]["event_truth"]["score"]
        assert event_score <= 0.3, f"No trigger should score <= 0.3, got {event_score}"
        assert "no_verified_trigger" in result["flags"]


class TestWorkerTruth:
    """Layer 2: Worker Truth."""

    def test_active_worker_high_score(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
        )
        worker_score = result["layers"]["worker_truth"]["score"]
        assert worker_score >= 0.7, f"Active worker should score >= 0.7, got {worker_score}"

    def test_zero_active_days_flagged(self):
        ctx = _base_worker()
        ctx["active_days"] = 0
        result = evaluate_fraud_risk(worker_context=ctx, trigger_context=_base_trigger())
        assert "zero_active_days" in result["flags"]

    def test_route_plausibility_in_layer(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
        )
        assert "route_plausibility" in result["layers"]["worker_truth"]


class TestDecisionBands:
    """Verify decision band thresholds."""

    def test_clean_claim_auto_approves_or_reviews(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
        )
        # Without evidence, anti-spoof verdict is "review" (uncertain),
        # so "needs_review" is the correct, conservative decision.
        assert result["recommended_action"] in ("auto_approve", "needs_review"), \
            f"Clean claim should auto_approve or needs_review, got {result['recommended_action']}"

    def test_no_trigger_manual_needs_review(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context={},
            manual_claim=True,
        )
        # Should at minimum be needs_review (manual claim escalation)
        assert result["recommended_action"] in ("needs_review", "hold_for_fraud", "reject_spoof_risk")

    def test_fraud_penalty_positive_for_fraud(self):
        ctx = _base_worker()
        ctx["active_days"] = 0
        ctx["gps_consistency_score"] = 0.1
        result = evaluate_fraud_risk(
            worker_context=ctx,
            trigger_context={},
            manual_claim=True,
        )
        assert result["fraud_penalty"] > 0


class TestFeatureVector:
    """Verify ML feature vector completeness."""

    def test_feature_vector_has_route_score(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
        )
        fv = result["feature_vector"]
        assert "route_plausibility_score" in fv
        # Should be a number (not None anymore — TomTom is wired)
        assert fv["route_plausibility_score"] is not None

    def test_feature_vector_has_all_keys(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
        )
        fv = result["feature_vector"]
        expected_keys = [
            "exif_browser_gps_distance_m",
            "shift_overlap_ratio",
            "route_plausibility_score",
            "historical_order_continuity",
            "trigger_correlation_score",
            "evidence_completeness",
            "prior_suspicious_rate",
        ]
        for key in expected_keys:
            assert key in fv, f"Missing feature vector key: {key}"


class TestDeviceTrustIngestion:

    def test_missing_device_context_is_uncertain_not_hard_fail(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
            device_context={},
        )

        anti_spoof = result["layers"]["anti_spoofing"]
        assert anti_spoof["verdict"] in ("pass", "review")
        assert anti_spoof["device_trust_score"] is not None
        assert anti_spoof["device_trust_tier"] in (
            "high",
            "moderate",
            "low",
            "high_risk",
        )
        assert anti_spoof["attestation_verdict"] in (
            "missing",
            "not_configured",
            "not_available",
            "error",
            "failed",
            "invalid",
            "device_not_trusted",
            "passed",
        )

    def test_attestation_failure_is_elevated_in_flags(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
            device_context={
                "context_present": True,
                "signature_verified": True,
                "attestation_verdict": "failed",
                "signal_confidence": "high",
                "is_rooted": True,
            },
        )

        anti_spoof = result["layers"]["anti_spoofing"]
        assert anti_spoof["attestation_verdict"] == "failed"
        assert "attestation_failed" in result["flags"]
        assert result["device_trust"]["attestation_verdict"] == "failed"
