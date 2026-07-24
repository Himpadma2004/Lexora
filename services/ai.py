"""
services/ai.py
All AI calls for Lexora — fully local, powered by LM Studio's local server.

LM Studio exposes an OpenAI-compatible REST API, so this uses the official
`openai` Python client pointed at your local LM Studio instance instead of
the real OpenAI API.

Model routing:
  - TEXT_MODEL → IELTS questions, IELTS evaluation, GRE word generation
  - QUIZ_MODEL → GRE quiz generation (reasoning model, better at
                 constructing plausible wrong-answer distractors)

Audio transcription: faster-whisper small.en (runs locally, separate from
LM Studio — LM Studio only serves text/vision chat models, not speech-to-text)

No API keys required. Everything runs on your own machine.

Because local models are weaker and less consistent than cloud models,
every structured-output function here uses:
  1. JSON-schema-constrained decoding (forces valid JSON shape)
  2. Python-side validation with automatic retries (catches missing
     fields, wrong counts, duplicate quiz options, out-of-range scores)
  3. A local-file fallback if the model still can't produce valid output
"""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

from openai import OpenAI
import streamlit as st
from faster_whisper import WhisperModel

# ── Model setup ──────────────────────────────────────────────────────────────

# ⚠️ These must EXACTLY match the model identifiers shown in LM Studio.
# Click the copy icon next to a loaded model's name in LM Studio to get the
# exact string, or check the cURL example dropdown shown in the server UI.
TEXT_MODEL = "meta-llama-3.1-8b-instruct"   # matches your currently loaded model
QUIZ_MODEL = "deepseek-r1-distill-qwen-8b"  # ⚠️ UPDATE this after loading DeepSeek in LM Studio

WHISPER_SIZE  = "small.en"   # better accent handling than "base.en"
LMSTUDIO_HOST = os.getenv("LMSTUDIO_HOST", "http://127.0.0.1:1234/v1")
DATA_DIR      = Path("data")
MAX_ATTEMPTS  = 3            # retries before falling back to local data

_client: Optional[OpenAI] = None
_whisper_model: Optional[WhisperModel] = None
_compat_client_cache: dict[tuple[str, str], OpenAI] = {}


def _get_client() -> OpenAI:
    """Initialise (once) the OpenAI-compatible client pointing at LM Studio."""
    global _client
    if _client is None:
        # LM Studio doesn't check the API key, but the client requires a non-empty string
        _client = OpenAI(base_url=LMSTUDIO_HOST, api_key="lm-studio")
    return _client


def _get_whisper() -> WhisperModel:
    """Initialise (once) the local Whisper model for audio transcription."""
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(WHISPER_SIZE, device="auto", compute_type="auto")
    return _whisper_model


def _get_compat_client(base_url: str, api_key: str) -> OpenAI:
    """Return a cached OpenAI-compatible client for local or hosted LLMs."""
    key = (base_url, api_key)
    if key not in _compat_client_cache:
        _compat_client_cache[key] = OpenAI(base_url=base_url, api_key=api_key)
    return _compat_client_cache[key]


def _resolve_practice_backend(provider: str = "local") -> tuple[OpenAI, str]:
    """
    Resolve the model backend for practice-mode OCR cleanup / quiz generation.

    Supported providers:
      - local / offline / lmstudio → LM Studio local server
      - groq → Groq OpenAI-compatible API, if GROQ_API_KEY is configured
    """
    provider = (provider or "local").strip().lower()

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if api_key:
            base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
            model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
            return _get_compat_client(base_url, api_key), model

    return _get_client(), TEXT_MODEL


# ── JSON Schemas (constrains LM Studio's output shape) ────────────────────────
# Note: structured-output mode requires the root schema to be an "object",
# so list-returning endpoints (GRE words) are wrapped in a {"words": [...]} envelope.

QUESTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["topic", "questions"],
}

EVALUATION_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_band": {"type": "number"},
        "fluency": {"type": "number"},
        "grammar": {"type": "number"},
        "vocabulary": {"type": "number"},
        "coherence": {"type": "number"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["overall_band", "fluency", "grammar", "vocabulary",
                 "coherence", "strengths", "weaknesses", "suggestions"],
}

