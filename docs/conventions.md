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

## 4. Errors, timeouts, retries, exit codes
Rule: **nothing may hang and nothing may fail silently**. All kinds of failure are classified in one place (`helpbot/problems.py`, `classify` + `explain`) and each
has its own message that says what happened and what to do. *Why:* the daily job and the scripts run unattended; a log line like "429" is not actionable.

| Case | Message says | Handling |
|---|---|---|
| Gemini daily free quota used up (429 `PerDay`) | quota used up, resets daily; wait / other model / other key | not retried; the run stops early (every upload would fail the same way); `chat.py` goes to the next model |
| Per-minute rate limit (429) | wait a minute or lower `upload_workers` | retried with backoff 2/4/8/16 s |
| Bad/expired key (400 "API key", 401, 403) | key rejected, check `GEMINI_API_KEY` | not retried; run stops; exit 2 in the scripts |
| Model/store not found (404) | model may be retired, check `chat_model`/`store_name` | not retried; `chat.py` tries the next model |
| Gemini 5xx | overloaded/down, run again later | retried, then reported |
| Request timeout (no answer within `request_timeout_seconds`, default 90) | timed out, check network / raise the timeout | retried a bounded number of times; one file failing does not stop the others |
| Indexing slower than 300 s | did not finish indexing; next run retries | file counted as failed |
| Network down / DNS | cannot reach the server | retried, then reported |
| Help Center timeout / 404 / 5xx after retries | names `help_center_url` for 404 | job aborts before touching the store, exit 3 |
| Bad input (missing id list, no articles, empty fetch) | the exact problem | exit 2, store untouched |
| Anything unknown | `Unexpected <Type>: ...` + traceback | exit 3 |

