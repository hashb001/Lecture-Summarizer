import logging
import os
from functools import lru_cache

from transformers import pipeline
import re
from collections import Counter
import torch

logger = logging.getLogger("ai_lecture_app")

def _get_device() -> int:
    """Return 0 (first CUDA GPU) if available, else -1 (CPU)."""
    if torch.cuda.is_available():
        logger.info(f"GPU detected: {torch.cuda.get_device_name(0)} — running model on CUDA")
        return 0
    logger.info("No CUDA GPU found — running model on CPU")
    return -1

@lru_cache(maxsize=1)
def _get_qa_pipeline():
    device = _get_device()
    return pipeline("text2text-generation", model="google/flan-t5-base", device=device)


try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore
STOPWORDS = {
    "the","a","an","and","or","but","if","then","else","to","of","in","on","for","with","by","as","at",
    "from","is","are","was","were","be","been","being","it","this","that","these","those","we","you","they",
    "i","he","she","them","his","her","our","your","their","not","can","could","should","would","may","might",
    "will","just","also","into","than","such","over","under","about","more","most","some","any","each"
}

def _keywords(text: str, k: int = 10) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", (text or "").lower())
    words = [w for w in words if w not in STOPWORDS]
    counts = Counter(words)
    # Prefer informative tokens: filter out very short and very common
    return [w for w, _ in counts.most_common(k)]

def _local_assignment_from_text(lecture_text: str) -> str:
    kws = _keywords(lecture_text, k=10)
    topics = kws[:6] if kws else ["the lecture content"]

    title = "Assignment: Key Concepts and Application"
    instructions = (
        "Read the lecture materials carefully. Answer all questions using only the lecture content. "
        "Where appropriate, use examples and justify your reasoning."
    )

    
    short_qs = []
    for i, t in enumerate(topics[:5], start=1):
        short_qs.append(f"{i}. Define “{t}” as used in the lecture and explain why it matters.")

    analytical = [
        f"1. Compare and contrast “{topics[0]}” and “{topics[1]}” based on the lecture. What are the key differences?",
        f"2. Choose one major concept (e.g., “{topics[2]}”) and explain how it connects to at least two other ideas from the lecture.",
        f"3. Identify an assumption or limitation discussed or implied in the lecture. How could it affect real-world use?"
    ]

    application = (
        "Scenario: Imagine you are asked to teach the main ideas of this lecture to a new student in 10 minutes.\n"
        "Task: Create a brief outline (5–8 bullet points) and include one practical example that demonstrates the core concept(s)."
    )

    return (
        f"Title:\n- {title}\n\n"
        f"Instructions:\n- {instructions}\n\n"
        "Part A – Short Answer Questions:\n"
        + "\n".join(f"- {q}" for q in short_qs)
        + "\n\n"
        "Part B – Analytical Questions:\n"
        + "\n".join(f"- {q}" for q in analytical)
        + "\n\n"
        "Part C – Application Task:\n"
        f"- {application}"
    )

def _local_quiz_from_text(lecture_text: str) -> str:
    kws = _keywords(lecture_text, k=12)
    topics = kws[:8] if kws else ["lecture"]

    title = "Quiz: Lecture Comprehension Check"
    instructions = "Answer all questions. Use only the lecture content; do not guess beyond what was taught."

    # Simple MCQ stems that remain grounded
    mcq = []
    for i, t in enumerate(topics[:8], start=1):
        mcq.append(
            f"{i}. In the lecture, “{t}” most directly refers to:\n"
            "   A) A key concept discussed in the lecture\n"
            "   B) An unrelated idea not covered\n"
            "   C) A historical fact outside the lecture\n"
            "   D) A purely fictional example"
        )

    sa = []
    for i, t in enumerate(topics[:4], start=1):
        sa.append(f"{i}. Explain “{t}” in 2–4 sentences based on the lecture.")

    return (
        f"Title:\n- {title}\n\n"
        f"Instructions:\n- {instructions}\n\n"
        "Part A – Multiple Choice:\n"
        + "\n\n".join(f"- {q}" for q in mcq)
        + "\n\n"
        "Part B – Short Answer:\n"
        + "\n".join(f"- {q}" for q in sa)
    )