_GRE_WORD_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "word": {"type": "string"},
        "pos": {"type": "string"},
        "ipa": {"type": "string"},
        "pronunciation": {"type": "string"},
        "meaning": {"type": "string"},
        "simple_explanation": {"type": "string"},
        "example": {"type": "string"},
        "mnemonic": {"type": "string"},
        "synonyms": {"type": "array", "items": {"type": "string"}},
        "antonyms": {"type": "array", "items": {"type": "string"}},
        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
    },
    "required": ["word", "pos", "ipa", "pronunciation", "meaning",
                 "simple_explanation", "example", "mnemonic",
                 "synonyms", "antonyms", "difficulty"],
}

GRE_WORDS_SCHEMA = {
    "type": "object",
    "properties": {
        "words": {"type": "array", "items": _GRE_WORD_ITEM_SCHEMA},
    },
    "required": ["words"],
}

QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
        "correct_index": {"type": "integer"},
        "explanation": {"type": "string"},
    },
    "required": ["question", "options", "correct_index", "explanation"],
}

OCR_CLEANUP_SCHEMA = {
    "type": "object",
    "properties": {
        "clean_text": {"type": "string"},
        "summary": {"type": "string"},
        "repair_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["clean_text", "summary", "repair_notes"],
}

PRACTICE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
        "correct_index": {"type": "integer"},
        "explanation": {"type": "string"},
        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
        "source_excerpt": {"type": "string"},
    },
    "required": [
        "question",
        "options",
        "correct_index",
        "explanation",
        "difficulty",
        "source_excerpt",
    ],
}

PRACTICE_SET_SCHEMA = {
    "type": "object",
    "properties": {
        "document_title": {"type": "string"},
        "summary": {"type": "string"},
        "questions": {"type": "array", "items": PRACTICE_ITEM_SCHEMA},
    },
    "required": ["document_title", "summary", "questions"],
}


# ── Core call + retry helper ───────────────────────────────────────────────────

def _strip_think_tags(raw: str) -> str:
    """
    DeepSeek-R1 models sometimes emit a <think>...</think> reasoning block
    before the final answer. Structured-output mode should prevent this,
    but we strip it defensively in case any reasoning leaks through.
    """
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def _call_structured(
    prompt: str,
    schema: dict,
    schema_name: str,
    model: str,
    temperature: float = 0.4,
    client: Optional[OpenAI] = None,
) -> dict:
    """Single call to LM Studio with schema-constrained JSON output on the given model."""
    client = client or _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema, "strict": True},
        },
        temperature=temperature,
    )
    raw = _strip_think_tags(response.choices[0].message.content)
    return json.loads(raw)


def _generate_with_retry(prompt: str, schema: dict, schema_name: str, validator, model: str, temperature: float = 0.4):
    """
    Call the given model up to MAX_ATTEMPTS times, validating each result.
    Local models occasionally skip fields or break constraints (e.g. wrong
    number of quiz options) — this catches that and re-prompts with a
    stronger correction note before giving up.
    """
    last_result = None
    current_prompt = prompt

    for attempt in range(MAX_ATTEMPTS):
        try:
            result = _call_structured(current_prompt, schema, schema_name, model, temperature)
            if validator(result):
                return result
            last_result = result
        except Exception:
            pass

        current_prompt = prompt + (
            "\n\nIMPORTANT: Your previous attempt was incomplete, malformed, "
            "or broke the rules above. Re-read every requirement carefully and "
            "make sure ALL fields are present, non-empty, and follow the exact counts specified."
        )

    return last_result  # best-effort fallback; caller decides if it's usable


def _generate_with_retry_and_client(
    prompt: str,
    schema: dict,
    schema_name: str,
    validator,
    model: str,
    client: OpenAI,
    temperature: float = 0.4,
):
    """Same retry wrapper as _generate_with_retry, but with a caller-provided client."""
    last_result = None
    current_prompt = prompt

    for attempt in range(MAX_ATTEMPTS):
        try:
            result = _call_structured(
                current_prompt,
                schema,
                schema_name,
                model,
                temperature,
                client=client,
            )
            if validator(result):
                return result
            last_result = result
        except Exception:
            pass

        current_prompt = prompt + (
            "\n\nIMPORTANT: Your previous attempt was incomplete, malformed, "
            "or broke the rules above. Re-read every requirement carefully and "
            "make sure ALL fields are present, non-empty, and follow the exact counts specified."
        )

    return last_result


