# Working notes

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
