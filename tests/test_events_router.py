"""
API tests for events router consumer operations endpoints.
"""

import os
import sys
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.dependencies import require_insurer_admin
from backend.app.routers import events


class _DummySB:
    pass


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(events.router)

    async def _mock_admin():
        return {"id": "admin-1", "role": "insurer_admin"}

    app.dependency_overrides[require_insurer_admin] = _mock_admin
    return TestClient(app)


class TestEventsRouterConsumerOps:
    def test_get_consumer_status(self):
        sb = _DummySB()
        expected_counts = {
            "processing": 1,
            "succeeded": 2,
            "failed": 3,
            "dead_letter": 4,
            "total": 10,
        }

        with patch("backend.app.routers.events.get_supabase_admin", return_value=sb), patch(
            "backend.app.routers.events.get_consumer_ledger_status_counts",
            return_value=expected_counts,
        ) as mock_counts:
            with _build_client() as client:
                resp = client.get("/events/consumers/status")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"
        assert payload["counts"] == expected_counts
        mock_counts.assert_called_once_with(sb)

    def test_list_consumer_dead_letters(self):
        sb = _DummySB()
        expected_rows = [
            {"id": "l1", "event_id": "e1", "status": "dead_letter"},
            {"id": "l2", "event_id": "e2", "status": "dead_letter"},
        ]

        with patch("backend.app.routers.events.get_supabase_admin", return_value=sb), patch(
            "backend.app.routers.events.list_dead_letter_consumer_entries",
            return_value=expected_rows,
        ) as mock_list:
            with _build_client() as client:
                resp = client.get("/events/consumers/dead-letter?limit=2")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"
        assert payload["count"] == 2
        assert payload["entries"] == expected_rows
        mock_list.assert_called_once_with(sb, limit=2)

    def test_requeue_consumer_dead_letters(self):
        sb = _DummySB()
        expected_result = {
            "selected": 5,
            "ledger_requeued": 5,
            "outbox_requeued": 5,
        }

        with patch("backend.app.routers.events.get_supabase_admin", return_value=sb), patch(
            "backend.app.routers.events.requeue_dead_letter_consumer_entries",
            return_value=expected_result,
        ) as mock_requeue:
            with _build_client() as client:
                resp = client.post("/events/consumers/dead-letter/requeue?limit=5")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"
        assert payload["selected"] == 5
        assert payload["ledger_requeued"] == 5
        assert payload["outbox_requeued"] == 5
        mock_requeue.assert_called_once_with(sb, limit=5)