def _get_openai_client():
    if OpenAI is None:
        raise RuntimeError(
            "OpenAI Python SDK is not installed. Add 'openai' to requirements.txt and pip install it."
        )
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)



def answer_question(context: str, question: str) -> str:
    """Answer using only the provided context."""
    qa = _get_qa_pipeline()

    prompt = (
        "Answer the question using only the information from the lecture below. "
        "If the lecture does not contain the answer, say you don't know.\n\n"
        "LECTURE:\n"
        f"{context}\n\n"
        "QUESTION:\n"
        f"{question}\n\n"
        "ANSWER:"
    )

    result = qa(
        prompt,
        max_new_tokens=256,
        do_sample=False,
        truncation=True,
    )
    return (result[0].get("generated_text") or "").strip()


def explain_slide(context: str, instruction: str) -> str:
    """Generate a longer, didactic explanation grounded in slide context."""
    qa = _get_qa_pipeline()

    full_prompt = (
        "You are an excellent university tutor. Use ONLY the slide context. "
        "If something isn't in the context, say so.\n\n"
        "SLIDE CONTEXT:\n"
        f"{context}\n\n"
        "INSTRUCTION:\n"
        f"{instruction}\n\n"
        "EXPLANATION:"
    )

    result = qa(
        full_prompt,
        max_new_tokens=420,
        do_sample=False,
        truncation=True,
    )
    return (result[0].get("generated_text") or "").strip()



def generate_assignment_from_lecture(lecture_text: str) -> str:
    # If OpenAI SDK or key is missing, fall back immediately
    try:
        client = _get_openai_client()
    except Exception:
        return _local_assignment_from_text(lecture_text)

    prompt = f"""
You are a university instructor. Based ONLY on the lecture content below, write a ready-to-use assignment for university students.

LECTURE CONTENT:
{lecture_text}

Write the FINAL assignment in this structure (but DO NOT repeat this description, just follow it):

Title:
- A short academic-style title for the assignment.

Instructions:
- 2–3 sentences explaining what students must do.

Part A – Short Answer Questions:
- 5 numbered short-answer questions.
- Questions must require understanding of the lecture, not copying.

Part B – Analytical Questions:
- 3 numbered, higher-order questions (explain, compare, evaluate, argue, etc).

Part C – Application Task:
- 1 realistic scenario or problem where students must apply the lecture concepts.

IMPORTANT:
- Output ONLY the finished assignment text.
- Do NOT show any section called “RULES”.
- Do NOT repeat or mention these instructions or the structure description.
- Do NOT include answers.
- Do NOT introduce information that is not in the lecture.
""".strip()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful university instructor. Follow constraints strictly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        # Covers insufficient_quota (429), invalid_api_key (401), network errors, etc.
        return _local_assignment_from_text(lecture_text)



def generate_quiz_from_lecture(lecture_text: str) -> str:
    try:
        client = _get_openai_client()
    except Exception:
        return _local_quiz_from_text(lecture_text)

    prompt = f"""
You are a university instructor. Based ONLY on the lecture content below, write a ready-to-use quiz for university students.

LECTURE CONTENT:
{lecture_text}

Write the FINAL quiz in this structure (but DO NOT repeat this description, just follow it):

Title:
- A short academic-style title for the quiz.

Instructions:
- 1–2 sentences explaining how to answer.

Part A – Multiple Choice:
- 8 numbered multiple-choice questions.
- Each question has options A–D.
- Do NOT include answers or an answer key.

Part B – Short Answer:
- 4 numbered short-answer questions.

IMPORTANT:
- Output ONLY the finished quiz text.
- Do NOT show any section called “RULES”.
- Do NOT repeat or mention these instructions or the structure description.
- Do NOT include answers.
- Do NOT introduce information that is not in the lecture.
""".strip()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful university instructor. Follow constraints strictly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return _local_quiz_from_text(lecture_text)
