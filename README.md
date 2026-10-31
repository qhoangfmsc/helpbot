# helpbot

Support-bot knowledge pipeline: scrape 40 Help Center articles, convert them to clean Markdown, load them into a Gemini File
Search store through the API, keep the store in sync with a daily job (only changes are uploaded), and chat with the result.

## Quick start: run locally in 5 minutes

You need Python 3.11+ and a free Gemini API key (https://aistudio.google.com/apikey). The key is the only secret.

```bash
git clone <this repo> && cd helpbot
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.sample .env          # then open .env (NOT .env.sample) and put your key after GEMINI_API_KEY=
python scripts/sync_docs.py  # loads the 40 articles into the store: first run ~1-2 min (added=40), again: skipped=40
python scripts/check_store.py                               # statistics + the 40 articles (id, title, link) -> "OK: the store matches articles/."
python scripts/chat.py "How do I add a YouTube video?"      # answer + "Article URL: ..." (5-25 s)
pytest -q                    # offline tests, grouped by grading area under tests/
```
Docker: `docker build -t helpbot . && docker run --rm -e GEMINI_API_KEY=<your key> helpbot` (one run, exit 0).
Everything else (store name, article list, timeouts, chat model) is in `config/settings.toml`; exit codes: 0 ok, 1 some uploads
failed, 2 config/key problem, 3 API/network problem (each prints a specific message). The free tier allows ~20 chat requests per model per day.

## What each script does

| Command | What it does |
|---|---|
| `python scripts/sync_docs.py` | scrape -> Markdown -> upload only new/changed articles (same job as the daily workflow) |
| `python scripts/check_store.py [--brief]` | read-only report: store statistics, local statistics, and per article its id, status, title, link, size, ~chunks and hash (`--brief` = statistics only) |
| `python scripts/chat.py ["question"]` | ask the bot (verbatim system prompt + File Search); no question = interactive |

## How it works

1. **Scrape** (`helpbot/zendesk.py`): public Help Center API; only the ids in `config/article_ids.txt` are kept.
2. **Markdown** (`helpbot/markdown.py`): headings, lists, code blocks, tables, images and links are kept, editor noise removed.
   Files in `articles/` are `<id>-<slug>.md`, starting with `# Title` and `Article URL: <url>`.
3. **Delta** (`helpbot/sync.py`): the SHA-256 of each file is stored as document metadata in the store; each run compares it with the
   fresh scrape: *added*, *updated* (new version uploaded, then the old deleted) or *skipped*. No database or state file.
4. **Chunking** (`helpbot/chunking.py`): 400 tokens per chunk, 50 overlap (~12%). Articles average ~1.4k tokens, so a few steps of a
   procedure stay together and a cut sentence is still retrievable. The API chunks server-side and reports no counts, so
   `chunks_estimated` in the log is a local estimate.

## Evidence

- **Daily job logs**: `.github/workflows/daily-sync.yml` builds the Docker image and runs the job once a day (21:00 UTC = 04:00 Vietnam time, outside business hours; the key is a repository secret).
  Last run, started manually: [run #3, Success, 28 s, commit a80c530](https://github.com/qhoangfmsc/helpbot/actions/runs/41233639313) (GitHub asks for a
  sign-in to open the raw log; the status and the `run-log` artifact are listed on the public run page). Its last log line:
  `2026-10-31 19:19:30,826 INFO done added=0 updated=0 skipped=40 deleted=0 failed=0 files=0 chunks_estimated=0 store_documents=40`
- **Assistant answer (screenshot)** to "How do I add a YouTube video?" (`python scripts/chat.py`): 5 steps, one `Article URL:` line, 3 retrieved chunks from the right
  article. The first attempt got an HTTP 503 from Gemini and the script retried by itself. The prompt is `prompts/system_prompt.txt` (verbatim).

  ![Terminal: answer to "How do I add a YouTube video?" with the Article URL line](docs/img/chat-youtube.png)
- **Tests**: `tests/scrape_quality`, `tests/vector_upload`, `tests/daily_job`, `tests/repo_hygiene` (green check from `tests.yml`).
- **Scrape fidelity**: `python scripts/verify_articles.py` re-fetches the 40 articles and compares them with the live site.

## Limits and what was cut

If the store ever holds many documents that are no longer in `config/article_ids.txt`, the job refuses to delete them (exit 1); after
shrinking the list on purpose run once `python scripts/sync_docs.py --allow-mass-delete`. AI Studio's chat has no File Search tool, so the
assistant is configured by API (`scripts/chat.py`). No chat UI, no Postgres/Redis (state lives in the store). Reasons and pros/cons of
every skipped item: `docs/backlog.md`; code conventions: `docs/conventions.md`.
