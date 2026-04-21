"""
Tests for the 8-stage claim pipeline.

Validates the full orchestration flow from trigger validation through
to final decision and audit trace.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.services.claim_pipeline import (
    run_claim_pipeline,
    map_severity_to_band,
    calculate_parametric_payout,
    PAYOUT_BANDS,
)


class TestSeverityToBand:

    def test_low_severity_band_1(self):
        assert map_severity_to_band(0.20) == 1

    def test_mid_severity_band_2(self):
        assert map_severity_to_band(0.50) == 2

    def test_high_severity_band_3(self):
        assert map_severity_to_band(0.80) == 3

    def test_escalation_override(self):
        assert map_severity_to_band(0.10, trigger_band="escalation") == 3

    def test_claim_override(self):
        assert map_severity_to_band(0.10, trigger_band="claim") == 2


class TestParametricPayout:

    def test_band_1_essential(self):
        result = calculate_parametric_payout(1, "essential")
        assert result["parametric_payout"] == 750.0  # 3000 * 0.25

    def test_band_2_essential(self):
        result = calculate_parametric_payout(2, "essential")
        assert result["parametric_payout"] == 1500.0  # 3000 * 0.50

    def test_band_3_essential(self):
        result = calculate_parametric_payout(3, "essential")
        assert result["parametric_payout"] == 3000.0  # 3000 * 1.00

    def test_band_3_plus(self):
        result = calculate_parametric_payout(3, "plus")
        assert result["parametric_payout"] == 4500.0  # 4500 * 1.00


class TestClaimPipeline:

    def _run_clean_auto(self):
        return run_claim_pipeline(
            claim_id="test-001",
            worker_context={
                "active_days": 6,
                "shift_overlap_ratio": 0.9,
                "orders_before_disruption": 3,
                "prior_claim_rate": 0.0,
                "gps_consistency_score": 0.85,
                "avg_hourly_income_inr": 150,
                "trust_score": 0.8,
            },
            trigger_context={
                "trigger_family": "heavy_rain",
                "trigger_code": "T01",
                "source_reliability": 0.90,
                "source_type": "openweather",
                "observed_value": 80,
                "severity_band": "claim",
            },
            claim_mode="trigger_auto",
            plan="essential",
        )

    def test_pipeline_returns_all_sections(self):
        result = self._run_clean_auto()
        assert "pipeline_trace" in result
        assert "computed_scores" in result
        assert "parametric_payout" in result
        assert "fraud_analysis" in result
        assert "review" in result

    def test_pipeline_trace_has_8_stages(self):
        result = self._run_clean_auto()
        stages = {t["stage"] for t in result["pipeline_trace"]}
        # Should have stages 1-8
        assert stages.issuperset({1, 2, 3, 4, 5, 6, 7, 8})

    def test_auto_trigger_approved(self):
        result = self._run_clean_auto()
        # Clean auto-trigger claim should be approved
        assert result["review"]["decision"] in ("auto_approved", "soft_hold_verification")

    def test_parametric_payout_present(self):
        result = self._run_clean_auto()
        pp = result["parametric_payout"]
        assert pp["plan"] == "essential"
        assert pp["parametric_payout"] > 0

    def test_manual_claim_gets_review(self):
        result = run_claim_pipeline(
            claim_id="test-002",
            worker_context={
                "active_days": 6,
                "shift_overlap_ratio": 0.9,
                "orders_before_disruption": 3,
                "prior_claim_rate": 0.0,
                "gps_consistency_score": 0.85,
                "avg_hourly_income_inr": 150,
                "trust_score": 0.8,
            },
            trigger_context=None,
            claim_mode="manual",
            plan="essential",
        )
        # Manual claims should be reviewed or rejected if fraud controls are critical.
        decision = result["review"]["decision"]
        assert decision in (
            "soft_hold_verification",
            "fraud_escalated_review",
            "rejected",
        )

    def test_pipeline_includes_device_trust_summary(self):
        result = self._run_clean_auto()
        trust = result["fraud_analysis"].get("device_trust")
        assert isinstance(trust, dict)
        assert "device_trust_score" in trust
        assert "device_trust_tier" in trust

    def test_pipeline_surfaces_risk_action_pack_in_review(self):
        result = self._run_clean_auto()

        fraud_pack = result["fraud_analysis"].get("risk_action_pack")
        assert isinstance(fraud_pack, dict)
        assert fraud_pack.get("review_priority") in {"p0", "p1", "p2", "p3", "p4"}
        assert isinstance(fraud_pack.get("required_challenges"), list)

        review = result["review"]
        assert "review_priority" in review
        assert "review_sla_minutes" in review
        assert "required_challenges" in review
        assert isinstance(review["required_challenges"], list)

    def test_risky_device_signals_surface_in_fraud_flags(self):
        result = run_claim_pipeline(
            claim_id="test-003",
            worker_context={
                "active_days": 6,
                "shift_overlap_ratio": 0.9,
                "orders_before_disruption": 3,
                "prior_claim_rate": 0.0,
                "gps_consistency_score": 0.85,
                "avg_hourly_income_inr": 150,
                "trust_score": 0.8,
            },
            trigger_context={
                "trigger_family": "heavy_rain",
                "trigger_code": "T01",
                "source_reliability": 0.90,
                "source_type": "openweather",
                "observed_value": 80,
                "severity_band": "claim",
            },
            claim_mode="manual",
            plan="essential",
            device_context={
                "context_present": True,
                "signature_verified": True,
                "attestation_verdict": "failed",
                "is_rooted": True,
                "signal_confidence": "high",
            },
        )

        flags = result["fraud_analysis"].get("flags", [])
        assert "attestation_failed" in flags

        risk_action_pack = result["fraud_analysis"].get("risk_action_pack", {})
        assert isinstance(risk_action_pack, dict)
        assert "device_attestation_rebind" in risk_action_pack.get(
            "required_challenges", []
        )

    def test_fast_lane_override_auto_approves_clean_manual_claim(self, monkeypatch):
        def _manual_ok(*_args, **_kwargs):
            return {
                "evidence_completeness_score": 0.92,
                "geo_confidence_score": 0.95,
                "manual_verification_status": "proceed_to_fraud_check",
                "hold_reasons": [],
            }

        def _fraud_clean(*_args, **_kwargs):
            return {
                "fraud_score": 0.12,
                "fraud_band": "low",
                "recommended_action": "needs_review",
                "flag_count": 0,
                "flags": [],
                "fraud_penalty": 0.01,
                "fraud_confidence": 0.91,
                "base_fraud_score": 0.12,
                "decision_explainability": {
                    "decision_reason_codes": ["decision_needs_review"],
                    "top_signal_contributors": [],
                    "top_calibration_impacts": [],
                    "risk_action_pack": {
                        "risk_tier": "low",
                        "review_priority": "p4",
                        "review_sla_minutes": 1440,
                        "required_challenges": [],
                        "recommended_controls": [],
                        "throttle_strategy": {
                            "enabled": False,
                            "mode": "normal_flow",
                        },
                    },
                },
                "risk_action_pack": {
                    "risk_tier": "low",
                    "review_priority": "p4",
                    "review_sla_minutes": 1440,
                    "required_challenges": [],
                    "recommended_controls": [],
                    "throttle_strategy": {
                        "enabled": False,
                        "mode": "normal_flow",
                    },
                },
                "calibration": {"adjustment_total": 0.0, "applied_rules": []},
                "device_trust": {
                    "device_trust_score": 0.92,
                    "device_trust_tier": "high",
                    "signal_confidence": "high",
                    "attestation_verdict": "passed",
                    "risk_signals": [],
                },
                "requires_liveness_check": False,
                "requires_throttling": False,
                "trust_update": {
                    "current_trust_score": 0.8,
                    "total_penalty": 0.0,
                    "new_trust_score": 0.8,
                    "applied_penalties": [],
                    "trust_degraded": False,
                },
                "layers": {
                    "anti_spoofing": {"score": 0.89},
                    "evidence_integrity": {"score": 0.88},
                },
                "feature_vector": {},
            }

        monkeypatch.setattr(
            "backend.app.services.claim_pipeline.evaluate_manual_claim",
            _manual_ok,
        )
        monkeypatch.setattr(
            "backend.app.services.claim_pipeline.evaluate_fraud_risk",
            _fraud_clean,
        )

        result = run_claim_pipeline(
            claim_id="test-fast-lane-001",
            worker_context={
                "zone_id": "zone-1",
                "active_days": 6,
                "shift_overlap_ratio": 0.9,
                "orders_before_disruption": 3,
                "prior_claim_rate": 0.0,
                "gps_consistency_score": 0.9,
                "avg_hourly_income_inr": 150,
                "trust_score": 0.8,
            },
            trigger_context={
                "trigger_family": "heavy_rain",
                "trigger_code": "T01",
                "source_reliability": 0.95,
                "source_type": "imd",
                "started_at": "2026-04-20T09:00:00Z",
                "severity_band": "claim",
            },
            claim_mode="manual",
            claim_record={
                "zone_id": "zone-1",
                "stated_lat": 12.9716,
                "stated_lng": 77.5946,
            },
            validated_incidents=[
                {
                    "zone_id": "zone-1",
                    "trigger_family": "heavy_rain",
                    "incident_start": "2026-04-20T08:00:00Z",
                    "incident_end": "2026-04-20T12:00:00Z",
                    "validation_source": "imd",
                    "cluster_spike_detected": False,
                }
            ],
            plan="essential",
        )

        assert result["review"]["decision_action"] == "auto_approve"
        assert result["review"]["decision"] == "auto_approved"
        assert any(
            step.get("name") == "fast_lane_decision_override"
            for step in result["pipeline_trace"]
        )
