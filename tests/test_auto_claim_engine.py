"""
Regression tests for auto-claim engine contract and persistence mapping.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from unittest.mock import patch

from backend.app.services.auto_claim_engine import (
    _process_worker_claim,
    run_auto_claim_engine,
)


class _Resp:
    def __init__(self, data=None):
        self.data = data


class _Table:
    def __init__(self, name: str, state: dict):
        self.name = name
        self.state = state
        self._rows = None

    def select(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        return self

    def insert(self, rows):
        self._rows = rows
        self.state.setdefault("inserted", {}).setdefault(self.name, []).append(rows)
        return self

    def execute(self):
        if self.name == "trigger_events":
            return _Resp(self.state.get("triggers", []))
        if self.name == "manual_claims":
            if self.state.get("raise_duplicate_on_claim_insert"):
                raise Exception(
                    'duplicate key value violates unique constraint "idx_unique_worker_event"'
                )
            return _Resp([{"id": "claim-001"}])
        if self.name == "payout_recommendations":
            return _Resp([{"id": "payout-001"}])
        return _Resp([])


class _SB:
    def __init__(self, state: dict):
        self.state = state

    def table(self, name: str):
        return _Table(name, self.state)


class TestAutoClaimEngine:

    @patch("backend.app.services.auto_claim_engine._get_worker_phone", return_value=None)
    @patch("backend.app.services.claim_pipeline.run_claim_pipeline")
    def test_process_worker_claim_maps_pipeline_and_schema(self, mock_pipeline, _mock_phone):
        mock_pipeline.return_value = {
            "review": {
                "decision_action": "auto_approve",
                "decision": "auto_approved",
            },
            "parametric_payout": {"parametric_payout": 1500.0},
            "fraud_analysis": {"fraud_score": 0.11},
            "internal_calibration": {
                "covered_weekly_income_b": 3000,
                "severity_score_s": 0.6,
                "exposure_score_e": 0.7,
                "confidence_score_c": 0.8,
                "fraud_holdback_fh": 0.1,
                "outlier_uplift_u": 1.0,
                "payout_cap": 3000,
                "expected_payout": 1200,
                "gross_premium": 28,
                "recommended_payout_internal": 1100,
            },
        }

        state = {}
        sb = _SB(state)

        result = asyncio.run(
            _process_worker_claim(
                sb=sb,
                worker={
                    "worker_id": "worker-1",
                    "policy": {"plan_type": "essential"},
                    "shift_overlap_ratio": 0.9,
                    "avg_hourly_income": 150,
                    "trust_score": 0.8,
                },
                trigger={"zone_id": "zone-1", "started_at": "2026-04-05T10:00:00Z"},
                trigger_id="trigger-1",
                trigger_code="T2",
                trigger_family="heavy_rain",
                severity_band="claim",
                city="Mumbai",
                observed_value=72,
                threshold_label=">=64.5mm",
            )
        )

        assert result["decision"] == "auto_approve"
        assert result["claim_status"] == "auto_approved"
        assert result["payout_amount"] == 1500.0

        claim_row = state["inserted"]["manual_claims"][0]
        assert "claim_status" in claim_row
        assert "claim_reason" in claim_row
        assert "status" not in claim_row
        assert "description" not in claim_row

        payout_row = state["inserted"]["payout_recommendations"][0]
        assert payout_row["claim_id"] == "claim-001"
        assert payout_row["recommended_payout"] == 1100
        assert payout_row["claim_probability_p"] == 0.15

    @patch("backend.app.services.auto_claim_engine._get_worker_phone", return_value=None)
    @patch("backend.app.services.claim_pipeline.run_claim_pipeline")
    def test_process_worker_claim_skips_duplicate_worker_event(self, mock_pipeline, _mock_phone):
        mock_pipeline.return_value = {
            "review": {
                "decision_action": "auto_approve",
                "decision": "auto_approved",
            },
            "parametric_payout": {"parametric_payout": 1500.0},
            "fraud_analysis": {"fraud_score": 0.11},
            "internal_calibration": {
                "covered_weekly_income_b": 3000,
                "severity_score_s": 0.6,
                "exposure_score_e": 0.7,
                "confidence_score_c": 0.8,
                "fraud_holdback_fh": 0.1,
                "outlier_uplift_u": 1.0,
                "payout_cap": 3000,
                "expected_payout": 1200,
                "gross_premium": 28,
                "recommended_payout_internal": 1100,
            },
        }

        state = {"raise_duplicate_on_claim_insert": True}
        sb = _SB(state)

        result = asyncio.run(
            _process_worker_claim(
                sb=sb,
                worker={
                    "worker_id": "worker-1",
                    "policy": {"plan_type": "essential"},
                },
                trigger={"zone_id": "zone-1", "started_at": "2026-04-05T10:00:00Z"},
                trigger_id="trigger-1",
                trigger_code="T2",
                trigger_family="heavy_rain",
                severity_band="claim",
                city="Mumbai",
                observed_value=72,
                threshold_label=">=64.5mm",
            )
        )

        assert result["decision"] == "skipped_duplicate"
        assert result["worker_id"] == "worker-1"

    @patch("backend.app.services.auto_claim_engine._find_eligible_workers")
    @patch("backend.app.services.auto_claim_engine._process_worker_claim")
    def test_run_auto_claim_engine_counts_duplicates(self, mock_process, mock_eligible):
        state = {
            "triggers": [
                {
                    "id": "trigger-1",
                    "zone_id": "zone-1",
                    "trigger_family": "heavy_rain",
                    "trigger_code": "T2",
                    "severity_band": "claim",
                    "city": "Mumbai",
                    "started_at": "2026-04-05T10:00:00Z",
                    "observed_value": 72,
                    "official_threshold_label": ">=64.5mm",
                }
            ]
        }
        sb = _SB(state)

        mock_eligible.return_value = [{"worker_id": "worker-1", "policy": {"plan_type": "essential"}}]
        mock_process.return_value = {
            "worker_id": "worker-1",
            "decision": "skipped_duplicate",
            "claim_status": "auto_approved",
        }

        summary = asyncio.run(run_auto_claim_engine(sb, lookback_hours=6))

        assert summary["triggers_scanned"] == 1
        assert summary["workers_eligible"] == 1
        assert summary["duplicates_skipped"] == 1
        assert len(summary["errors"]) == 0