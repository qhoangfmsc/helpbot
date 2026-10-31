"""One specific, actionable message per kind of failure (quota, rate limit, bad key, timeout, network...).

Pure functions, no network: they only look at the exception that was raised.
"""

import json

import httpx
import requests
from google.genai import errors

# Exit codes of the job and the scripts
EXIT_SOME_FAILED = 1  # some uploads failed; the next run retries them
EXIT_CONFIG = 2  # missing key, bad id list, nothing to sync
EXIT_API = 3  # Gemini / Help Center unreachable, quota used up or timeouts before the work could start

TRANSIENT = {"rate_limit", "server_error", "timeout", "network"}  # worth retrying after a pause
FATAL_FOR_RUN = {"daily_quota", "auth"}  # every further request would fail the same way: stop the run early


def _text(error: BaseException) -> str:
    return json.dumps(getattr(error, "details", None), default=str) + " " + str(error)


def classify(error: BaseException) -> str:
    """daily_quota | rate_limit | auth | not_found | client_error | server_error | timeout | indexing_timeout |
    network | help_center | input | unknown"""
    if isinstance(error, errors.ClientError):
        if error.code == 429:
            return "daily_quota" if "PerDay" in _text(error) else "rate_limit"
        if error.code in (401, 403) or (error.code == 400 and "API key" in _text(error)):
            return "auth"
        return "not_found" if error.code == 404 else "client_error"
    if isinstance(error, errors.ServerError):
        return "server_error"
    if isinstance(error, TimeoutError):  # the store raises it when indexing takes too long
        return "indexing_timeout"
    if isinstance(error, (httpx.TimeoutException, requests.exceptions.Timeout)):  # before the network check: a subclass
        return "timeout"
    if isinstance(error, (httpx.TransportError, requests.exceptions.ConnectionError, ConnectionError)):
        return "network"
    if isinstance(error, requests.exceptions.RequestException):  # Zendesk, after its retries
        return "help_center"
    if isinstance(error, (ValueError, OSError)):
        return "input"
    return "unknown"


def _describe(error: BaseException) -> tuple[str, str]:
    """(what happened, what to do). Retry notes show only the first part; a final failure shows both."""
    kind = classify(error)
    code = getattr(error, "code", None)
    if kind == "daily_quota":
        return ("Gemini free-tier DAILY quota is used up (free tier: about 20 requests per model per day)",
                "It resets once a day: wait, use another model (chat_model in config/settings.toml) or another API key.")
    if kind == "rate_limit":
        return ("Gemini rate limit reached (too many requests in a short time)",
                "Wait a minute and run again, or lower upload_workers in config/settings.toml.")
    if kind == "auth":
        return "Gemini rejected the API key (invalid, expired or without access)", "Check GEMINI_API_KEY in .env."
    if kind == "not_found":
        return ("Gemini could not find the model or store (the model name may have been retired)",
                "Check chat_model / store_name in config/settings.toml.")
    if kind == "client_error":
        return f"Gemini refused the request (HTTP {code}): {getattr(error, 'message', error)}", ""
    if kind == "server_error":
        return f"Gemini is overloaded or down (HTTP {code})", "It was retried and still failed; run again later."
    if kind == "timeout":
        return ("Timed out waiting for the server (no answer within the request timeout)",
                "Check the network and run again; raise request_timeout_seconds in config/settings.toml if answers are just slow.")
    if kind == "indexing_timeout":
        return f"Gemini did not finish indexing in time: {error}", "The next run retries that file."
    if kind == "network":
        return "Cannot reach the server (network down, DNS or proxy problem)", "Check your internet connection and run again."
    if kind == "help_center":
        status = getattr(getattr(error, "response", None), "status_code", None)
        if status == 404:
            return "Help Center URL not found (HTTP 404)", "Check help_center_url in config/settings.toml."
        return f"The Help Center kept failing after retries ({type(error).__name__}, HTTP {status})", "Run again in a few minutes."
    if kind == "input":
        return str(error), ""
    return f"Unexpected {type(error).__name__}: {error}", ""


def summarize(error: BaseException) -> str:
    """What happened, in one short clause: for notes such as "retrying in 3s"."""
    return _describe(error)[0]


def explain(error: BaseException) -> str:
    """What happened and what to do about it: for the final message of a failure."""
    summary, advice = _describe(error)
    if not advice:
        return summary
    return f"{summary}. {advice}"


def is_transient(error: BaseException) -> bool:
    return classify(error) in TRANSIENT
