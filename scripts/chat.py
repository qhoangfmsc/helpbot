"""Chat with the bot the way a customer would: system prompt + File Search over the synced store.

Usage:
  python scripts/chat.py                          # interactive, empty line or Ctrl-D to quit
  python scripts/chat.py "How do I add a YouTube video?"   # one question
Env: GEMINI_API_KEY, GEMINI_FILE_SEARCH_STORE (default helpbot-docs), GEMINI_MODEL (default gemini-3.5-flash-lite).
"""

import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from helpbot.store import DEFAULT_STORE_NAME, FileSearchStore  # noqa: E402

SYSTEM_PROMPT = Path(__file__).resolve().parent.parent.joinpath("prompts/system_prompt.txt").read_text(encoding="utf-8")
FALLBACK_MODELS = ("gemini-flash-lite-latest", "gemini-3-flash-preview")
ARTICLE_URL_LINE = re.compile(r"^.*Article URL:.*$", re.M)


def ask(client: genai.Client, store_name: str, question: str, model: str):
    """Try the preferred model, then fallbacks; each is retried a few times on overload (503) / rate limit (429)."""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store_name]))],
    )
    last: Exception | None = None
    for candidate in (model, *FALLBACK_MODELS):
        for attempt in range(3):
            try:
                return candidate, client.models.generate_content(model=candidate, contents=question, config=config)
            except (errors.ServerError, errors.ClientError) as error:
                if isinstance(error, errors.ClientError) and error.code != 429:
                    last = error
                    break  # e.g. model not available: go to the next model
                last = error
                time.sleep(3 * (attempt + 1))
    raise SystemExit(f"all models failed, last error: {last}")


def show(model: str, response) -> None:
    print(f"\n{response.text}\n")
    meta = response.candidates[0].grounding_metadata
    chunks = (meta.grounding_chunks if meta else None) or []
    print(f"--- model: {model} | retrieved chunks: {len(chunks)}")
    for chunk in chunks:
        context = chunk.retrieved_context
        print(f"    source: {context.title}")
    urls = ARTICLE_URL_LINE.findall(response.text or "")
    print(f"--- 'Article URL:' lines in the answer: {len(urls)} (the prompt asks for up to 3)\n")


def main() -> int:
    load_dotenv()
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    store = FileSearchStore.open(client, os.environ.get("GEMINI_FILE_SEARCH_STORE", DEFAULT_STORE_NAME))
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    if len(sys.argv) > 1:
        show(*ask(client, store.name, " ".join(sys.argv[1:]), model))
        return 0
    while True:
        try:
            question = input("you> ").strip()
        except EOFError:
            return 0
        if not question:
            return 0
        show(*ask(client, store.name, question, model))


if __name__ == "__main__":
    sys.exit(main())
