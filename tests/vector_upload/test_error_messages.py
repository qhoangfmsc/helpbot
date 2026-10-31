"""Every kind of failure gets its own specific message (built from fake exceptions: no network, no quota used)."""

import httpx
import pytest
import requests
from google.genai import errors

from helpbot.problems import classify, explain, is_transient
from helpbot.store import REQUEST_TIMEOUT_SECONDS, http_options, with_retries


def gemini(code: int, message: str = "x", quota_id: str | None = None) -> errors.APIError:
    error = {"code": code, "message": message}
    if quota_id:
        error["details"] = [{"violations": [{"quotaId": quota_id}]}]
    cls = errors.ServerError if code >= 500 else errors.ClientError
    return cls(code, {"error": error})


def http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(response=response)


CASES = [
    (gemini(429, quota_id="GenerateRequestsPerDayPerProjectPerModel-FreeTier"), "daily_quota", "DAILY quota"),
    (gemini(429, quota_id="GenerateRequestsPerMinutePerProjectPerModel-FreeTier"), "rate_limit", "rate limit"),
    (gemini(400, "API key not valid. Please pass a valid API key."), "auth", "rejected the API key"),
    (gemini(403, "permission denied"), "auth", "rejected the API key"),
    (gemini(404, "model not found"), "not_found", "could not find the model or store"),
    (gemini(400, "bad request body"), "client_error", "refused the request (HTTP 400)"),
    (gemini(503, "overloaded"), "server_error", "overloaded or down (HTTP 503)"),
    (httpx.ReadTimeout("slow"), "timeout", "Timed out waiting for the server"),
    (requests.exceptions.ReadTimeout(), "timeout", "Timed out waiting for the server"),
    (httpx.ConnectError("no route"), "network", "Cannot reach the server"),
    (requests.exceptions.ConnectionError(), "network", "Cannot reach the server"),
    (TimeoutError("indexing 1-a.md did not finish in 300s"), "indexing_timeout", "did not finish indexing"),
    (http_error(404), "help_center", "Help Center URL not found (HTTP 404)"),
    (http_error(500), "help_center", "Help Center kept failing"),
    (ValueError("no articles to write"), "input", "no articles to write"),
    (KeyError("boom"), "unknown", "Unexpected KeyError"),
]


@pytest.mark.parametrize("error,kind,words", CASES, ids=[c[1] + ":" + type(c[0]).__name__ for c in CASES])
def test_each_failure_has_its_own_kind_and_message(error, kind, words):
    assert classify(error) == kind
    assert words in explain(error)


def test_only_waiting_problems_are_retried():
    assert [k for e, k, _ in CASES if is_transient(e)] == ["rate_limit", "server_error", "timeout", "timeout", "network", "network"]


def test_daily_quota_and_bad_key_fail_at_once_instead_of_waiting():
    for error in (gemini(429, quota_id="GenerateRequestsPerDayPerProjectPerModel-FreeTier"), gemini(403)):
        calls = []

        def call():
            calls.append(1)
            raise error

        with pytest.raises(errors.ClientError):
            with_retries(call, sleep=lambda s: None)
        assert len(calls) == 1


def test_timeouts_and_network_errors_are_retried_a_limited_number_of_times():
    for error in (httpx.ReadTimeout("slow"), httpx.ConnectError("down")):
        calls = []

        def call():
            calls.append(1)
            raise error

        with pytest.raises(type(error)):
            with_retries(call, attempts=3, sleep=lambda s: None)
        assert len(calls) == 3  # bounded: never an endless loop


def test_every_request_has_a_timeout(monkeypatch):
    monkeypatch.delenv("GEMINI_TIMEOUT_SECONDS", raising=False)
    assert http_options().timeout == int(REQUEST_TIMEOUT_SECONDS * 1000)  # the SDK default would be None = wait forever
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "5")
    assert http_options().timeout == 5000
