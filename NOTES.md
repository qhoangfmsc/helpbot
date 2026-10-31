# Working notes

> Historical log. Entries before step 3 mention a 417-article corpus that was only used for testing; since D24 the project covers exactly the 40 articles in `config/article_ids.txt`.

Append-only log of decisions, confirmed facts and what was done per step. Newest step last.

## Decisions

| # | Decision | Why |
|---|----------|-----|
| D1 | Repo `helpbot` = Part 1 (coding) only; planning lives elsewhere | User choice; keeps repo focused and non-searchable by the vendor name |
| D2 | ~~OpenAI~~ -> **Gemini (AI Studio + File Search)** as AI platform | Changed 2026-10-31: user will not fund an OpenAI account; Gemini has a free tier and the spec allows it. Spike must confirm File Search works end to end |
| D3 | "Lean Core": Python at repo root, no Next.js/NestJS/Postgres/Redis for now | Pass bar equals sum of required areas; UI is not graded |
| D4 | Stateless sync: `article_id` + `content_hash` as File Search document metadata | Cron filesystems are ephemeral; avoids a DB. **Needs API verification** |
| D5 | Package `helpbot/` at repo root (not `src/`) | `python main.py` and Docker work with no path tricks |
| D6 | Scrape ALL published articles (417), not just 30 | Ensures the YouTube answer is covered; Zendesk API is cheap (5 requests); spec says >= 30 |
| D7 | Filename `<article_id>-<title-slug>.md` | Stable id => stable mapping even if the title changes |
| D8 | File layout: `# Title`, blank, `Article URL: <html_url>`, blank, body | The bot must cite literal `Article URL:` lines; no timestamps in the file so the content hash only changes when content changes |
| D9 | Links are kept as authored (in-page anchors and absolute help-center links; no rewriting) | Spec: "preserve relative links" |
| D10 | Single-column tables (TIP/NOTE boxes) -> blockquote; table without `<th>` -> first row becomes header; blank rows dropped; real iframes -> link | Zendesk has no `<th>`, plain conversion produced empty header rows |
| D11 | Never commit/push; user reviews and commits (proposals only) | User instruction |
| D12 | Commit messages follow Conventional Commits | User instruction |
| D14 | Scrape all 417 but cap what is uploaded (`MAX_ARTICLES`); the cap is decided after the spike shows free-tier limits | User choice; scraping is cheap, upload is where limits bite |
| D15 | Commit a 40-article sample (`samples/articles/`, incl. all 7 YouTube articles) built by `scripts/make_samples.py`; `data/` is git-ignored | User choice; reviewers see Markdown quality, repo stays small |
| D18 | In-page `#anchor` links stay exactly as authored in the source (no rewrite/removal) | User choice: favour the spec's literal "preserve links" and the primary source over own edits |
| D19 | Use the cheapest Gemini model that supports File Search for testing (flash-lite class) | User instruction: minimise cost/tokens |
| D20 | One commit per finished step/feature, Conventional Commits; commit only after the user's request and a second confirmation | User instruction (2026-10-31) |
| D21 | Chunking 400 tokens / 50 overlap; chunk count is a local estimate (`chars/4`), logged as `chunks_estimated` | API does not expose chunk counts; settings are tunable constants in `helpbot/chunking.py` |
| D22 | Delete orphans (articles gone from the site) unless that would remove > 50% of the store or `MAX_ARTICLES` is set | A broken/partial fetch must not wipe the knowledge base |
| D23 | New version is uploaded before the old one is deleted; a crash leaves a duplicate that the next run removes | Never leave an article without a document |
| D24 | Job scope = the 40 articles in `config/article_ids.txt` (same as `samples/articles`, includes YouTube); `ARTICLE_IDS_FILE=` empty = all | User instruction: match the flow reviewers actually run; 417 was for testing |
| D25 | Commits made on explicit request after showing the list; first batch = 3 commits (0d276a0, 599b31d, 94a046e) | D20/D17 |
| D26 | `scripts/chat.py` default model = `gemini-3.5-flash` (follows the `Article URL:` instruction, lite does not); document layout unchanged | measured 4/4 vs 0/4 |
| D27 | One folder `articles/` (committed job output) replaces `data/` + `samples/`; no "all articles" mode | User instruction: only the 40 articles matter |
| D28 | No answer guardrails (eval script / retry / topic gate): the task only needs the sample question answered with cited URLs; keep the assistant = verbatim prompt + File Search | User instruction: avoid workaround-style additions |
| D29 | User-facing scripts: sync_docs, check_store, chat; README is a 5-minute user guide | User instruction |
| D17 | Commits need an explicit request AND a second confirmation after I show files + messages | User instruction (2026-10-31) |
| D13 | Plan each step before doing it; settle open items from the previous step first | User instruction |

