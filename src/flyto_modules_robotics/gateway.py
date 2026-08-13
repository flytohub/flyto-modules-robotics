"""Talking to the robot gateway that happens to be on this machine.

A step never names a machine. The job it belongs to was already dispatched to a
device, so this code is running on the robot it drives, and the gateway is on
loopback. That is what lets five identical robots share one authored workflow
instead of five copies differing only by address.

The address is configuration rather than a parameter for the same reason. A
workflow that carried a host would be bound to one robot, which is the
duplication the capability model exists to remove — just wearing a URL instead
of a device id.

Only the standard library is used, so installing this package pulls nothing in.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from .catalog import CapabilityCatalog, CapabilityCatalogError, parse_capability_catalog

DEFAULT_GATEWAY_URL = "http://127.0.0.1:8766"
GATEWAY_URL_ENV = "FLYTO_ROBOTICS_GATEWAY_URL"
TOKEN_ENV = "FLYTO_ROBOTICS_DELIVERY_TOKEN"
ROBOT_ID_ENV = "FLYTO_ROBOTICS_ROBOT_ID"

# A loopback request should answer immediately; a mission is waited for by
# polling, not by holding a socket open for its duration.
REQUEST_TIMEOUT_SECONDS = 5.0
POLL_INTERVAL_SECONDS = 0.5
DEFAULT_MISSION_TIMEOUT_SECONDS = 120.0
MAX_CATALOG_RESPONSE_BYTES = 256 * 1024

# The lower gateway reports a finished mission as "completed"; earlier revisions
# of this client only knew "succeeded" and so kept polling a mission that was
# already over until the timeout marked it timed_out. Both are terminal, and the
# older names are kept so a gateway that still emits them is understood.
TERMINAL_STATES = frozenset(
    {"completed", "succeeded", "failed", "cancelled", "aborted"}
)


class GatewayError(RuntimeError):
    """The robot gateway could not be reached, or refused the request."""


class GatewayRefused(GatewayError):
    """The gateway rejected the plan. The detail is operator-facing."""


def gateway_url() -> str:
    return (os.environ.get(GATEWAY_URL_ENV) or DEFAULT_GATEWAY_URL).rstrip("/")


def robot_id() -> str:
    value = (os.environ.get(ROBOT_ID_ENV) or "").strip()
    if not value:
        raise GatewayError(
            f"{ROBOT_ID_ENV} is not set; a step cannot guess which robot it drives"
        )
    return value


def _token() -> str:
    value = (os.environ.get(TOKEN_ENV) or "").strip()
    if not value:
        raise GatewayError(f"{TOKEN_ENV} is not set")
    return value


def _call(
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    max_response_bytes: int | None = None,
    opener=urllib.request.urlopen,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{gateway_url()}{path}",
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_token()}",
            **({"Content-Type": "application/json"} if payload is not None else {}),
        },
    )
    try:
        with opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if max_response_bytes is not None:
                return _bounded_json(response, max_response_bytes)
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if max_response_bytes is not None:
            try:
                _bounded_json(exc, max_response_bytes)
            except CapabilityCatalogError:
                pass
            raise GatewayRefused("robot gateway refused capability catalog") from None
        try:
            body = json.load(exc)
        except Exception:  # noqa: BLE001 - an error body may be anything
            body = {}
        detail = str(body.get("detail") or body.get("error") or exc.code)
        # A refusal is the gateway doing its job. Surfaced as its own type so a
        # step reports "the robot would not accept this" rather than "network".
        raise GatewayRefused(detail[:300]) from exc
    except urllib.error.URLError as exc:
        if max_response_bytes is not None:
            raise GatewayError("robot gateway unavailable") from None
        raise GatewayError(
            f"no robot gateway at {gateway_url()}: {exc.reason}"
        ) from exc


def _bounded_json(stream: Any, maximum: int) -> dict[str, Any]:
    """Read one bounded JSON object without reflecting untrusted content."""
    headers = getattr(stream, "headers", None)
    declared = headers.get("Content-Length") if headers is not None else None
    if declared is not None:
        try:
            length = int(declared)
        except (TypeError, ValueError):
            raise CapabilityCatalogError() from None
        if length < 0 or length > maximum:
            raise CapabilityCatalogError()

    try:
        raw = stream.read(maximum + 1)
    except Exception:
        raise CapabilityCatalogError() from None
    if isinstance(raw, str):
        try:
            encoded = raw.encode("utf-8")
        except UnicodeError:
            raise CapabilityCatalogError() from None
    elif isinstance(raw, bytes):
        encoded = raw
    else:
        raise CapabilityCatalogError()
    if len(encoded) > maximum or (declared is not None and len(encoded) != length):
        raise CapabilityCatalogError()
    try:
        value = json.loads(encoded.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise CapabilityCatalogError() from None
    if not isinstance(value, dict):
        raise CapabilityCatalogError()
    return value


def start_plan(
    request: dict[str, Any],
    *,
    opener=urllib.request.urlopen,
) -> dict[str, Any]:
    """Hand a wrapped plan to the gateway and return the session it created."""
    return _call("/v1/plans", payload=request, opener=opener)


def capability_catalog(*, opener=urllib.request.urlopen) -> CapabilityCatalog:
    """Read and strictly validate the gateway catalog without starting a plan."""
    payload = _call(
        "/v1/capabilities",
        max_response_bytes=MAX_CATALOG_RESPONSE_BYTES,
        opener=opener,
    )
    return parse_capability_catalog(payload)


def session(session_id: str, *, opener=urllib.request.urlopen) -> dict[str, Any]:
    return _call(f"/v1/deliveries/{session_id}", opener=opener)


def await_session(
    session_id: str,
    *,
    timeout_seconds: float = DEFAULT_MISSION_TIMEOUT_SECONDS,
    opener=urllib.request.urlopen,
    sleep=time.sleep,
    monotonic=time.monotonic,
) -> dict[str, Any]:
    """Poll until the mission reaches an outcome, or give up saying so.

    Giving up does not stop the robot and does not pretend the mission failed —
    the gateway still owns it, and the last observed payload is returned with a
    ``timed_out`` marker so a caller can report what it actually knows.
    """
    deadline = monotonic() + max(1.0, float(timeout_seconds))
    latest: dict[str, Any] = {}
    while True:
        latest = session(session_id, opener=opener)
        state = str(latest.get("state") or latest.get("status") or "").lower()
        if state in TERMINAL_STATES:
            return latest
        if monotonic() >= deadline:
            return {**latest, "timed_out": True}
        sleep(POLL_INTERVAL_SECONDS)