# ── Validators (the "stronger rules" layer) ───────────────────────────────────

def _valid_questions(r: dict) -> bool:
    return (
        isinstance(r, dict)
        and bool(r.get("topic"))
        and isinstance(r.get("questions"), list)
        and len(r["questions"]) >= 3
        and all(isinstance(q, str) and len(q.strip()) > 5 for q in r["questions"])
    )


def _valid_evaluation(r: dict) -> bool:
    if not isinstance(r, dict):
        return False
    score_keys = ["overall_band", "fluency", "grammar", "vocabulary", "coherence"]
    for k in score_keys:
        v = r.get(k)
        if not isinstance(v, (int, float)) or not (0 <= v <= 9):
            return False
    for k in ["strengths", "weaknesses", "suggestions"]:
        if not isinstance(r.get(k), list) or len(r[k]) < 1:
            return False
    return True


def _valid_gre_word(w: dict) -> bool:
    if not isinstance(w, dict):
        return False
    required = ["word", "pos", "ipa", "pronunciation", "meaning",
                "simple_explanation", "example", "mnemonic",
                "synonyms", "antonyms", "difficulty"]
    if not all(w.get(k) for k in required):
        return False
    if len(w["word"].split()) > 2:
        return False
    if not isinstance(w["synonyms"], list) or len(w["synonyms"]) < 2:
        return False
    if not isinstance(w["antonyms"], list) or len(w["antonyms"]) < 1:
        return False
    if w["difficulty"] not in ("easy", "medium", "hard"):
        return False
    return True


def _valid_gre_words_envelope(r: dict, expected_min: int = 5) -> bool:
    if not isinstance(r, dict):
        return False
    words = r.get("words")
    return (
        isinstance(words, list)
        and len(words) >= expected_min
        and all(_valid_gre_word(w) for w in words)
    )


def _valid_quiz(q: dict) -> bool:
    if not isinstance(q, dict):
        return False
    if not q.get("question") or not q.get("explanation"):
        return False
    options = q.get("options")
    if not isinstance(options, list) or len(options) != 4:
        return False
    if len({o.strip().lower() for o in options}) != 4:
        return False
    idx = q.get("correct_index")
    if not isinstance(idx, int) or not (0 <= idx <= 3):
        return False
    return True


def _valid_ocr_cleanup(r: dict) -> bool:
    return (
        isinstance(r, dict)
        and isinstance(r.get("clean_text"), str)
        and len(r["clean_text"].strip()) > 10
        and isinstance(r.get("summary"), str)
        and isinstance(r.get("repair_notes"), list)
    )


