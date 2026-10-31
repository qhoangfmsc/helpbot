---
name: spec-recheck
description: Re-check the repo against the take-home spec after finishing a feature. Reports requirements that are missing, partially done, or work that is superfluous. Use after every completed milestone and before submission.
---

# spec-recheck

Goal: catch gaps and scope creep against the original spec, not against memory.

1. Read `CLAUDE.local.md` for the spec path and the condensed checklist.
2. Extract the spec text from the PDF (swift/PDFKit snippet in `CLAUDE.local.md`) and read it again. The condensed checklist can drift; the PDF wins.
3. Inspect the repo as it is now (`git status`, `ls`, relevant files, run the tests / the job if cheap). Judge by evidence, not by intent.
4. Output a table, one row per requirement touched by the feature just finished plus any still-open mandatory ones:

   | Requirement | Status (done / partial / missing) | Evidence (file:line, command output) |

5. Then two short lists:
   - **Missing or weak** versus the spec (with the rubric area and points at risk).
   - **Superfluous**: work not asked for by the spec and not on the extra-credit path; propose cutting or deferring.
6. Update the checkboxes in `CLAUDE.local.md` for items that now have evidence.

Rules: never mark done without evidence; quote the spec wording for anything marked verbatim (system prompt); do not copy spec text into tracked files.
