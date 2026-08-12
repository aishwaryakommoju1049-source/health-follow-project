"""Smoke tests — proves the harness itself works.

If these fail, nothing else in the suite can be trusted.
"""

from __future__ import annotations

import pytest

from app.core.llm import Tier, get_model
from tests.support.stub_llm import StubChatModel, StubExhaustedError


def test_app_is_alive(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_stub_replaces_every_model(stub_llm: StubChatModel) -> None:
    """The autouse fixture must intercept every tier.

    Note the import at the top of this module is ``from app.core.llm import
    get_model`` — the same form agent nodes will use. That is deliberate: it
    proves the stub reaches callers that bound the function into their own
    namespace at import time, which a patch on ``get_model`` would not.
    """
    for tier in Tier:
        assert get_model(tier) is stub_llm


def test_stub_records_the_tier_it_was_asked_for(stub_llm: StubChatModel) -> None:
    stub_llm.always("ok")

    get_model(Tier.MECHANICAL).invoke("classify this")
    get_model(Tier.CRITICAL).invoke("verify this")

    assert stub_llm.call_count == 2
    assert len(stub_llm.calls_for(Tier.MECHANICAL)) == 1
    assert len(stub_llm.calls_for(Tier.CRITICAL)) == 1


def test_stub_returns_queued_responses_in_order(stub_llm: StubChatModel) -> None:
    stub_llm.respond_with("first", "second")
    model = get_model(Tier.CRITICAL)

    assert model.invoke("a") == "first"
    assert model.invoke("b") == "second"


def test_unscripted_call_fails_loudly(stub_llm: StubChatModel) -> None:
    """A silent default would let a test pass while extra calls were made."""
    with pytest.raises(StubExhaustedError):
        get_model(Tier.CRITICAL).invoke("nothing was scripted")


def test_db_fixture_is_usable(db) -> None:
    """Proves the transactional fixture connects and rolls back.

    Skips locally when Postgres is not running; fails in CI, where the
    service container is guaranteed.
    """
    from sqlalchemy import text

    assert db.execute(text("SELECT 1")).scalar_one() == 1