## Confirmed facts

- Zendesk public endpoint `GET https://support.optisigns.com/api/v2/help_center/en-us/articles.json?per_page=100` works without auth (2026-10-31). 417 articles over 5 pages, `next_page` link, rate limit header `x-rate-limit: 400`. Fields used: `id`, `title`, `html_url`, `updated_at`, `body` (HTML), `draft`. Bodies contain no nav/ads.
- Body HTML uses p/li/a/img/table/h2-h4/pre/code/iframe; links are mostly absolute help-center URLs plus `#anchors`.
- Python 3.12.13 at `/opt/homebrew/bin/python3.12`; Docker 29.3.1 available; no poppler (PDF text via PDFKit).

## UNVERIFIED (resolve with `api-docs-check` before the upload step)

- OpenAI Assistants API sunset vs Responses API + `file_search`; what "assistant" means in the Playground now.
- Vector store file `attributes` support / filter on list.
- Chunking strategy params and whether chunk counts are exposed (fallback: estimate locally and say so).

## Work log

### Step 0 - project setup (2026-10-31)
- Removed `docs/` and `brainstorm.txt` (spec kept outside the repo; path in `CLAUDE.local.md`, git-ignored).
- Wrote `CLAUDE.md` (rules), `CLAUDE.local.md` (spec path + checklist), `.gitignore`, skills: `spec-recheck`, `api-docs-check`, `verify-submission`.
- Memory notes saved for spec location, scope decisions, never-commit.

### Step 1 - scrape -> Markdown (2026-10-31)
- Built `helpbot/zendesk.py` (paginated fetch, skips drafts/empty), `helpbot/markdown.py` (clean + convert), `helpbot/scrape.py` (write files), `main.py` (scrape stage only for now).
- Iterated on real output: empty table headers (188 files) -> fixed by table normalisation; images inside table cells were dropped by markdownify -> unwrapped `figure/p` and enabled `keep_inline_images_in`.
- Added `scripts/check_markdown.py` + skill `md-quality-check`; 10 unit tests (`tests/`).
- Evidence: 417 files written; `check_markdown.py` -> 417/417 ok; `pytest` -> 10 passed; `python main.py` exit 0.
- Known legit oddities: HTML shown as text/code in embed how-tos; comparison tables with empty top-left cell.
- Not done yet: upload to vector store, assistant + screenshot, delta sync, Docker, deploy, README.

### Review of step 1 (2026-10-31) - user questions
- Link census over the 417 files: 4381 absolute help-center links, 779 other absolute, 1247 in-page `#anchors`, 5 path-relative (`/attachments/token/...`, in 2 files). All are kept as authored, so "preserve relative links" holds literally. Absolute links are better for citations, so no rewriting.
- 417 = the API `count` for en-us; 0 drafts/empty bodies skipped, so this is the full published en-us corpus (~2.4 MB, ~0.6M tokens). The spec says >= 30, so 417 is allowed but not required.
- Provider concern: OpenAI API reportedly gives no free credits and bills file_search per call (third-party sources, not an official page => UNVERIFIED). Assistants API reportedly shut down 2026-08-26 (third-party sources) => the Playground "Assistant" is gone; Responses API + file_search is the path. Gemini AI Studio has a free tier; File Search reportedly 1 GB free storage, indexing $0.15/1M tokens on paid, query embeddings free (third-party sources, UNVERIFIED). Decision on provider pending (D2 may change).

