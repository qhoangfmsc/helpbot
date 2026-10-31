from pathlib import Path

# The take-home requires this exact text (note the bullet character U+2022 and straight quotes).
EXPECTED = (
    "You are OptiBot, the customer-support bot for OptiSigns.com.\n"
    "• Tone: helpful, factual, concise.\n"
    "• Only answer using the uploaded docs.\n"
    "• Max 5 bullet points; else link to the doc.\n"
    '• Cite up to 3 "Article URL:" lines per reply.'
)


def test_system_prompt_is_verbatim():
    assert (Path(__file__).resolve().parents[2] / "prompts" / "system_prompt.txt").read_text(encoding="utf-8") == EXPECTED
