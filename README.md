# helpbot

Support-bot knowledge pipeline: scrape 40 Help Center articles, convert them to clean Markdown, load them into a Gemini File
Search store through the API, keep the store in sync with a daily job (only the delta is uploaded), and chat with the result.

| Script | What it does |
|---|---|
| `python scripts/sync_docs.py` | scrape -> Markdown -> upload only new/changed articles (same job as the daily workflow) |
| `python scripts/check_store.py [--list]` | read-only re-check: does the store hold exactly the files in `articles/`? |
| `python scripts/chat.py "question"` | ask the bot (verbatim system prompt + File Search); no argument = interactive |

## Quick start: run locally in 5 minutes

Needs Python 3.12 and a free Gemini API key (aistudio.google.com/apikey). Docker is optional.

```bash
git clone <this repo> && cd helpbot
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.sample .env                    # then put your key in GEMINI_API_KEY=
python scripts/sync_docs.py            # first run (~1-2 min): ... added=40 ...; run it again: ... skipped=40 ...
python scripts/check_store.py          # -> "OK: the store matches articles/."
python scripts/chat.py "How do I add a YouTube video?"   # answer + "Article URL: ..." (5-25 s: the model thinks)
pytest -q                              # offline tests, grouped by grading area under tests/
docker build -t helpbot . && docker run --rm -e GEMINI_API_KEY helpbot    # one run, exit 0
```
Last line of a sync: `added=… updated=… skipped=… deleted=… failed=… files=… chunks_estimated=… store_documents=…`.
The store (`helpbot-docs`) is created on the first run. The free tier allows only ~20 chat requests per model per day; when it is used up (or on a
timeout, a bad key, no network...) the scripts print a specific message. Exit codes: 0 ok, 1 some uploads failed, 2 config/key problem, 3 API/network problem.

## How it works

1. **Scrape** (`helpbot/zendesk.py`): public Help Center API, paginated and retried; only the ids in `config/article_ids.txt` are kept.
2. **Markdown** (`helpbot/markdown.py`): headings, lists, code blocks, tables, images and links are kept, editor noise is removed.
   Files in `articles/` are `<id>-<slug>.md`, starting with `# Title` and `Article URL: <url>`.
3. **Delta** (`helpbot/sync.py`): the SHA-256 of each file is stored as document metadata in the store; each run compares it with the
   fresh scrape: *added*, *updated* (new version uploaded, then the old deleted) or *skipped*. No database or state file.
4. **Chunking** (`helpbot/chunking.py`): 400 tokens per chunk, 50 overlap (~12%). Articles average ~1.4k tokens, so a few steps of a
   procedure stay together and a cut sentence is still retrievable. The API chunks server-side and reports no counts, so
   `chunks_estimated` is a local estimate.

## Evidence

- **Daily job logs** (`.github/workflows/daily-sync.yml`, once a day, Docker, key in a repository secret): _TODO: link to the Actions run_.
- **Assistant answer** to "How do I add a YouTube video?" with cited URLs: _TODO: screenshot_. The prompt is `prompts/system_prompt.txt` (verbatim).
- **Tests**: `tests/scrape_quality`, `tests/vector_upload`, `tests/daily_job`, `tests/repo_hygiene` (green check from `tests.yml`).
- **Scrape fidelity**: `python scripts/verify_articles.py` re-fetches the 40 articles and compares them with the live site.

## Limits and what was cut

AI Studio's chat has no File Search tool, so the assistant is configured by API (`scripts/chat.py`). No chat UI, no Postgres/Redis (state
lives in the store). Reasons and pros/cons of every skipped item: `docs/backlog.md`; code conventions: `docs/conventions.md`.
