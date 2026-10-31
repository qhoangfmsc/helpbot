# Backlog: skipped or to optimise (with pros / cons)

Rule 0: core flow first. Everything here is deliberately **after** the flow works. Status: `todo`, `later`, `accepted` (known, decided to live with).

| # | Item | Why not now | Pros of doing it | Cons / cost | Status |
|---|---|---|---|---|---|
| B1 | Make the bot print literal `Article URL:` lines (today it cites a Markdown link, 0 lines) | prompt is verbatim and fixed; fix is in document layout | matches the prompt wording and the screenshot requirement more literally | needs experiments (e.g. repeat the URL line per section) and a full re-upload | **todo, highest** |
| B2 | Include chunk settings in the content hash | settings are fixed for now | changing chunk size would automatically re-ingest | a settings change re-uploads everything (intended) | todo |
| B3 | Real chunk counts | API does not expose them | exact logs | no way today; estimate is labelled `chunks_estimated` | accepted |
| B4 | Orphan (deleted-article) deletion proven on the real API | unit-tested only; demo store covers add/skip/update | confidence | a few extra API calls | later |
| B5 | Link rewriting (absolute help-center links -> relative) | spec says *preserve*; absolute links are better for citations | literal reading of the spec | breaks links outside the site, more code | accepted (not done) |
| B6 | Glued words that exist in the source HTML (~9 articles) | not converter bugs | cosmetic | would mean guessing spaces | accepted |
| B7 | Strip image URLs before indexing | images are kept per spec | fewer noisy tokens per chunk | images are part of "preserve"; needs a second representation | later |
| B8 | Zendesk incremental API instead of full re-scrape | spec says re-scrape and hash | fewer requests | extra moving part; full scrape is 5 requests | accepted |
| B9 | Other locales / languages | only `en-us` needed | broader coverage | more articles, more limit pressure | accepted |
| B10 | Adaptive upload rate (429 handling) and tuning `UPLOAD_WORKERS` | 4 workers worked (417 files in ~16 min) | faster, safer on tight limits | complexity | later |
| B11 | Model name drift (`gemini-2.5-*` already 404) | `chat.py` has fallbacks | resilience | config surface | later |
| B12 | AI Studio cannot attach a File Search store (Tools panel has no such option) | needs the recruiter's answer | proper "set up in AI Studio" evidence | none if they accept the API/CLI evidence | **open question** |
| B13 | CI workflow running pytest | core first | reviewers see a green check | ~10 lines of YAML | todo |
| B14 | Publish a machine-readable run summary (artifact/JSON) | log link is enough for the rubric | easier review | extra code | later |
| B15 | Run `verify_samples.py` on all 417 in CI | rate limits, time | catches converter regressions | slow, network | later |
| B16 | Next.js chat UI | not graded; spec asks for scripts + assistant | nicer demo, shows full-stack skill | hours of work outside the rubric | later (extra credit) |
| B17 | NestJS API layer | not needed: Next.js route handler could call Gemini | shows backend structure | another service and deployment | skip |
| B18 | Postgres for sync state | state already lives in the store | queryable history | extra service, credentials, migrations | skip |
| B19 | Redis | no cache/queue need in a once-a-day job | none here | extra service | skip |
| B20 | Brief short overlap window during updates (old and new version both searchable) | upload-then-delete is the safe order | none needed | seconds of duplicate context | accepted |
| B21 | Heading level jumps (H1 -> H3) in 197 articles | spec says preserve headings | cleaner outline | would alter authored structure | accepted |

| B22 | Full 417-article mode is only exercised by hand | tests run on the 40 samples (Gemini limits) | catches problems that only show at scale | 417 uploads ~16 min; it already found the base64-image bug | accepted (one full run done) |

## Problems found and how they were handled
| Problem | Handling |
|---|---|
| 188 files with empty table headers | fixed (table normalisation) |
| Words glued by whitespace-only tags (28 files) | fixed |
| `<ol start="N">` ignored -> steps renumbered from 1 | fixed (found by the live fact-check) |
| Inline base64 image (1 article, 125 KB line) made one upload fail | fixed: images with `data:` src dropped; linter flags it |
| Gemini 503 "high demand", `gemini-2.5-*` 404 | retries + model fallbacks in `chat.py` |
| Empty fetch could look like "all articles deleted" | guard: job fails, nothing is deleted |
