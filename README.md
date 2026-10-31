# helpbot

Support-bot knowledge pipeline: scrape a Zendesk Help Center, convert every article to clean Markdown, load it into a
Gemini File Search store through the API, and keep the store in sync with a daily job that uploads only the delta.

## How it works

1. **Scrape** (`helpbot/zendesk.py`): published articles via the public Help Center API (paginated, retried). The job keeps the
   40 articles listed in `config/article_ids.txt` in sync (the same set as the committed `articles/` folder, includes the YouTube one);
   To change the scope edit that file (one id per line); articles that leave the list are deleted from the store.
2. **Markdown** (`helpbot/markdown.py`): HTML is cleaned and converted; headings, lists, code blocks, tables, images and links
   are kept, editor noise removed. Files are `<id>-<slug>.md`, starting with `# Title` and `Article URL: <url>`.
3. **Delta** (`helpbot/sync.py`): the SHA-256 of each file is stored as document metadata (`article_id`, `content_hash`) in the
   store. Each run lists the store and compares: *added*, *updated* (new version uploaded, then the old one deleted), *skipped*
   (same hash). Articles removed from the site are deleted (refused if > 50% of the store). No database or state file.
4. **Chunking** (`helpbot/chunking.py`): 400-token chunks, 50 tokens overlap (~12%): articles average ~1.4k tokens, so a few steps of
   a procedure stay together and cut sentences stay retrievable. The API chunks server-side and does not report counts, so
   the logged `chunks_estimated` is a local estimate.

## Run locally

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.sample .env                 # set GEMINI_API_KEY (free key from aistudio.google.com/apikey)
python main.py                      # sync the 40 listed articles (ARTICLE_LIMIT=N: only the N newest of them)
python scripts/chat.py "How do I add a YouTube video?"    # ask the bot (gemini-3.5-flash + File Search)
pytest -q                           # offline tests, organised by grading area under tests/
```

Docker: `docker build -t helpbot . && docker run --rm -e GEMINI_API_KEY helpbot` runs the job once and exits 0 on success.
Last log line: `added=… updated=… skipped=… deleted=… failed=… files=… chunks_estimated=… store_documents=…`.

## Daily job

`.github/workflows/daily-sync.yml` builds the image and runs it once a day (03:17 UTC); `GEMINI_API_KEY` is a repository secret.
Logs of the last run (counts shown on the run page, full log as artifact): _TODO: link to the Actions run_.

## Assistant answer

System prompt: `prompts/system_prompt.txt` (verbatim). _TODO: screenshot of "How do I add a YouTube video?" with cited URLs._

## Tests and docs

`tests/scrape_quality`, `tests/vector_upload`, `tests/daily_job`, `tests/repo_hygiene` (no network). `articles/` holds the 40 scraped
articles (the job rewrites them on every run; unchanged articles stay byte-identical). Code conventions and reasons: `docs/conventions.md`; skipped items with pros/cons: `docs/backlog.md`.

## What was cut

Chat UI (Next.js/NestJS), Postgres/Redis (state lives in the store), exact chunk counts (not exposed), tuning the bot to print
literal `Article URL:` lines (backlog B1).
