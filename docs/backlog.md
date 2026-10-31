# Backlog: skipped or to optimise (with pros / cons)

Rule 0: core flow first. Everything here is deliberately **after** the flow works. Status: `todo`, `later`, `accepted` (known, decided to live with).

| # | Item | Why not now | Pros of doing it | Cons / cost | Status |
|---|---|---|---|---|---|
| B1 | Make the bot print literal `Article URL:` lines | **resolved by model choice**: layout variants (URL after every heading, URL every ~1000 chars) stayed at 0/6 on `gemini-3.5-flash-lite`; `gemini-3.5-flash` printed them in 4/4 answers and `gemini-3-flash-preview` in 3/4 (temp 0, 8 YouTube-related articles). `chat.py` defaults to `gemini-3.5-flash` | exact match with the prompt wording and the screenshot requirement | costlier than lite; still not perfect (one answer had 6 bullets, prompt says max 5); small sample | done, residual risk accepted |
| B2 | Include chunk settings in the content hash | settings are fixed for now | changing chunk size would automatically re-ingest | a settings change re-uploads everything (intended) | todo |
| B3 | Real chunk counts | API does not expose them | exact logs | no way today; estimate is labelled `chunks_estimated` | accepted |
| B4 | Orphan (deleted-article) deletion proven on the real API | unit-tested only; demo store covers add/skip/update | confidence | a few extra API calls | later |
| B5 | Link rewriting (absolute help-center links -> relative) | spec says *preserve*; absolute links are better for citations | literal reading of the spec | breaks links outside the site, more code | accepted (not done) |
| B6 | Glued words that exist in the source HTML (~9 articles) | not converter bugs | cosmetic | would mean guessing spaces | accepted |
| B7 | Strip image URLs before indexing | images are kept per spec | fewer noisy tokens per chunk | images are part of "preserve"; needs a second representation | later |
| B8 | Zendesk incremental API instead of full re-scrape | spec says re-scrape and hash | fewer requests | extra moving part; full scrape is 5 requests | accepted |
| B9 | Other locales / languages | only `en-us` needed | broader coverage | more articles, more limit pressure | accepted |
| B10 | Adaptive upload rate (429 handling) and tuning `upload_workers` | 4 workers worked (40 files in ~1.5 min) | faster, safer on tight limits | complexity | later |
| B11 | Model name drift (`gemini-2.5-*` already 404) | `chat.py` has fallbacks | resilience | config surface | later |
| B12 | AI Studio cannot attach a File Search store (Tools panel has no such option) | needs the recruiter's answer | proper "set up in AI Studio" evidence | none if they accept the API/CLI evidence | **open question** |
| B13 | CI workflow running pytest | core first | reviewers see a green check | ~10 lines of YAML | todo |
| B14 | Publish a machine-readable run summary (artifact/JSON) | log link is enough for the rubric | easier review | extra code | later |
| B15 | Run `verify_articles.py` in CI | needs network, adds a flaky dependency on the live site | catches converter regressions | slow, network | later |
| B16 | Next.js chat UI | not graded; spec asks for scripts + assistant | nicer demo, shows full-stack skill | hours of work outside the rubric | later (extra credit) |
| B17 | NestJS API layer | not needed: Next.js route handler could call Gemini | shows backend structure | another service and deployment | skip |
| B18 | Postgres for sync state | state already lives in the store | queryable history | extra service, credentials, migrations | skip |
| B19 | Redis | no cache/queue need in a once-a-day job | none here | extra service | skip |
| B20 | Brief short overlap window during updates (old and new version both searchable) | upload-then-delete is the safe order | none needed | seconds of duplicate context | accepted |
| B21 | Heading level jumps (H1 -> H3) in 197 articles | spec says preserve headings | cleaner outline | would alter authored structure | accepted |

| B22 | Off-topic questions that happen to touch a document ("What is the weather in Paris?" -> bot says it has no live weather, then states that Paris is a supported Weather Wall city, with the right `Article URL:`) | the system prompt is verbatim and cannot say "if the docs lack it, say so"; File Search only has `top_k`, no relevance threshold | cleaner refusals for near-topic questions | would need prompt changes (not allowed) or a post-filter that is not part of the assistant itself | accepted: measured on 4 off-topic questions x 2 models, 3/4 are clean refusals, the 4th is grounded in a real document |
| B23 | Slow answers: `gemini-3.5-flash` spends ~500 hidden "thinking" tokens (13.7 s measured), the lite model answers in ~5.5 s; the free tier allows only ~20 requests per model per day (429 `PerDay`) | speed is not graded; `thinking_budget=0` made the answer lose its `Article URL:` line | faster chat | stream the answer (looks faster), or accept lite and its weaker prompt compliance | accepted: `chat.py` shows a status line, the time, and moves to another model at once when the daily quota is used up (see conventions section 4) |
| B24 | Answer "guardrails" (a script scoring answers, validate-and-retry, an off-topic classifier before answering) | the task only grades that the sample question is answered correctly with cited URLs; these would be workarounds around the verbatim prompt, not part of the assistant | measurable quality, closer to the real OptiBot | extra model calls, code outside the assistant, risk of looking like a hack | **declined by the user** |

## Problems found and how they were handled
| Problem | Handling |
|---|---|
| Many files with empty table headers (first scrape) | fixed (table normalisation) |
| Words glued by whitespace-only tags | fixed |
| `<ol start="N">` ignored -> steps renumbered from 1 | fixed (found by the live fact-check) |
| Inline base64 image (one article, a single 125 KB line) made an upload fail | fixed: images with `data:` src dropped; linter flags it |
| Gemini 503 "high demand", `gemini-2.5-*` 404 | retries + model fallbacks in `chat.py` |
| Empty fetch could look like "all articles deleted" | guard: job fails, nothing is deleted |
