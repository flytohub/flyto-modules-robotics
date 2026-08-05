"""Talking to the local robot gateway, and telling failures apart."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from flyto_modules_robotics import gateway as gw


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv(gw.TOKEN_ENV, "test-only-token-with-at-least-32-bytes!!")
    monkeypatch.setenv(gw.ROBOT_ID_ENV, "flyto-tb3-lab-001")
    monkeypatch.delenv(gw.GATEWAY_URL_ENV, raising=False)


def responder(payload, captured=None):
    class _Response(io.StringIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def opener(request, timeout=None):
        if captured is not None:
            captured.append(request)
        return _Response(json.dumps(payload))

    return opener


def test_the_gateway_defaults_to_loopback():
    """A step runs on the robot it drives, so the address is not a parameter."""
    assert gw.gateway_url() == "http://127.0.0.1:8766"


def test_a_configured_gateway_url_is_honoured(monkeypatch):
    monkeypatch.setenv(gw.GATEWAY_URL_ENV, "http://127.0.0.1:9999/")
    assert gw.gateway_url() == "http://127.0.0.1:9999"


def test_a_missing_token_is_refused_before_any_request(monkeypatch):
    monkeypatch.delenv(gw.TOKEN_ENV, raising=False)
    with pytest.raises(gw.GatewayError, match=gw.TOKEN_ENV):
        gw.start_plan({"plan": {}}, opener=responder({}))


def test_a_missing_robot_id_says_so_rather_than_guessing(monkeypatch):
    monkeypatch.delenv(gw.ROBOT_ID_ENV, raising=False)
    with pytest.raises(gw.GatewayError, match=gw.ROBOT_ID_ENV):
        gw.robot_id()


def test_the_request_carries_the_bearer_token_and_the_plan():
    captured = []
    gw.start_plan({"contract_version": "x"}, opener=responder({"session_id": "pln-1"}, captured))
    request = captured[0]
    assert request.full_url == "http://127.0.0.1:8766/v1/plans"
    assert request.headers["Authorization"].startswith("Bearer ")
    assert json.loads(request.data)["contract_version"] == "x"


def test_a_refusal_is_its_own_failure_kind():
    """"The robot would not accept this" and "no robot" need different answers."""
    def opener(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, 400, "Bad Request", {},
            io.BytesIO(json.dumps({"error": "plan_run_request_invalid",
                                   "detail": "a plan that moves must end with safe_stop"}).encode()),
        )

    with pytest.raises(gw.GatewayRefused, match="safe_stop"):
        gw.start_plan({}, opener=opener)


def test_an_unreachable_gateway_names_the_address():
    def opener(request, timeout=None):
        raise urllib.error.URLError("Connection refused")

    with pytest.raises(gw.GatewayError, match="127.0.0.1:8766"):
        gw.start_plan({}, opener=opener)


def test_awaiting_a_session_returns_once_it_is_terminal():
    states = [{"state": "running"}, {"state": "running"}, {"state": "succeeded"}]
    calls = {"n": 0}

    def opener(request, timeout=None):
        payload = states[min(calls["n"], len(states) - 1)]
        calls["n"] += 1
        return responder(payload)(request)

    result = gw.await_session("pln-1", opener=opener, sleep=lambda _: None)
    assert result["state"] == "succeeded"
    assert calls["n"] == 3


def test_giving_up_waiting_does_not_claim_the_mission_failed():
    """The gateway still owns the robot; all this knows is that it stopped watching."""
    clock = {"t": 0.0}

    def monotonic():
        clock["t"] += 10.0
        return clock["t"]

    result = gw.await_session(
        "pln-1",
        timeout_seconds=1.0,
        opener=responder({"state": "running"}),
        sleep=lambda _: None,
        monotonic=monotonic,
    )
    assert result["timed_out"] is True
    assert result["state"] == "running", "not rewritten to failed"
