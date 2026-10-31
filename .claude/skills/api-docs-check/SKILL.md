---
name: api-docs-check
description: Verify an external API (Gemini File Search, Zendesk Help Center) against current docs or a live call before writing code against it. Records confirmed facts in NOTES.md.
---

# api-docs-check

APIs drift faster than model memory. Before writing code that calls one:

1. State the question precisely (e.g. "Does a vector store file accept `attributes`? Is a chunk count returned?").
2. Answer from a primary source: current official docs (web fetch/search) or a minimal live call with throwaway code. Prefer the live call for response shapes.
3. Record in `NOTES.md` under `## Confirmed API facts`: the fact, the source (URL or the command), and the date.
4. Mark anything unconfirmed as `UNVERIFIED` and give the fallback; do not build on it silently.
5. If the SDK is involved, pin the version actually tested in `requirements.txt`.

Open questions for this project (resolve first):
- Gemini File Search: create store, upload file to store (SDK call names, current `google-genai` version), free-tier limits (storage, requests/day, upload rate).
- Per-document `custom_metadata` (`article_id`, `content_hash`): supported? Can documents be listed with their metadata? Can a document be deleted/replaced?
- Chunking config params (max tokens per chunk / overlap) and whether chunk counts are exposed (fallback: estimate locally and say so).
- Citations: does the grounding metadata expose the source document text so `Article URL:` lines are citable?
- Can AI Studio (UI) use a File Search store created through the API (needed for the assistant setup + screenshot)? If not, what is the closest allowed flow?
- Zendesk: already confirmed, see NOTES.md.
