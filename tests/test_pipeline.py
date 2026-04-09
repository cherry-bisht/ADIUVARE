import asyncio

from adiuvare.core.models import RequestContext
from adiuvare.core.pipeline import Pipeline
from adiuvare.state.identity_store import IdentityStore


def test_pipeline_runs_end_to_end():
    ctx = RequestContext(
        identity="u1",
        payload="select * from users",
        url="/login",
        method="POST",
        headers={"User-Agent": "Mozilla/5.0"},
        ip="127.0.0.1",
        endpoint="/login",
    )

    gate, out = asyncio.run(Pipeline(IdentityStore()).process(ctx))
    assert gate.passed is True
    assert out is not None
    assert out.verdict == "flag"


def test_pipeline_stops_when_gate_fails():
    store = IdentityStore()
    store.block("u1")

    ctx = RequestContext(
        identity="u1",
        payload="select * from users",
        url="/login",
        method="POST",
        headers={"User-Agent": "Mozilla/5.0"},
        ip="127.0.0.1",
        endpoint="/login",
    )

    gate, out = asyncio.run(Pipeline(store).process(ctx))
    assert gate.passed is False
    assert out is None


def test_pipeline_picks_up_suspicious_user_agent():
    ctx = RequestContext(
        identity="u1",
        payload=None,
        url="/",
        method="GET",
        headers={"User-Agent": "curl/8.0"},
        ip="127.0.0.1",
        endpoint="/",
    )

    gate, out = asyncio.run(Pipeline(IdentityStore()).process(ctx))
    assert gate.passed is True
    assert out is not None
    assert out.score > 0.0


def test_pipeline_marks_missing_user_agent_as_suspicious():
    ctx = RequestContext(
        identity="u1",
        payload=None,
        url="/",
        method="GET",
        headers={},
        ip="127.0.0.1",
        endpoint="/",
    )

    gate, out = asyncio.run(Pipeline(IdentityStore()).process(ctx))
    assert gate.passed is True
    assert out is not None
    assert out.score > 0.0


def test_pipeline_writes_score_back_to_identity_store():
    store = IdentityStore()
    ctx = RequestContext(
        identity="u1",
        payload="select * from users",
        url="/login",
        method="POST",
        headers={"User-Agent": "Mozilla/5.0"},
        ip="127.0.0.1",
        endpoint="/login",
    )

    gate, out = asyncio.run(Pipeline(store).process(ctx))
    assert gate.passed is True
    assert out is not None
    assert store.get("u1").score_ewma == out.score


def test_pipeline_repeats_pick_up_identity_state():
    store = IdentityStore()
    ctx = RequestContext(
        identity="u1",
        payload="select * from users",
        url="/login",
        method="POST",
        headers={"User-Agent": "Mozilla/5.0"},
        ip="127.0.0.1",
        endpoint="/login",
    )

    _, first = asyncio.run(Pipeline(store).process(ctx))
    _, second = asyncio.run(Pipeline(store).process(ctx))
    assert first is not None
    assert second is not None
    assert second.score > first.score
    assert store.get("u1").score_ewma < second.score
