import re
from functools import lru_cache

from transformers import AutoTokenizer, pipeline

MODEL = "sshleifer/distilbart-cnn-12-6"

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
CONTROL_CHARS = re.compile(r"[\u200B-\u200D\uFEFF\x00-\x1F\x7F]")


@lru_cache(maxsize=1)
def _get_tokenizer():
    return AutoTokenizer.from_pretrained(MODEL, use_fast=True)


@lru_cache(maxsize=1)
def _get_summarizer():
    tok = _get_tokenizer()
    return pipeline("summarization", model=MODEL, tokenizer=tok)


def _normalize(text: str) -> str:
    text = CONTROL_CHARS.sub(" ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _to_bullets(text: str, max_items: int) -> list[str]:
    sents = [s.strip("•-—–· \t") for s in SENT_SPLIT.split(text) if s.strip()]

    bullets: list[str] = []
    seen: set[str] = set()
    for s in sents:
        if len(s.split()) < 6:
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        bullets.append(s)
        if len(bullets) >= max_items:
            break
    return bullets or ([text] if text else [])


def summarize_slide(text: str, ratio: float = 0.65, max_bullets: int = 10) -> list[str]:
    """Summarize a slide into bullet points.

    - Uses a cached HF summarization pipeline.
    - Returns short text as-is.
    """

    text = _normalize(text)
    if not text:
        return ["⚠️ No readable text found on this slide."]

    words = len(text.split())
    if words < 25:
        return [text]

    tokenizer = _get_tokenizer()
    summarizer = _get_summarizer()

    enc = tokenizer(text, add_special_tokens=False, return_attention_mask=False)
    input_tokens = len(enc["input_ids"])

    target_words = max(40, min(int(words * ratio), 220))
    approx_max_tok = int(target_words * 1.3)

    
    max_len = min(max(30, approx_max_tok), int(input_tokens * 0.9))
    min_len = max(20, int(max_len * 0.75))
    if min_len >= max_len:
        min_len = max(12, int(max_len * 0.6))
    
    # Absolute safety check to prevent ValueError from pipeline
    if min_len >= max_len:
        min_len = max(1, max_len - 1)

    out = summarizer(
        text,
        max_length=max_len,
        min_length=min_len,
        truncation=True,
        no_repeat_ngram_size=3,
        num_beams=4,
        do_sample=False,
        length_penalty=1.05,
        early_stopping=True,
    )[0]["summary_text"].strip()

    return _to_bullets(out, max_items=max_bullets)
