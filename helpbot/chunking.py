"""Chunking settings sent to the store, plus a local estimate of how many chunks that produces.

The File Search API chunks and embeds server-side and does not report chunk counts, so the number we log is
an estimate: the whitespace chunker slides a window of `MAX_TOKENS_PER_CHUNK` tokens, advancing by
`MAX_TOKENS_PER_CHUNK - OVERLAP_TOKENS`.
"""

import math

MAX_TOKENS_PER_CHUNK = 400
OVERLAP_TOKENS = 50
CHARS_PER_TOKEN = 4  # rough average for English text; real tokenisation differs slightly


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def estimate_chunks(text: str) -> int:
    tokens = estimate_tokens(text)
    if tokens <= MAX_TOKENS_PER_CHUNK:
        return 1
    return 1 + math.ceil((tokens - MAX_TOKENS_PER_CHUNK) / (MAX_TOKENS_PER_CHUNK - OVERLAP_TOKENS))
