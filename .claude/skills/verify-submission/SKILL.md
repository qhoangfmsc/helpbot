---
name: verify-submission
description: Final pre-submission gate for the take-home repo - runs the Docker job, scans for secrets and forbidden names, checks README length, verbatim prompt, logs link and screenshots. Use right before sending the repo.
---

# verify-submission

Run each check and report pass/fail with evidence. Do not fix silently; list failures first.

1. `/spec-recheck` - everything mandatory must be `done`.
2. Build and run: `docker build -t helpbot .` then `docker run --rm --env-file .env helpbot`; confirm exit code `0` and the final summary line `added= updated= skipped= files= chunks=`.
3. Second run of the same command must show `added=0 updated=0` and `skipped=<all>` (delta works, idempotent).
4. Secrets: `git ls-files` contains no `.env`; `git grep -nEi "sk-[A-Za-z0-9]{20,}|api[_-]?key\s*=\s*['\"]?[A-Za-z0-9]"` returns nothing real; `git log -p` has no keys either.
5. Names: `git ls-files`, repo name, description, commit messages (`git log --format=%s%n%b`) contain no `optisigns` / `optibot` (README mention of the scraped site is the only allowed one).
6. `prompts/system_prompt.txt` equals the spec text byte-for-byte (the test in `tests/` must pass).
7. `wc -l README.md` fits one page (~60 lines max); contains setup, local run, daily-job log link (open it logged-out), screenshot with cited `Article URL:` lines.
8. `pytest -q` passes; no network used.
9. Public log link works for a reviewer without login.
10. List what was cut for the README "cut" section.
