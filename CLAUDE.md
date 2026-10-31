# helpbot

Docs-grounded support bot: scrape a Zendesk Help Center -> clean Markdown -> Gemini File Search store -> daily delta sync job (Docker, cloud cron).
Part 1 of a time-boxed take-home. Planning work is **not** in this repo.

The take-home spec lives outside the repo; its path and the requirement checklist are in `CLAUDE.local.md` (git-ignored). Never copy the spec or the file path into tracked files.

## Rule 0 - core flow first, optimise last (overrides every other rule)

1. **Finish the whole core flow the task asks for first** (scrape -> Markdown -> upload via API -> assistant check -> Docker -> scheduled daily job with delta + logs -> README), so there is a working prototype that already earns the rubric points. Test that prototype end to end.
2. **Only then optimise**, starting from that working prototype, in order of rubric value.
3. **When a problem shows up while building:** write it down in `docs/backlog.md`. If it can be fixed right away (a few minutes), fix it. If it is complex, do **not** chase it: cover the case with a simple guard that fails loudly or degrades safely (an error, a skip, a log line) and move on.
4. **Do not polish details before the flow works.** No perfecting of one corner case while other required parts are missing.
5. **Write down every reason and decision** (why this design, why this convention, what was skipped and its pros/cons) in `NOTES.md` (log), `docs/conventions.md` (code conventions and their reasons) and `docs/backlog.md` (skipped/optimise items), so it can be explained later in the interview.

## Rules

1. **Rubric-first.** Every task maps to a graded area (scrape quality 25, API vector-store upload 20, daily job + logs 15, code + README 10, tests +5). The pass bar equals the sum of the required areas, so none can be skimped. Out-of-rubric work (Next.js UI, NestJS, Postgres, Redis) only after the required parts are done and >1.5h remains.
2. **Timebox: 8 focused hours.** Note actual time per milestone in `NOTES.md`. Anything cut goes in the README.
3. **System prompt is verbatim.** It lives only in `prompts/system_prompt.txt`; a test compares it to the spec text. Never paraphrase or translate.
4. **Job contract.** `main.py` runs once and exits 0 on success, non-zero on failure. Idempotent. State is committed only after the upload is confirmed. Final log line: `added=X updated=Y skipped=Z deleted=D failed=F files=N chunks_estimated=M store_documents=S` (chunk counts are not exposed by the API, so they are estimated and labelled).
5. **Do not trust memory for APIs.** Check current Gemini API docs before writing API calls; record what was confirmed in `NOTES.md` (see skill `api-docs-check`).
6. **Evidence before "done".** Run it and show output / screenshot. No "should work".
7. **Secrets and names.** Keys only via env / `.env`; keep `.env.sample` current. No "optisigns"/"optibot" in repo name, description, commit messages or code identifiers (the README may name the scraped site where unavoidable).
8. **Tests are pure.** No network in unit tests; use fixtures (HTML -> Markdown, delta classification, prompt verbatim, hashing).
9. **Commits: only when the user asks, and confirm before committing; push only when the user explicitly asks.** Granularity: **one commit per finished step/feature** (code + its tests + the docs/notes it changes), not many tiny commits; split only if a step mixes unrelated concerns. Format: **Conventional Commits** `type(scope): subject` (types: feat, fix, docs, test, chore, refactor, ci, build; imperative, <= 72 chars, e.g. `feat(scrape): convert help center articles to markdown`), plus an optional body that says what and why. When asked, first show the exact files and message and wait for an explicit second confirmation. Only then commit, with the user's own git identity as the only author: **no `Co-Authored-By` trailer and no tool attribution lines**. Stage by explicit paths, never `git add -A`.
10. **README <= 1 page** (setup, run locally, daily-job log link, screenshot). Count lines before finishing.
11. **After every finished feature, run `/spec-recheck`** and report what is missing or superfluous versus the spec before moving on.
12. **Stateless sync.** Change detection state lives in File Search document metadata (`article_id`, `content_hash`), not in a DB or local disk (cron filesystems are ephemeral). Verify attribute support in the current API first.
13. **Log every step.** Record decisions (with why), confirmed API facts and what was done (with evidence) in `NOTES.md`, then give the user a short summary at the end of each step: what was done, decisions, evidence, what is next, proposed commit.
14. **Plan first, then do.** Before each step, present a short plan (goal, who does what, risks, open decisions), settle any open items left from the previous step, and wait for the user's go-ahead before coding.
15. **Ask before calling the Gemini generate API.** The free tier allows only ~20 requests per model per day (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`). Never run chat/eval/probe scripts that generate text on my own: prefer offline tests and fakes, and ask the user first for any real-API check (uploads and store listing are not generate calls, but still ask before big runs).

## Layout

```
main.py  Dockerfile  README.md  .env.sample
helpbot/         # package: zendesk fetch, markdown conversion, scrape, (later) vector store, sync
tests/           # pytest, fixtures in tests/fixtures
prompts/         # system_prompt.txt
config/          # article_ids.txt: the 40 articles the job syncs (includes the YouTube article)
articles/        # the 40 Markdown files: job output, committed so reviewers can read them
data/            # git-ignored scratch space for experiments
scripts/         # user-facing: sync_docs.py, check_store.py, chat.py (documented in README); dev: check_markdown, verify_articles, demo_delta
.claude/skills/  # spec-recheck, md-quality-check, api-docs-check, verify-submission
```

Python 3.12. Dependencies pinned in `requirements.txt`.

## Conventions

- Match the surrounding code; type hints on public functions; no speculative abstractions.
- Logging via `logging` (never `print` in `helpbot/`); structured `key=value` summary lines.
- Network access isolated behind small functions so tests can stub them.
