"""Chunking settings (400 tokens, 50 overlap) and the local chunk estimate used in the log."""

from helpbot.chunking import MAX_TOKENS_PER_CHUNK, OVERLAP_TOKENS, estimate_chunks


def test_chunking_settings_are_sane():
    assert 0 < OVERLAP_TOKENS < MAX_TOKENS_PER_CHUNK
    assert OVERLAP_TOKENS / MAX_TOKENS_PER_CHUNK <= 0.25  # overlap should not dominate the chunk


def test_chunk_estimate_grows_with_length_and_is_at_least_one():
    assert estimate_chunks("") == 1
    assert estimate_chunks("x" * (4 * MAX_TOKENS_PER_CHUNK)) == 1
    assert estimate_chunks("x" * (4 * MAX_TOKENS_PER_CHUNK + 4)) == 2
    assert estimate_chunks("x" * 40_000) > estimate_chunks("x" * 8_000) > 1
