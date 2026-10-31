# Code conventions and the reasons behind them

Written so each choice can be explained later. "Why" is the point of this file; the rules themselves are small.

## 1. Working principle
- **Core flow first, optimise last** (Rule 0 in `CLAUDE.md`). The task is graded on a rubric (scrape 25, vector-store upload 20,
  daily job 15, code + README 10, tests +5) and the pass bar equals the sum of the required areas, so every area must work
  before any area is polished. *Why:* in an 8-hour build something will be missing; a complete rough flow beats one polished corner.
- When a case is complex: **guard it** (raise, skip, log) instead of solving it, and write it in `backlog.md`.

## 2. Layout: one job per module
| Module | Responsibility | Kind |
|---|---|---|
| `helpbot/zendesk.py` | fetch articles (pagination, retries) | I/O |
| `helpbot/markdown.py` | HTML -> Markdown, file format | pure |
| `helpbot/scrape.py` | write files, pick newest N, drop stale files | file I/O |
| `helpbot/chunking.py` | chunk settings + chunk-count estimate | pure |
| `helpbot/sync.py` | hash + delta planning (added/updated/skipped/...) | pure |
| `helpbot/store.py` | **the only module that talks to Gemini** | I/O |
| `helpbot/pipeline.py` | orchestration: delta -> parallel upload -> deletes -> summary | orchestration |
| `main.py` | env config, logging setup, exit code | entry point |
*Why:* pure logic (the part that can be wrong) is testable offline and fast; swapping the vector store later touches `store.py` only.

## 3. Python style
- Python 3.12, type hints on public functions, `dataclass(frozen=True)` for values, no speculative abstractions or base classes
  (`Store` is a `Protocol` only because tests substitute it). Comments say *why*, not what. Lines <= ~120 chars.
- Standard `logging`, never `print` inside `helpbot/` (scripts may print: they are CLIs). *Why:* the job's log is a deliverable.

## 4. Errors, retries, exit codes
- **Systemic problem -> fail the whole job loudly:** missing key (exit 2), empty fetch (`write_articles` raises), mass deletion
  (> 50% of the store, refused and reported as a problem -> exit 1). *Why:* a broken fetch must never look like "everything was deleted".
- **Per-item problem -> keep going:** one failed upload is logged with traceback, counted in `failed=`, the others continue,
  exit code 1 at the end. *Why:* one bad article must not block 400 good ones; stateless sync retries it next run.
- **Retries only for transient errors:** 5xx and 429, exponential backoff 2/4/8/16 s (Gemini), `urllib3.Retry` (Zendesk, `Retry-After`
  capped at 60 s). 4xx is never retried. *Why:* observed real 503 "high demand"; an uncapped `Retry-After` could hang a cron run.
- **Order of operations for updates:** upload the new version, then delete the old. A crash leaves a duplicate that the next run
  removes (`plan_delta` -> `duplicates`). *Why:* never leave an article without a searchable document.

## 5. Configuration
- Environment variables only, read in `main.py` (and dev scripts), every one listed in `.env.sample` (a test enforces this).
  No config files, no CLI flags in the job. *Why:* the job runs in Docker/cron where env vars are the standard injection point.
- Secrets never in the repo or image: `.env` is git/docker-ignored; the key is passed at `docker run`.

## 6. Markdown output (what the converter guarantees)
File = `# Title`, blank, `Article URL: <html_url>`, blank, body. Name = `<id>-<slug>.md`.
- `Article URL:` is a literal line because the system prompt tells the bot to cite such lines. The id prefix keeps names unique and stable if a title changes.
- No timestamps in the file: the content hash changes only when the content changes (the converter must be deterministic; checked
  by scraping twice and diffing).
- Kept: headings, lists (incl. `<ol start>`), code blocks, links exactly as authored (absolute, relative, `#anchors`), images, tables.
- Removed/normalised, each because the real corpus showed the problem: editor noise (`style`, `data-*`, empty anchors, empty
  `p/li/headings/links`); `span` unwrapped (spaces survive); whitespace-only `<strong>` -> a space; zero-width and nbsp chars;
  tables without `<th>` (188 files) -> first row becomes header, one-column callout tables -> blockquote; images inside table cells
  kept; iframes -> a link; inline base64 images dropped (125 KB of noise that also broke the upload).
- Not a goal: pixel-perfect HTML. Source quirks (a missing space in the original HTML) are kept as they are.

## 7. Delta sync and state
- State lives **in the store**: each document carries `article_id` and `content_hash` metadata; each run lists the store and compares.
  *Why:* cron containers have no persistent disk; this needs no database, file or secret besides the API key.
- Hash = SHA-256 of the final Markdown. `ARTICLE_LIMIT=N` (newest N by `updated_at`) is a partial mode and **never deletes**.
- Known limit: changing chunk settings alone does not change the hash (see backlog B2).

## 7b. Scope of the job
- The job syncs the articles listed in `config/article_ids.txt` (40 ids; the job writes them to the committed `articles/` folder, which a
  test keeps in step with the list; includes the YouTube article). *Why:* it is the flow a reviewer will run and read; small, fast, within free-tier limits.
- The job fetches the Help Center listing (a handful of paginated requests) and keeps only the listed ids; there is no "all articles" mode.
- The list is the truth: documents of articles that left the list are deleted (still behind the 50% guard); an id that no longer
  exists on the site is only a warning. `ARTICLE_LIMIT=N` (newest N) is a partial mode and never deletes.

## 8. Chunking
400 tokens per chunk, 50 overlap (~12%). *Why:* articles average ~1.4k tokens and are step-by-step procedures; ~400 tokens keeps a few
steps together, the overlap protects sentences cut at a boundary. The API chunks server-side and does not report counts, so the
logged `chunks_estimated` uses `chars / 4`. Values are constants in `chunking.py`, easy to tune.

## 8b. Model choice
`scripts/chat.py` uses `gemini-3.5-flash` by default. *Why:* measured, not assumed: the cheaper lite model ignores "Cite up to 3 `Article URL:` lines"
(0/4 answers), `gemini-3.5-flash` follows it (4/4). Document layout did not matter. Model names drift (`gemini-2.5-*` already return 404), so
the script has fallbacks and a `GEMINI_MODEL` override.

## 9. Tests
- Offline, fast, no real keys. Layout follows the rubric: `tests/scrape_quality`, `tests/vector_upload`, `tests/daily_job`, `tests/repo_hygiene`.
- Shared fakes live in `tests/support.py` (`FakeStore`, `run_main`). Real-API checks are scripts, not tests: `scripts/demo_delta.py`,
  `scripts/verify_articles.py`, `scripts/chat.py`. *Why:* Gemini has rate limits and a key is required; pytest must be runnable by a reviewer.
- Corpus tests use the **40 committed articles** only (Gemini has rate limits).
- Every real bug found gets a test (whitespace glue, `<ol start>`, base64 image, empty fetch, unsafe delete).

## 10. Git
Conventional Commits (`type(scope): subject`), one commit per finished step, the user is the only author, never `git add -A`, never push from tooling.