### Step 1b - decisions applied (2026-10-31)
- Provider switched to Gemini (D2); `.env.sample` now has `GEMINI_API_KEY`, `GEMINI_FILE_SEARCH_STORE`; `api-docs-check` open questions rewritten for Gemini.
- Added `scripts/make_samples.py` (deterministic: all YouTube + 6 code + 6 table + even spread) -> `samples/articles/` 40 files (292 KB), `check_markdown.py` 40/40 ok; `data/` added to `.gitignore`.
- Waiting on the user: create a Gemini API key and put it in `.env`; then the spike (step 2a) starts.

### Step 1c - commits (2026-10-31)
- Created 7 Conventional Commits on `main` for steps 0-1b, authored only by the repo owner (no co-author trailer); nothing pushed.
- Rule 9 relaxed: commit only when the user asks, never push, user is the sole author. D16: no `Co-Authored-By` / tool attribution lines in this repo.

### Step 1d - review fixes (2026-10-31)
- Bug: whitespace-only inline tags (`<span> </span>`, `<strong> </strong>`, `<strong>\xa0</strong>`) were dropped, gluing words (`**Hello****World**`, `[x](url)or`). Fix: unwrap `span`; replace whitespace-only emphasis tags with a single space; drop only empty `p`/`li`. Glued link-word files 28 -> 8; the rest are images adjacent to text in the source HTML. `**P****review**` is split bold in the source, renders fine.
- Added `retrying_session()` (5 retries, backoff 1s, 429/5xx, honours Retry-After) as the default session for Zendesk fetches.
- Tests: 10 -> 15. Re-scraped 417/417 ok; `samples/articles` rebuilt 40/40 ok.

### Step 2a - Gemini File Search spike (2026-10-31), done
- Confirmed live (SDK `google-genai` 2.34.0, free tier, no card): create store, `upload_to_file_search_store` with `custom_metadata` (`article_id`, `content_hash`) and `chunking_config` (white-space: `max_tokens_per_chunk`, `max_overlap_tokens`), `documents.list/get/delete`, store info `active_documents_count`, `size_bytes`, `embedding_model=models/gemini-embedding-001`. Metadata round-trips through `documents.list` => stateless sync (D4) works.
- Upload is async (operation); ~8 s per small file sequentially => 417 files ~ 1 h sequential. Consider thread pool and/or the `MAX_ARTICLES` cap.
- NOT exposed: chunk count (neither store nor document). Fallback: estimate locally from token counts and chunking params, and label it "estimated" in logs/README.
- Models: `gemini-2.5-*` return 404 for new users. `gemini-flash-latest`, `gemini-flash-lite-latest`, `gemini-3-flash-preview`, `gemini-3.5-flash` worked with File Search; `gemini-3.1-flash-lite*` returned intermittent 503 (high demand) => the query code needs retries.
- Query with `file_search` tool + the system prompt, model `gemini-3.5-flash-lite` (cheapest that worked): correct 5-bullet answer for "How do I add a YouTube video?" with a doc link. `grounding_metadata.grounding_chunks[].retrieved_context` gives `title` (our display_name) and chunk `text`.
- `metadata_filter='article_id = "..."'` works (only that document was retrieved).
- `documents.delete` needs `config={"force": True}` for non-empty documents (400 FAILED_PRECONDITION otherwise); `file_search_stores.delete(..., force=True)` works. Update = delete document + upload new one.
- Spike store deleted; no resources left in the account.
- Concern: the model cited the doc as a Markdown link, not as literal `Article URL:` lines; only 1 of 3 retrieved chunks contained the `Article URL:` header line. To test in step 2b with the verbatim prompt (idea: repeat the URL line per H2 section so each chunk carries it).
- UNVERIFIED: AI Studio UI using an API-created store (user must check in the UI after the real upload); rate limit under concurrent uploads.

