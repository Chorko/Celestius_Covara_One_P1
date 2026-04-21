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

    def test_cluster_intelligence_weight_exists(self):
        assert "cluster_intelligence" in SIGNAL_WEIGHTS


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


class TestFraudCalibration:

    def test_attestation_failure_adds_calibration_rule(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
            device_context={
                "context_present": True,
                "signature_verified": True,
                "attestation_verdict": "failed",
                "signal_confidence": "high",
            },
        )

        calibration = result.get("calibration", {})
        applied = calibration.get("applied_rules", [])
        assert any(rule.get("rule") == "attestation_failed" for rule in applied)
        assert result.get("fraud_score", 0.0) >= result.get("base_fraud_score", 0.0)

    def test_cluster_risk_is_counted_in_scoring(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
            zone_claims_last_hour=60,
            zone_avg_hourly=5.0,
        )

        assert result["layers"]["cluster_intelligence"]["cluster_risk"] >= 0.9
        calibration = result.get("calibration", {})
        applied = calibration.get("applied_rules", [])
        assert any(rule.get("rule") == "cluster_risk_critical" for rule in applied)

    def test_cluster_intelligence_accepts_claimed_at_batch_timestamps(self):
        claim_ts = "2026-04-20T10:00:00Z"
        recent_batch = [
            {
                "stated_lat": 12.97160,
                "stated_lng": 77.59460,
                "claimed_at": "2026-04-20T09:59:20Z",
            },
            {
                "stated_lat": 12.97164,
                "stated_lng": 77.59458,
                "claimed_at": "2026-04-20T09:59:40Z",
            },
            {
                "stated_lat": 12.97158,
                "stated_lng": 77.59463,
                "claimed_at": "2026-04-20T10:00:10Z",
            },
        ]

        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
            claim_data={
                "stated_lat": 12.97161,
                "stated_lng": 77.59461,
                "claimed_at": claim_ts,
            },
            recent_claims_batch=recent_batch,
            zone_claims_last_hour=0,
            zone_avg_hourly=5.0,
        )

        cluster_layer = result["layers"]["cluster_intelligence"]
        assert cluster_layer["cluster_risk"] >= 0.5
        assert any(
            flag in result["flags"]
            for flag in ("dbscan_fraud_cluster_match", "cluster_density_fallback_match")
        )

    def test_evidence_forensics_receives_runtime_image_bytes(self, monkeypatch):
        captured: dict[str, bytes | None] = {"file_bytes": None}

        def _integrity_stub(exif_metadata, file_bytes=None, worker_context=None):
            captured["file_bytes"] = file_bytes
            return {
                "integrity_score": 0.91,
                "flags": [],
                "checks": {
                    "ai_generation": {
                        "ai_generated_probability": 0.02,
                        "synthid_detected": False,
                        "c2pa_metadata_found": False,
                    }
                },
            }

        monkeypatch.setattr(
            "backend.app.services.fraud_engine.analyze_evidence_integrity",
            _integrity_stub,
        )

        image_bytes = b"\x89PNGmock"
        evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
            evidence_records=[
                {
                    "evidence_type": "photo",
                    "exif_timestamp": "2026:04:20 10:00:00",
                    "_file_bytes": image_bytes,
                }
            ],
        )

        assert captured["file_bytes"] == image_bytes


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


class TestFraudExplainability:

    def test_explainability_has_reason_codes_and_contributors(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
            manual_claim=True,
            zone_claims_last_hour=60,
            zone_avg_hourly=5.0,
        )

        explainability = result.get("decision_explainability")
        assert isinstance(explainability, dict)

        reason_codes = explainability.get("decision_reason_codes", [])
        assert isinstance(reason_codes, list)
        assert len(reason_codes) > 0
        assert any(
            code in reason_codes
            for code in (
                "decision_needs_review",
                "decision_hold_for_fraud",
                "decision_batch_hold",
                "decision_reject_spoof_risk",
            )
        )

        contributors = explainability.get("top_signal_contributors", [])
        assert isinstance(contributors, list)
        assert len(contributors) > 0
        first = contributors[0]
        assert "signal" in first
        assert "risk_impact" in first

    def test_explainability_reflects_attestation_failure(self):
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
            manual_claim=True,
        )

        reason_codes = (
            result.get("decision_explainability", {}).get(
                "decision_reason_codes", []
            )
        )
        assert "attestation_failed" in reason_codes


class TestFraudRiskActionPack:

    def test_compromised_manual_without_trigger_rejects(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context={},
            manual_claim=True,
            device_context={
                "context_present": True,
                "signature_verified": True,
                "attestation_verdict": "failed",
                "signal_confidence": "high",
                "is_rooted": True,
            },
        )

        assert result["recommended_action"] == "reject_spoof_risk"
        assert "emulator_detected" in result["flags"]

    def test_risk_action_pack_has_priority_and_challenges(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
            manual_claim=True,
            zone_claims_last_hour=80,
            zone_avg_hourly=5.0,
            device_context={
                "context_present": True,
                "signature_verified": True,
                "attestation_verdict": "failed",
                "signal_confidence": "high",
                "is_rooted": True,
            },
        )

        pack = result.get("risk_action_pack", {})
        assert isinstance(pack, dict)
        assert pack.get("review_priority") in {"p0", "p1", "p2", "p3", "p4"}
        assert isinstance(pack.get("review_sla_minutes"), int)
        challenges = pack.get("required_challenges", [])
        assert isinstance(challenges, list)
        assert "device_attestation_rebind" in challenges

    def test_missing_signed_context_reason_code_present(self):
        result = evaluate_fraud_risk(
            worker_context=_base_worker(),
            trigger_context=_base_trigger(),
            manual_claim=True,
            device_context={},
        )

        reason_codes = result.get("decision_explainability", {}).get(
            "decision_reason_codes", []
        )
        assert "missing_signed_device_context" in reason_codes
