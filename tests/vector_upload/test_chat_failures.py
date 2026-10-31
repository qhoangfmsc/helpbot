"""scripts/chat.py and scripts/check_store.py: each failure ends with its own message and exit code, and never loops forever."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors

ROOT = Path(__file__).resolve().parents[2]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


chat = load("chat")
check_store = load("check_store")
DAILY = errors.ClientError(429, {"error": {"message": "quota", "details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}})
AUTH = errors.ClientError(400, {"error": {"message": "API key not valid. Please pass a valid API key."}})


class FakeClient:
    """`script` maps a model name to a list of outcomes: an exception is raised, anything else is returned."""

    def __init__(self, script):
        self.script, self.calls = script, []
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, model, contents, config):
        self.calls.append(model)
        outcomes = self.script.get(model, [httpx.ReadTimeout("slow")])
        outcome = outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(chat.time, "sleep", lambda s: None)


def test_a_rejected_key_stops_at_once_with_the_config_exit_code():
    client = FakeClient({"gemini-3.5-flash": [AUTH]})
    with pytest.raises(chat.ChatFailed) as failure:
        chat.ask(client, "store", "q", "gemini-3.5-flash")
    assert failure.value.code == 2 and "rejected the API key" in str(failure.value)
    assert client.calls == ["gemini-3.5-flash"]  # no retries, no other model


def test_daily_quota_moves_to_the_next_model_without_waiting():
    client = FakeClient({"gemini-3.5-flash": [DAILY], "gemini-3-flash-preview": ["ANSWER"]})
    model, response = chat.ask(client, "store", "q", "gemini-3.5-flash")
    assert (model, response) == ("gemini-3-flash-preview", "ANSWER")
    assert client.calls == ["gemini-3.5-flash", "gemini-3-flash-preview"]


def test_overload_is_retried_on_the_same_model_then_succeeds():
    overloaded = errors.ServerError(503, {"error": {"message": "overloaded"}})
    client = FakeClient({"gemini-3.5-flash": [overloaded, overloaded, "ANSWER"]})
    assert chat.ask(client, "store", "q", "gemini-3.5-flash") == ("gemini-3.5-flash", "ANSWER")
    assert client.calls == ["gemini-3.5-flash"] * 3


def test_timeouts_everywhere_end_with_a_bounded_number_of_attempts_and_a_clear_message():
    client = FakeClient({})  # every model times out forever
    with pytest.raises(chat.ChatFailed) as failure:
        chat.ask(client, "store", "q", "gemini-3.5-flash")
    assert len(client.calls) == 3 * chat.ATTEMPTS_PER_MODEL  # 3 models x 3 attempts, then it gives up
    assert "every model failed" in str(failure.value) and "Timed out waiting for the server" in str(failure.value)
    assert failure.value.code == 3


def test_a_question_has_a_hard_time_limit(monkeypatch):
    monkeypatch.setattr(chat, "ANSWER_MAX_SECONDS", -1)
    client = FakeClient({"gemini-3.5-flash": ["ANSWER"]})
    with pytest.raises(chat.ChatFailed, match="gave up after"):
        chat.ask(client, "store", "q", "gemini-3.5-flash")
    assert client.calls == []


def test_chat_without_a_key_exits_2_and_says_how_to_fix_it(monkeypatch, capsys):
    monkeypatch.setattr(chat, "load_dotenv", lambda path: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert chat.main() == 2
    assert "GEMINI_API_KEY is not set" in capsys.readouterr().err


def test_chat_exits_3_with_the_reason_when_the_store_cannot_be_opened(monkeypatch, capsys):
    monkeypatch.setattr(chat, "load_dotenv", lambda path: None)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(chat, "make_client", lambda key, timeout=None: object())
    monkeypatch.setattr(chat.FileSearchStore, "open", staticmethod(lambda client, name: (_ for _ in ()).throw(httpx.ConnectError("down"))))
    monkeypatch.setattr(chat.sys, "argv", ["chat.py", "hello"])
    assert chat.main() == 3
    assert "Cannot reach the server" in capsys.readouterr().err


def test_check_store_reports_why_it_could_not_read_the_store(monkeypatch, capsys):
    monkeypatch.setattr(check_store, "load_dotenv", lambda path: None)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(check_store, "make_client", lambda key, timeout=None: object())
    monkeypatch.setattr(check_store.FileSearchStore, "open", staticmethod(lambda client, name: (_ for _ in ()).throw(DAILY)))
    assert check_store.main() == 3
    assert "DAILY quota" in capsys.readouterr().err


def test_check_store_without_a_key_exits_2(monkeypatch, capsys):
    monkeypatch.setattr(check_store, "load_dotenv", lambda path: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert check_store.main() == 2