### Pre-2b checks (2026-10-31)
- Determinism: two consecutive scrapes produced 0 differing files => content hash is stable, hash-based delta is safe (attachment-token links also stable).
- Corpus scan (417 files): 236 contain nbsp/zero-width chars (to normalise), 14 empty headings (to drop), 197 jump from H1 straight to H3 (cosmetic, kept), 822/3414 images have empty alt (kept), biggest file 134 KB, avg 5.7 KB (~1.4k tokens).
- AI Studio: no source found showing that a File Search store created via API can be selected in the AI Studio chat UI; one source says the AI Studio File Search demo needs a paid key (third-party, UNVERIFIED). Plan: user checks the UI; prepare a clarifying email to the recruiter.
- Elapsed time so far is roughly 1.5-1.7 h of the 8 h budget (estimated from file timestamps; not measured). Start recording per step.

### Roadmap (updated)
0 setup [done] - 1 scrape [done] - 1e core review (small) - 2a spike [done] - 2b pipeline: delta + upload + logging + chat script - 3 assistant in AI Studio + screenshot - 4 Docker - 5 deploy daily job + public logs link - 6 README, CI/tests visibility, verify-submission.

### Step 1e - core review and fact-check (2026-10-31)
- Fixes: `\xa0`/zero-width chars normalised (text nodes first, so empty wrappers are detected); empty headings and empty links dropped; image wrapped in `<strong>` inside a heading kept; title whitespace collapsed; `write_articles` refuses an empty fetch (a source outage must fail the job), removes stale generated files only (`<id>[-slug].md`), never other `.md`; Zendesk retry caps `Retry-After` at 60 s (`retry_after_max`); `<ol start="N">` kept (step numbers were restarting at 1 - found by the live fact-check).
- /code-review (medium) findings triaged: 3 valid fixed (zero-width in empty wrappers, unsafe stale deletion, uncapped Retry-After); normalising chars inside code is intentional (documented); 3 dismissed (speculative or already covered; the CLAUDE.md "contradiction" was stale/incorrect).
- `scripts/verify_samples.py` (network): re-fetches every article from the live API and the public page, then checks title, `Article URL`, byte equality with a fresh conversion, word multiset (source vs Markdown, independent of the converter), link targets, images, code blocks, headings. First run 20/40 flagged: all verifier artefacts except one real bug (`<ol start>`); after fixing both, **40/40 samples verified against the live site** (public pages answer 200, same title, same body words, unchanged since scraping).
- Verifier semantics learned: `<ol>` item numbers are implied text; iframes appear as links; callout headings live in blockquotes; link-text==URL is an autolink `<url>`; link targets inside code blocks stay as plain text.
- Tests 15 -> 27. Corpus 417/417 lint ok (now also flags empty headings and invisible chars).

### Step 1f/2b - full-corpus fact-check, then upload pipeline (2026-10-31)
- Live fact-check of all 417 articles: 408 ok; the 9 flagged are verifier artefacts or source quirks (words split across inline tags in the verifier, `at<a>` / `</a>We` glued in the source HTML, an example `mailto:` with `<ip>`); no converter bug left. Only 2 of the 4 "glued" cases were inspected individually, the rest follow the same pattern.
- Built: `prompts/system_prompt.txt` (verbatim from the PDF, bullet U+2022 and straight quotes; test), `helpbot/sync.py` (pure delta), `helpbot/chunking.py`, `helpbot/store.py` (Gemini wrapper: find/create store, list docs with metadata, upload+poll, force delete, retries on 5xx/429), `helpbot/pipeline.py` (thread pool uploads, counters updated single-threaded, deletion guards), `main.py` wiring via env, `scripts/chat.py`.
- Bug caught in review of my own code: counters were mutated from worker threads; moved deletion of replaced docs after the pool.
- Tests 27 -> 56 (all offline). Real API checks on a throwaway store `helpbot-test` (MAX_ARTICLES=6, 4 workers): run1 added=6 in ~18 s; run2 skipped=6; after planting a doc with a wrong hash: updated=1 deleted=1; run4 skipped=6. This proves add/skip/update on the real API; orphan deletion is only covered by unit tests.
- Throughput: ~3 s/file effective with 4 workers (~8 s/file sequential) => 417 files ~ 20 min on the first run; daily runs only upload the delta.
- Finding for the tuning step: with the verbatim prompt the model cites with a Markdown link, not literal `Article URL:` lines (0 lines in the answer). Needs an experiment on document layout (e.g. repeat the `Article URL:` line per section) without touching the prompt.
- Full 417 upload into store `helpbot-docs` started in the background (log in scratchpad `full_run1.log`).
- README skeleton created (<= 1 page rule); daily job, screenshot and "what was cut" sections are TODO.

