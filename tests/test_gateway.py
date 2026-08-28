"""Talking to the local robot gateway, and telling failures apart."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest
from test_catalog import valid_catalog

from flyto_modules_robotics import gateway as gw
from flyto_modules_robotics.catalog import CapabilityCatalogError


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


def test_catalog_get_uses_bearer_auth_and_starts_no_plan():
    captured = []
    catalog = gw.capability_catalog(opener=responder(valid_catalog(), captured))
    request = captured[0]
    assert request.full_url == "http://127.0.0.1:8766/v1/capabilities"
    assert request.get_method() == "GET"
    assert request.data is None
    assert request.headers["Authorization"] == (
        "Bearer test-only-token-with-at-least-32-bytes!!"
    )
    assert catalog.capabilities[0].runtime_name == "move_relative"


def test_safe_stop_uses_the_session_endpoint_and_returns_its_cancelled_state():
    captured = []
    result = gw.safe_stop(
        "pln-1",
        reason="operator_cancelled",
        opener=responder({"session_id": "pln-1", "status": "cancelled"}, captured),
    )

    request = captured[0]
    assert request.full_url == (
        "http://127.0.0.1:8766/v1/deliveries/pln-1/safe-stop"
    )
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"reason": "operator_cancelled"}
    assert result["status"] == "cancelled"


def test_catalog_refusal_and_invalid_body_keep_fixed_distinct_categories():
    secret = "test-only-token-with-at-least-32-bytes!!"

    def refused(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "Forbidden",
            {},
            io.BytesIO(json.dumps({"detail": f"raw response {secret}"}).encode()),
        )

    with pytest.raises(gw.GatewayRefused) as refused_error:
        gw.capability_catalog(opener=refused)
    assert str(refused_error.value) == "robot gateway refused capability catalog"
    assert secret not in str(refused_error.value)

    with pytest.raises(CapabilityCatalogError) as invalid_error:
        gw.capability_catalog(opener=responder({"secret": secret}))
    assert str(invalid_error.value) == "capability catalog invalid"
    assert secret not in str(invalid_error.value)


def test_catalog_unreachable_is_fixed_and_does_not_leak_url_or_reason(monkeypatch):
    monkeypatch.setenv(gw.GATEWAY_URL_ENV, "http://127.0.0.1:9999/?secret=query")

    def unavailable(request, timeout=None):
        raise urllib.error.URLError("secret transport reason")

    with pytest.raises(gw.GatewayError) as caught:
        gw.capability_catalog(opener=unavailable)
    assert type(caught.value) is gw.GatewayError
    assert str(caught.value) == "robot gateway unavailable"


class _BoundedResponse(io.BytesIO):
    def __init__(self, body, *, content_length=None):
        super().__init__(body)
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_oversized_catalog_success_is_bounded_before_json_decode():
    body = b'{' + b'"secret":"' + b'x' * (gw.MAX_CATALOG_RESPONSE_BYTES + 100) + b'"}'
    response = _BoundedResponse(body)

    with pytest.raises(CapabilityCatalogError) as caught:
        gw.capability_catalog(opener=lambda request, timeout=None: response)

    assert str(caught.value) == "capability catalog invalid"
    assert response.read_sizes == [gw.MAX_CATALOG_RESPONSE_BYTES + 1]
    assert response.tell() == gw.MAX_CATALOG_RESPONSE_BYTES + 1


def test_oversized_http_error_body_is_bounded_and_content_free():
    secret = "test-only-token-with-at-least-32-bytes!!"
    body = (secret.encode() + b"x" * (gw.MAX_CATALOG_RESPONSE_BYTES + 100))
    read_sizes = []

    class ErrorBody(io.BytesIO):
        def read(self, size=-1):
            read_sizes.append(size)
            return super().read(size)

    def refused(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, 500, "secret status", {}, ErrorBody(body)
        )

    with pytest.raises(gw.GatewayRefused) as caught:
        gw.capability_catalog(opener=refused)
    assert str(caught.value) == "robot gateway refused capability catalog"
    assert secret not in str(caught.value)
    assert read_sizes == [gw.MAX_CATALOG_RESPONSE_BYTES + 1]


def test_catalog_content_length_excess_and_truncation_fail_before_parsing():
    for response in (
        _BoundedResponse(b"{}", content_length=gw.MAX_CATALOG_RESPONSE_BYTES + 1),
        _BoundedResponse(b"{}", content_length=3),
    ):
        with pytest.raises(CapabilityCatalogError):
            gw.capability_catalog(opener=lambda request, timeout=None, r=response: r)
    assert response.read_sizes == [gw.MAX_CATALOG_RESPONSE_BYTES + 1]


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


def test_completed_is_terminal_and_is_not_waited_out():
    """The real gateway says "completed"; polling past it wastes the whole timeout."""
    calls = {"n": 0}
    slept = []

    def opener(request, timeout=None):
        calls["n"] += 1
        return responder({"state": "completed"})(request)

    result = gw.await_session("pln-1", opener=opener, sleep=slept.append)
    assert result["state"] == "completed"
    assert calls["n"] == 1, "returned on the first observation"
    assert slept == [], "no poll interval was waited out"
    assert "timed_out" not in result


def test_succeeded_is_still_terminal():
    """The older name stays understood; adding "completed" replaces nothing."""
    slept = []
    result = gw.await_session(
        "pln-1", opener=responder({"state": "succeeded"}), sleep=slept.append
    )
    assert result["state"] == "succeeded"
    assert slept == []
    assert "timed_out" not in result


def test_running_is_not_terminal_and_keeps_polling():
    """Guards the widened set against swallowing a mission that is still moving."""
    states = [{"state": "running"}, {"state": "completed"}]
    calls = {"n": 0}
    slept = []

    def opener(request, timeout=None):
        payload = states[min(calls["n"], len(states) - 1)]
        calls["n"] += 1
        return responder(payload)(request)

    result = gw.await_session("pln-1", opener=opener, sleep=slept.append)
    assert result["state"] == "completed"
    assert calls["n"] == 2, "polled past the nonterminal observation"
    assert slept == [gw.POLL_INTERVAL_SECONDS]


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