def _valid_practice_item(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    required = ["question", "options", "correct_index", "explanation", "difficulty", "source_excerpt"]
    if not all(item.get(key) for key in required):
        return False
    options = item.get("options")
    if not isinstance(options, list) or len(options) != 4:
        return False
    if len({str(opt).strip().lower() for opt in options}) != 4:
        return False
    if item.get("difficulty") not in {"easy", "medium", "hard"}:
        return False
    correct_index = item.get("correct_index")
    return isinstance(correct_index, int) and 0 <= correct_index <= 3


def _valid_practice_envelope(r: dict, expected_min: int = 1) -> bool:
    return (
        isinstance(r, dict)
        and isinstance(r.get("document_title"), str)
        and isinstance(r.get("summary"), str)
        and isinstance(r.get("questions"), list)
        and len(r["questions"]) >= expected_min
        and all(_valid_practice_item(item) for item in r["questions"])
    )


# ── IELTS Speaking (uses TEXT_MODEL) ──────────────────────────────────────────

def generate_ielts_questions(part: int) -> dict:
    """
    Generate IELTS Speaking questions for Part 1, 2, or 3.
    Falls back to sample_questions.json if the local model fails validation.

    Returns: {"topic": str, "questions": list[str]}
    """
    descriptions = {
        1: "Part 1: exactly 5 short personal questions about daily life, hobbies, or work/study.",
        2: "Part 2: One cue card. First item is the instruction starting with 'Describe…'. The next 3 items are the bullet points the candidate must address.",
        3: "Part 3: exactly 4 abstract discussion questions linked to the Part 2 topic.",
    }

    prompt = f"""You are an official IELTS examiner creating speaking test materials.

Generate IELTS Speaking {descriptions[part]}

Rules:
- Every question must be a complete, grammatically correct English sentence.
- Do not repeat similar questions.
- Keep the topic label short (3-5 words).
"""
    result = _generate_with_retry(
        prompt, QUESTIONS_SCHEMA, "ielts_questions", _valid_questions,
        model=TEXT_MODEL, temperature=0.6,
    )

    if result and _valid_questions(result):
        return result

    sample = json.loads((DATA_DIR / "sample_questions.json").read_text(encoding="utf-8"))
    key = f"part{part}"
    return sample.get(key, {"topic": "General", "questions": ["Tell me about yourself."]})


def evaluate_ielts_answer(part: int, question: str, answer: str) -> dict:
    """
    Evaluate a student's IELTS speaking answer using the official band descriptors.
    """
    prompt = f"""You are a certified IELTS Speaking examiner. Evaluate this student response strictly.

Part: {part}
Question: {question}
Student answer: {answer}

Rules:
- Every score (overall_band, fluency, grammar, vocabulary, coherence) MUST be a number
  between 0 and 9, in 0.5 increments. Never leave a score blank or out of range.
- Be realistic — most learners score between 4.5 and 7.5. Do not default every score to the same value.
- Give at least 2 specific strengths, 2 specific weaknesses, and 2 concrete suggestions —
  reference actual words or phrases from the student's answer, not generic advice.
"""
    result = _generate_with_retry(
        prompt, EVALUATION_SCHEMA, "ielts_evaluation", _valid_evaluation,
        model=TEXT_MODEL, temperature=0.4,
    )

    if result and _valid_evaluation(result):
        return result

    return {
        "overall_band": 5.5, "fluency": 5.5, "grammar": 5.5,
        "vocabulary": 5.5, "coherence": 5.5,
        "strengths": ["You attempted to answer the question directly."],
        "weaknesses": ["The local model could not fully evaluate this response — try again."],
        "suggestions": ["Re-record or resubmit your answer for a clearer evaluation."],
    }


def evaluate_audio_answer(part: int, question: str, audio_bytes: bytes, mime_type: str = "audio/webm") -> dict:
    """
    Transcribe recorded audio locally with faster-whisper, then evaluate the
    transcript using TEXT_MODEL as an IELTS examiner.

    Returns an evaluation dict with an extra "transcript" key.
    """
    suffix = ".wav" if "wav" in mime_type else ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        whisper = _get_whisper()
        segments, _info = whisper.transcribe(tmp_path, language="en")
        transcript = " ".join(seg.text.strip() for seg in segments).strip()

        if len(transcript) < 5:
            return {
                "transcript": "(No clear speech detected)",
                "overall_band": 0, "fluency": 0, "grammar": 0,
                "vocabulary": 0, "coherence": 0,
                "strengths": [],
                "weaknesses": ["No speech was detected in the recording."],
                "suggestions": ["Please re-record your answer, speaking clearly into the microphone."],
            }

        result = evaluate_ielts_answer(part, question, transcript)
        result["transcript"] = transcript
        return result

    finally:
        os.unlink(tmp_path)


# ── GRE Vocabulary (words: TEXT_MODEL · quiz: QUIZ_MODEL) ────────────────────

def generate_gre_words(easy: int = 2, medium: int = 2, hard: int = 1) -> list:
    """
    Generate a daily GRE vocabulary set using TEXT_MODEL.
    Falls back to gre_words.json if the local model can't produce valid words.
    """
    total = easy + medium + hard
    prompt = f"""You are a GRE vocabulary expert. Generate exactly {total} GRE-level English words:
- {easy} EASY words
- {medium} MEDIUM words
- {hard} HARD word(s)

STRICT RULES — follow every one of these:
1. Each "word" must be a single real English word (not a phrase, not invented, not a name).
2. Do NOT use common everyday words (e.g. "happy", "big", "run"). These must be genuine
   GRE-level vocabulary that would appear on an actual GRE exam word list.
3. "ipa" must use real IPA symbols in slashes, e.g. /ˈwɜːrd/.
4. "synonyms" must contain at least 3 real, correctly-spelled English words that
   genuinely mean the same thing.
5. "antonyms" must contain at least 2 real, correctly-spelled English words that
   genuinely mean the opposite.
6. "difficulty" must match the requested count exactly — do not mislabel an easy
   word as hard or vice versa.
7. Do not repeat the same word twice in the list.
8. "example" must be a natural, complete sentence using the word correctly in context.

Double-check every word's definition and IPA pronunciation before finalizing your answer.
"""
    result = _generate_with_retry(
        prompt, GRE_WORDS_SCHEMA, "gre_words",
        lambda r: _valid_gre_words_envelope(r, expected_min=total),
        model=TEXT_MODEL, temperature=0.5,
    )

    if result and _valid_gre_words_envelope(result, expected_min=total):
        return result["words"][:total]

    return json.loads((DATA_DIR / "gre_words.json").read_text(encoding="utf-8"))


def generate_word_quiz(word: str, meaning: str, example: str) -> dict:
    """
    Generate a 4-option multiple-choice quiz for a single GRE word using
    QUIZ_MODEL — its reasoning ability helps build genuinely plausible,
    non-obvious wrong-answer distractors instead of generic filler options.
    """
    prompt = f"""Create a GRE-style multiple-choice vocabulary question for the word "{word}".

Definition: {meaning}
Example usage: {example}

STRICT RULES:
1. "options" must contain EXACTLY 4 entries, no more, no less.
2. Exactly ONE option must be the correct definition/usage of "{word}" — this is the
   value at "correct_index".
3. The other 3 options must be real English words or phrases that are plausible
   distractors (similar difficulty level) but clearly incorrect on reflection.
   Do not make distractors that are synonyms of the correct answer.
4. All 4 options must be different from each other — no duplicates or near-duplicates.
5. "correct_index" must be an integer from 0 to 3 matching the position of the
   correct option in the "options" array (0 = first option).
6. "explanation" must clearly state why the correct option is right, in one sentence.

Think through which distractors would actually be plausible/tempting for a GRE
test-taker who only partially knows the word, then finalize your answer.
"""
    result = _generate_with_retry(
        prompt, QUIZ_SCHEMA, "gre_quiz", _valid_quiz,
        model=QUIZ_MODEL, temperature=0.4,
    )

    if result and _valid_quiz(result):
        return result

    return {
        "question": f"What does '{word}' most nearly mean?",
        "options": [meaning, "An unrelated concept", "The opposite meaning", "A common everyday term"],
        "correct_index": 0,
        "explanation": f"'{word}' means: {meaning}",
    }


def clean_ocr_text(raw_text: str, provider: str = "local") -> dict:
    """
    Clean OCR text by fixing spacing, punctuation, broken words, and obvious
    spelling noise while preserving the original meaning as closely as possible.

    Returns a dict with keys: clean_text, summary, repair_notes.
    """
    normalized = re.sub(r"\s+", " ", (raw_text or "")).strip()
    if not normalized:
        return {
            "clean_text": "",
            "summary": "No OCR text was provided.",
            "repair_notes": ["Upload a PDF or image with readable text."],
        }

    client, model = _resolve_practice_backend(provider)
    prompt = f"""You are cleaning noisy OCR output from PDFs and images.

Goal:
- Repair line breaks, punctuation, spacing, broken words, and obvious spelling errors.
- Preserve the original meaning and question order.
- Do not invent facts, answer keys, or content that is not present.
- Keep tables, numbered items, and question numbering if they exist.

OCR text:
{normalized[:12000]}

Return a clean, readable version plus a short summary and 3-7 bullet repair notes.
"""

    result = _generate_with_retry_and_client(
        prompt,
        OCR_CLEANUP_SCHEMA,
        "ocr_cleanup",
        _valid_ocr_cleanup,
        model=model,
        client=client,
        temperature=0.2,
    )

    if result and _valid_ocr_cleanup(result):
        return result

    fallback_text = re.sub(r"[ \t]+", " ", normalized)
    fallback_text = re.sub(r"\n{3,}", "\n\n", fallback_text)
    return {
        "clean_text": fallback_text,
        "summary": "OCR cleanup completed with a lightweight local fallback.",
        "repair_notes": [
            "Whitespace was normalized.",
            "Use a sharper scan or higher-resolution image for better results.",
        ],
    }


def _heuristic_practice_set(clean_text: str, max_questions: int | None, document_name: str) -> dict:
    """Best-effort fallback when the model is unavailable or returns invalid JSON."""
    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
    if not lines:
        return {
            "document_title": document_name,
            "summary": "No readable question text could be extracted.",
            "questions": [],
        }

    candidates = [
        line for line in lines
        if "?" in line or re.match(r"^\d+[\).\-\s]", line)
    ]
    if not candidates:
        candidates = lines

    items = []
    difficulty_cycle = ["easy", "medium", "hard"]
    selected_candidates = candidates if max_questions is None else candidates[:max_questions]
    for idx, line in enumerate(selected_candidates):
        stripped = re.sub(r"^\d+[\).\-\s]+", "", line).strip()
        snippet = stripped[:140] if stripped else line[:140]
        difficulty = difficulty_cycle[idx % 3]
        question = snippet if snippet.endswith("?") else f"Which option best reflects the meaning of this source text?\n\n{snippet}"
        correct = f"A faithful interpretation of: {snippet[:60]}"
        items.append({
            "question": question,
            "options": [
                correct,
                "A loosely related idea",
                "An opposite interpretation",
                "An unrelated distractor",
            ],
            "correct_index": 0,
            "explanation": "This fallback keeps the source meaning intact while still giving a valid MCQ shell.",
            "difficulty": difficulty,
            "source_excerpt": snippet,
        })

    return {
        "document_title": document_name,
        "summary": "A fallback quiz was generated because the LLM output was unavailable or invalid.",
        "questions": items,
    }


def generate_practice_set_from_text(
    raw_text: str,
    provider: str = "local",
    max_questions: int | None = None,
    document_name: str = "Uploaded Practice Set",
) -> dict:
    """
    Convert cleaned OCR text into a GRE-style MCQ practice set.

    This is the core practice pipeline used by the new Practice page.
    """
    cleaned = clean_ocr_text(raw_text, provider=provider)
    clean_text = cleaned.get("clean_text", "")
    if not clean_text.strip():
        return {
            "document_title": document_name,
            "summary": cleaned.get("summary", "No readable text was found."),
            "repair_notes": cleaned.get("repair_notes", []),
            "clean_text": "",
            "questions": [],
        }

    client, model = _resolve_practice_backend(provider)
    prompt = f"""You are converting OCR-cleaned study material into a GRE-style practice set.

Document title: {document_name}

Rules:
1. Extract every distinct MCQ item in the order they appear. Do not stop early unless the source itself ends.
2. If the source already contains a question and answer options, repair OCR noise and preserve the intended meaning.
3. If the source contains a question without options, create exactly 4 plausible options.
4. If the source text is a passage or notes, turn the most test-worthy details into MCQs.
5. Use difficulty labels: easy, medium, hard.
6. Keep explanations short, precise, and grounded in the source text.
7. Do not invent unsupported facts.

Cleaned source text:
{clean_text[:14000]}

Return a JSON object with:
- document_title
- summary
- questions (each item must include question, options[4], correct_index, explanation, difficulty, source_excerpt)
"""

    result = _generate_with_retry_and_client(
        prompt,
        PRACTICE_SET_SCHEMA,
        "practice_set",
        lambda r: _valid_practice_envelope(r, expected_min=1),
        model=model,
        client=client,
        temperature=0.25,
    )

    if result and _valid_practice_envelope(result, expected_min=1):
        result["clean_text"] = clean_text
        result["repair_notes"] = cleaned.get("repair_notes", [])
        return result

    fallback = _heuristic_practice_set(clean_text, max_questions, document_name)
    fallback["clean_text"] = clean_text
    fallback["repair_notes"] = cleaned.get("repair_notes", [])
    return fallback