### Step 2b-2 - flow completed except cloud deploy (2026-10-31)
- Rule 0 added at the top of CLAUDE.md (core flow first, optimise last, note problems, simple guards for complex cases, record reasons).
- Docs: `docs/conventions.md` (conventions + reasons), `docs/backlog.md` (skipped/optimise items with pros/cons, problems found).
- Tests reorganised by rubric area: `tests/scrape_quality` (25), `tests/vector_upload` (20), `tests/daily_job` (15), `tests/repo_hygiene` (10); shared fakes in `tests/support.py`. 88 passed + 1 xfail (README TODO reminder). Corpus tests use the 40 samples only.
- `ARTICLE_LIMIT=N` (replaces MAX_ARTICLES): newest N by `updated_at`, never deletes. `run_job()` in pipeline.py; `main.py` is now only wiring.
- Full 417 upload: first run added=416 failed=1 (article 8899727608083 "QR Scan to Interact": a 125 KB inline base64 image made the upload fail with 400 "Upload has already been terminated"). Fix: drop `data:` images in the converter, linter + test; rerun: `added=1 skipped=416`, store=417 documents.
- Docker image built (280 MB); container run against the full store: exit 0, `skipped=417`, 9 clean log lines, key not in the log; no key -> exit 2.
- `scripts/demo_delta.py` on a throwaway store (real API, 5 scenarios, all OK): 30 newest -> same again (skipped 30) -> widened to 40 (added 10, skipped 30) -> new article (added 1, skipped 39) -> edited article (updated 1, skipped 39). Store deleted afterwards.
- Chat check on the full store: correct 5-bullet answer for the YouTube question from the right article, 3 chunks, but 0 literal `Article URL:` lines (backlog B1).
- Added `.github/workflows/daily-sync.yml` (once a day, Docker, secret key, log artifact + summary) and `tests.yml`; YAML validated, NOT yet run (needs the repo pushed to GitHub by the user, a secret and a first manual run).
- Open: AI Studio cannot attach a File Search store (screenshot of the Tools panel) -> email the recruiter; deploy target decision; screenshot; README TODOs.

### Step 3 - commits and 40-article scope (2026-10-31)
- Created the 3 approved commits (fix(scrape), feat(sync), ci); author only the user; working tree clean afterwards.
- Scope standardised to 40 articles: `config/article_ids.txt` (ids of `samples/articles`), `load_ids`/`select_ids` in `helpbot/scrape.py`, `main.py` reads `ARTICLE_IDS_FILE` (default that file; empty = all), Dockerfile copies `config/`. 10 new tests (98 passed + 1 xfail).
- Deleted the 417-document test store `helpbot-docs` (my own test resource; otherwise 377 orphans would trip the 50% deletion guard) and let the job recreate it: run1 `added=40 failed=0`, run2 `skipped=40`, container run `skipped=40` exit 0; chat answer for the YouTube question correct (3 chunks, right article, 0 literal `Article URL:` lines).
- GitHub Actions needs a *repository* secret (the workflow has no `environment:`), see README.