- **Hard limits against hanging:** every HTTP request has a timeout (the SDK default is *no timeout*, so `make_client` always sets one); the whole job stops starting
  uploads after `job_max_minutes` (default 30, below the workflow's 45-minute cut-off); one `chat.py` question gives up after 150 s; retries are always bounded.
- **Exit codes:** 0 ok | 1 some uploads failed (the next run retries them) | 2 configuration/input problem | 3 API or network problem.
- **Per-item problem -> keep going:** one failed upload is logged with its reason, counted in `failed=`, the others continue.
- **Systemic problem -> fail loudly:** empty fetch, mass deletion (> 50% of the store) is refused and reported as a problem (exit 1). The refusal names the one-off override
  `python scripts/sync_docs.py --allow-mass-delete`, to be run by a human on purpose; it is never set in the workflow and never applies to partial (`--limit`) runs.
- **Order of operations for updates:** upload the new version, then delete the old; a crash leaves a duplicate that the next run removes.

## 5. Configuration
- **One secret, one environment variable:** `GEMINI_API_KEY` (in `.env`, git-ignored; `.env.sample` is the empty template the task asks for). A hygiene test fails if code reads any other
  variable, if `.env.sample` holds anything but the empty key, or if a key-shaped value appears in any file that would be committed. *Why:* a leaked key must be impossible to commit by accident.
- **Everything else is `config/settings.toml`** (`helpbot/settings.py`): store name, article list file, articles folder, Help Center URL, upload workers, timeouts, chat model and fallbacks. It is
  validated: a misspelt name or a value of the wrong type is an error (exit 2), never silently ignored. TOML because Python reads it with the standard library (`tomllib`) and it allows comments.
- **One-off actions are command-line flags**, not settings: `--allow-mass-delete`, `--limit N`. *Why:* a dangerous switch must not be left on in a file by mistake.
- Secrets never in the repo or image: the key is passed at `docker run` or comes from a repository secret.

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
- Hash = SHA-256 of the final Markdown. `--limit N` (newest N of the selection by `updated_at`) is a partial mode and **never deletes**.
- Known limit: changing chunk settings alone does not change the hash (see backlog B2).

## 7b. Scope of the job
- The job syncs the **union** of two sources: the ids in `config/article_ids.txt` (pinned, always kept; includes the YouTube article that
  answers the sample question and is not among the newest) and the `newest_articles` (default 40) most recently updated articles of the site.
  An article in both counts once. *Why:* the spec asks the daily job to detect new/updated articles; a fixed list can never see a new one,
  while "newest only" could drop the YouTube article. One job for local and cloud so what the reviewer runs is what the cron runs.
- Measured on the live site: 40 pinned + 40 newest overlap on 6 articles = 74. `newest_articles = 0` goes back to the pinned list only.
- Deletion: a document is deleted only when its article is **gone from the site** (`site_ids` from the same fetch), still behind the 50% guard.
  Articles that merely fell out of the newest window stay, so the store grows slowly (backlog B25). `--limit N` is a partial mode and never deletes.
- The job fetches the Help Center listing (a handful of paginated requests); there is no "all articles" mode.

## 8. Chunking
400 tokens per chunk, 50 overlap (~12%). *Why:* articles average ~1.4k tokens and are step-by-step procedures; ~400 tokens keeps a few
steps together, the overlap protects sentences cut at a boundary. The API chunks server-side and does not report counts, so the
logged `chunks_estimated` uses `chars / 4`. Values are constants in `chunking.py`, easy to tune.

## 8b. Model choice
`scripts/chat.py` uses `gemini-3.5-flash` by default. *Why:* measured, not assumed: the cheaper lite model ignores "Cite up to 3 `Article URL:` lines"
(0/4 answers), `gemini-3.5-flash` follows it (4/4). Document layout did not matter. Model names drift (`gemini-2.5-*` already return 404), so
the script has fallbacks and the model names live in `config/settings.toml`.

## 8c. Scripts
Three user-facing scripts, each a thin entry point over the package (one implementation, no copies): `sync_docs.py` runs `main.main()` (same job as the
daily workflow), `check_store.py` is read-only (reuses `plan_delta` to compare the store with `articles/`; prints statistics and one entry per article so a mismatch can be debugged), `chat.py` asks the bot. Each one finds the repo
root and `.env` from its own location, so it works from any directory. Dev tools: `check_markdown.py`, `verify_articles.py`, `demo_delta.py`.
`chat.py` prints a status line and the answer time, because a request takes 5-25 s (see backlog B23).

## 9. Tests
- Offline, fast, no real keys. Layout follows the rubric: `tests/scrape_quality`, `tests/vector_upload`, `tests/daily_job`, `tests/repo_hygiene`.
- Shared fakes live in `tests/support.py` (`FakeStore`, `run_main`). Real-API checks are scripts, not tests: `scripts/demo_delta.py`,
  `scripts/verify_articles.py`, `scripts/chat.py`. *Why:* Gemini has rate limits and a key is required; pytest must be runnable by a reviewer.
- Corpus tests use the committed `articles/` folder (the pinned articles plus the newest ones the job fetched, 74 at the time of writing); no network.
- Every real bug found gets a test (whitespace glue, `<ol start>`, base64 image, empty fetch, unsafe delete).

## 10. Git
Conventional Commits (`type(scope): subject`), one commit per finished step, the user is the only author, never `git add -A`, never push from tooling.

## 11. Key choices: pros and cons (for the interview)
| Choice | Pros | Cons / what it costs |
|---|---|---|
| Gemini File Search instead of OpenAI vector store | free tier, chunking/embedding done server-side, one SDK | 20 generate requests per model per day; no chunk counts; AI Studio chat has no File Search tool (assistant is driven by API) |
| Public Zendesk API + BeautifulSoup/markdownify with data-driven cleanups | stable fields (`updated_at`, `body`), no browser, 5 requests per scrape; every cleanup came from a real defect and has a test | custom code to maintain; some source quirks kept on purpose (glued words, absolute links) |
| Stateless delta: SHA-256 in document metadata | no DB, no state file, works on an ephemeral cron container | one list call per run; chunk settings are not part of the hash (backlog B2) |
| Pinned ids + newest N in one job | catches new articles and keeps the YouTube article; same code local and in the cron | store grows slowly (B25); 74 articles instead of a tidy 40 |
| Delete only articles gone from the site, behind a 50% guard | a broken fetch cannot wipe the store | a stale article that is still on the site is never removed |
| GitHub Actions as the scheduler (Docker image built in the run) | free, logs and artifact link, secret store, manual button | not a classic hosting platform; schedule may start late (observed ~3 h); raw logs need sign-in |
| Verbatim system prompt, no answer guardrails | exactly what the spec asks; honest evaluation | the bot is not perfect (sometimes no literal `Article URL:` line, depends on the model) |
| One secret in `.env`, everything else in `config/settings.toml` | a key cannot be committed by mistake (hygiene tests); settings validated | two places to look |
| Offline tests with fakes, grouped by rubric area | fast, runnable by a reviewer without a key | real-API behaviour is checked by scripts, not tests |
