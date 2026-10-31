"""Chat with the bot the way a customer would: system prompt + File Search over the synced store.

Usage:
  python scripts/chat.py                          # interactive, empty line or Ctrl-D to quit
  python scripts/chat.py "How do I add a YouTube video?"   # one question
Env: GEMINI_API_KEY, GEMINI_FILE_SEARCH_STORE (default helpbot-docs), GEMINI_MODEL (default gemini-3.5-flash).
Exit codes: 0 ok | 2 missing/invalid key | 3 Gemini unreachable, quota used up or timed out (each case prints its own message).
"""

import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from helpbot.problems import EXIT_API, EXIT_CONFIG, classify, explain, is_transient  # noqa: E402
from helpbot.store import DEFAULT_STORE_NAME, FileSearchStore, make_client  # noqa: E402

SYSTEM_PROMPT = (ROOT / "prompts" / "system_prompt.txt").read_text(encoding="utf-8")
# gemini-3.5-flash follows "cite Article URL: lines"; the lite models do not (measured, see docs/backlog.md B1)
DEFAULT_MODEL = "gemini-3.5-flash"
FALLBACK_MODELS = ("gemini-3-flash-preview", "gemini-flash-lite-latest")
ATTEMPTS_PER_MODEL = 3
ANSWER_MAX_SECONDS = 150  # hard limit for one question, whatever the retries and fallbacks add up to
ARTICLE_URL_LINE = re.compile(r"^.*Article URL:.*$", re.M)


class ChatFailed(Exception):
    def __init__(self, message: str, code: int = EXIT_API):
        super().__init__(message)
        self.code = code


def note(text: str) -> None:
    print(f"    ({text})", file=sys.stderr)


def ask(client: genai.Client, store_name: str, question: str, model: str):
    """Preferred model first, then the fallbacks. What happens on a failure depends on its kind (helpbot.problems):
    bad key -> stop; overload/rate limit/timeout/network -> wait and retry; quota used up/model gone -> next model."""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store_name]))],
    )
    deadline = time.monotonic() + ANSWER_MAX_SECONDS
    last: Exception | None = None
    for candidate in (model, *FALLBACK_MODELS):
        for attempt in range(1, ATTEMPTS_PER_MODEL + 1):
            if time.monotonic() > deadline:
                raise ChatFailed(f"gave up after {ANSWER_MAX_SECONDS}s. Last problem: {explain(last) if last else 'none'}")
            try:
                return candidate, client.models.generate_content(model=candidate, contents=question, config=config)
            except Exception as error:
                last = error
                if classify(error) == "auth":
                    raise ChatFailed(explain(error), EXIT_CONFIG) from error
                if is_transient(error) and attempt < ATTEMPTS_PER_MODEL:
                    wait = 3 * attempt
                    note(f"{candidate}: {explain(error)} Retrying in {wait}s")
                    time.sleep(wait)
                    continue
                note(f"{candidate}: {explain(error)} Trying the next model")
                break
    raise ChatFailed(f"every model failed. Last problem: {explain(last)}")


def show(model: str, response, seconds: float) -> None:
    print(f"\n{response.text}\n")
    meta = response.candidates[0].grounding_metadata
    chunks = (meta.grounding_chunks if meta else None) or []
    print(f"--- model: {model} | answered in {seconds:.1f}s | retrieved chunks: {len(chunks)}")
    for chunk in chunks:
        print(f"    source: {chunk.retrieved_context.title}")
    urls = ARTICLE_URL_LINE.findall(response.text or "")
    print(f"--- 'Article URL:' lines in the answer: {len(urls)} (the prompt asks for up to 3)\n")


def answer(client: genai.Client, store_name: str, question: str, model: str) -> None:
    print("Searching the docs and thinking (usually 5-15 s)...", file=sys.stderr)
    started = time.perf_counter()
    used, response = ask(client, store_name, question, model)
    show(used, response, time.perf_counter() - started)


def main() -> int:
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("error: GEMINI_API_KEY is not set (copy .env.sample to .env and fill it in)", file=sys.stderr)
        return EXIT_CONFIG
    client = make_client(api_key)
    try:
        store = FileSearchStore.open(client, os.environ.get("GEMINI_FILE_SEARCH_STORE", DEFAULT_STORE_NAME))
    except Exception as error:
        print(f"error: could not open the store. {explain(error)}", file=sys.stderr)
        return EXIT_CONFIG if classify(error) == "auth" else EXIT_API
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    if len(sys.argv) > 1:
        try:
            answer(client, store.name, " ".join(sys.argv[1:]), model)
        except ChatFailed as failure:
            print(f"error: {failure}", file=sys.stderr)
            return failure.code
        return 0
    while True:
        try:
            question = input("you> ").strip()
        except EOFError:
            return 0
        if not question:
            return 0
        try:
            answer(client, store.name, question, model)
        except ChatFailed as failure:
            print(f"error: {failure}", file=sys.stderr)
            if failure.code == EXIT_CONFIG:  # a bad key will not fix itself; other problems may pass, so keep chatting
                return failure.code


if __name__ == "__main__":
    sys.exit(main())