### Step 4 - verify-submission and B1 (2026-10-31)
- verify-submission local checks: no `.env` tracked; exact key value absent from HEAD and all history; no key-shaped strings; no company name in commit messages (17 tracked file names contain it only because scraped article slugs do); 98 tests pass; README 51 lines, 2 TODOs left (log link, screenshot). Remote `origin` = github.com/qhoangfmsc/helpbot, main pushed up to `94a046e`; local is 1 commit ahead plus this step's changes. `gh` is not installed here, so I could not read the Actions runs.
- B1 experiment (throwaway stores, 8 YouTube-related articles, temp 0): layouts V0/V1 (URL after each heading)/V2 (URL every ~1000 chars) all 0/6 literal `Article URL:` answers on `gemini-3.5-flash-lite`. Models on the unchanged layout: lite 0/4, `gemini-3.5-flash` 4/4, `gemini-3-flash-preview` 3/4. Decision D26: `chat.py` defaults to `gemini-3.5-flash`; the layout stays as is. One answer from flash had 6 bullets (prompt: max 5).
- All experiment stores deleted; only `helpbot-docs` (40 documents) remains.

### Step 5 - single folder, 40 articles only (2026-10-31)
- Found: the store had 417 documents because the first GitHub Actions run used the pushed commit `94a046e` (before the 40-article scope); the scope commit `8ce75c4` was not pushed yet. The 50% deletion guard would have refused to prune 377 orphans, so the store was deleted and recreated by the job: run1 `added=40`, run2 `skipped=40`.
- `data/` and `samples/` merged into one committed folder `articles/` (job output; git sees 40 renames at 100% similarity, so the job rewrites identical bytes). `scripts/make_samples.py` removed (the id list is the source), `verify_samples.py` -> `verify_articles.py`, test file renamed. Default `ARTICLES_DIR=articles`.
- The "all articles" mode is removed: `main.py` always reads the id list (exit 2 if the file is missing/invalid). Tests build an id list from the articles they provide. All mentions of the larger corpus removed from code, tests, README, docs (this log keeps its history).
- Decision D27: scope is exactly the 40 listed articles; to change it edit `config/article_ids.txt`.

### Step 6 - commit and off-topic probe (2026-10-31)
- Commit `c8eb571 refactor: sync listed articles from articles` (message chosen by the user). `git push` failed from the tool environment (no GitHub credentials: "could not read Username"), so origin is still at `94a046e`; the user pushes from their own terminal. Rule 9 now says: push only on explicit request.
- Recheck on 40 articles: container exit 0 `skipped=40`; `verify_articles.py` 40/40 vs the live site; chat answer for the YouTube question has 1 literal `Article URL:` line and 3 chunks from the right article.
- Off-topic probe (`gemini-3.5-flash` and lite, 4 questions): 3/4 clean refusals ("I can only answer using our documentation"); the weather question is answered from the Weather Wall cities article. Logged as backlog B22 (accepted: prompt is verbatim).

### Step 7 - scripts and README as a user guide (2026-10-31)
- Real OptiBot screenshots (user): short 3-step answer with a titled link, refuses the Paris weather question outright, has chat memory and tool steps. Our bot: prompt + File Search only (the task's scope); differences logged, guardrail ideas declined (D28, backlog B24).
- Latency probe (single measurements): imports 0.2 s, store lookup 0.7 s, `gemini-3.5-flash` 13.7 s (575 thinking tokens), lite 5.5 s; 429 RESOURCE_EXHAUSTED on the free tier appeared during the probe; `thinking_budget=0` dropped the `Article URL:` line. `chat.py` now prints a status line, retry reasons (stderr) and the answer time.
- New `scripts/sync_docs.py` (runs `main.main()`), `scripts/check_store.py` (read-only comparison of store vs `articles/`, `--list`, exit 1 when different) with 4 offline tests (102 passed + 1 xfail). All three run from any directory (verified from /tmp): `check_store` 40/40 in sync, `sync_docs` skipped=40, `chat` correct answer with one `Article URL:` line (24.8 s that time).
- README rewritten as a 51-line guide: scripts table, 5-minute quick start, how it works (chunking explained), evidence section (2 TODOs: Actions run link, screenshot), limits.
