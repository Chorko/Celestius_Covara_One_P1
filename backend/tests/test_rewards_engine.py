"""Regression tests for rewards engine idempotency safeguards."""

from unittest.mock import AsyncMock

import pytest

from backend.app.services import rewards_engine


class _Response:
    def __init__(self, data):
        self.data = data


class _CoinsLedgerStub:
    """Minimal Supabase-like stub for coins_ledger operations used by award_coins."""

    def __init__(self, existing_rows=None, insert_error: Exception | None = None):
        self.existing_rows = existing_rows or []
        self.insert_error = insert_error
        self.insert_calls = 0
        self.insert_row = None
        self._mode = None

    def table(self, name: str):
        assert name == "coins_ledger"
        return self

    def select(self, *_args, **_kwargs):
        self._mode = "select"
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def insert(self, row: dict):
        self._mode = "insert"
        self.insert_row = row
        return self

    def execute(self):
        if self._mode == "select":
            return _Response(self.existing_rows)

        if self._mode == "insert":
            self.insert_calls += 1
            if self.insert_error:
                raise self.insert_error
            return _Response([{"id": "new_ledger_row"}])

        raise AssertionError("Unexpected query mode in test stub")


@pytest.mark.asyncio
async def test_award_coins_skips_duplicate_reference(monkeypatch):
    sb = _CoinsLedgerStub(existing_rows=[{"id": "existing"}])
    monkeypatch.setattr(rewards_engine, "get_balance", AsyncMock(return_value=34))

    result = await rewards_engine.award_coins(
        sb=sb,
        profile_id="worker_123",
        activity="policy_purchase",
        coins=12,
        description="Weekly essential coverage purchased via Stripe",
        reference_id="cs_test_123",
    )

    assert result["success"] is True
    assert result["idempotent"] is True
    assert result["coins_awarded"] == 0
    assert result["new_balance"] == 34
    assert sb.insert_calls == 0


@pytest.mark.asyncio
async def test_award_coins_treats_unique_conflict_as_idempotent(monkeypatch):
    sb = _CoinsLedgerStub(
        existing_rows=[],
        insert_error=Exception("duplicate key value violates unique constraint"),
    )
    monkeypatch.setattr(rewards_engine, "get_balance", AsyncMock(return_value=34))

    result = await rewards_engine.award_coins(
        sb=sb,
        profile_id="worker_123",
        activity="policy_purchase",
        coins=12,
        description="Weekly essential coverage purchased via Stripe",
        reference_id="cs_test_123",
    )

    assert result["success"] is True
    assert result["idempotent"] is True
    assert result["coins_awarded"] == 0
    assert result["new_balance"] == 34
    assert sb.insert_calls == 1


@pytest.mark.asyncio
async def test_award_coins_inserts_once_for_new_reference(monkeypatch):
    sb = _CoinsLedgerStub(existing_rows=[])
    monkeypatch.setattr(rewards_engine, "get_balance", AsyncMock(return_value=46))

    result = await rewards_engine.award_coins(
        sb=sb,
        profile_id="worker_123",
        activity="policy_purchase",
        coins=12,
        description="Weekly essential coverage purchased via Stripe",
        reference_id="cs_test_123",
    )

    assert result == {"success": True, "coins_awarded": 12, "new_balance": 46}
    assert sb.insert_calls == 1
    assert sb.insert_row["reference_id"] == "cs_test_123"
