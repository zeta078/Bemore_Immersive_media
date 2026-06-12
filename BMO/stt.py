# stt.py
import json
import os

from faster_whisper import WhisperModel

from commands.speech_commands import (
    contains_wake_word,
    remove_wake_word,
    is_rest_command
)
from logger import log_debug, log_error


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORRECTION_PATH = os.path.join(BASE_DIR, "stt_corrections.json")
_stt_corrections_cache = None

VERY_LOW_STT_CONFIDENCE = 0.45
CONFIDENT_STT_CONFIDENCE = 0.75
MIN_TEXT_LENGTH = 2
UNCLEAR_TEXTS = {
    "음",
    "어",
    "아",
    "응",
    "네",
    "예",
    "그",
    "저",
}

model = WhisperModel("base", device="cpu", compute_type="int8")


def load_stt_corrections() -> dict:
    global _stt_corrections_cache

    if _stt_corrections_cache is not None:
        return _stt_corrections_cache

    if not os.path.exists(CORRECTION_PATH):
        _stt_corrections_cache = {}
        return _stt_corrections_cache

    try:
        with open(CORRECTION_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                log_error("[STT CORRECTION ERROR] stt_corrections.json은 JSON 객체 형식이어야 합니다")
                data = {}
            _stt_corrections_cache = data
            return _stt_corrections_cache
    except Exception as e:
        log_error(f"[STT CORRECTION ERROR] {e}")
        _stt_corrections_cache = {}
        return _stt_corrections_cache


def apply_stt_corrections(text: str) -> str:
    if not text:
        return ""

    corrected = text.strip()

    for wrong, correct in load_stt_corrections().items():
        corrected = corrected.replace(wrong, correct)

    return corrected.strip()


def is_unclear_text(text: str) -> bool:
    normalized = (text or "").strip()

    return normalized in UNCLEAR_TEXTS


def is_too_short(text: str) -> bool:
    normalized = (text or "").strip()

    return len(normalized.replace(" ", "")) < MIN_TEXT_LENGTH


def analyze_raw_stt(raw_text: str, probability: float) -> tuple[str, str]:
    normalized = (raw_text or "").strip()

    if not normalized:
        return "very_uncertain", "empty_text"

    if probability < VERY_LOW_STT_CONFIDENCE:
        return "very_uncertain", "very_low_stt_confidence"

    if is_too_short(normalized):
        return "very_uncertain", "too_short_raw_text"

    if is_unclear_text(normalized):
        return "very_uncertain", "unclear_raw_expression"

    if probability < CONFIDENT_STT_CONFIDENCE:
        return "uncertain", "medium_stt_confidence"

    return "confident", ""


def analyze_corrected_stt(corrected_text: str, current_level: str, current_reason: str) -> tuple[str, str]:
    if current_level == "very_uncertain":
        return current_level, current_reason

    if not corrected_text:
        return "uncertain", "empty_corrected_text"

    if is_too_short(corrected_text):
        return "uncertain", "too_short_corrected_text"

    if is_unclear_text(corrected_text):
        return "uncertain", "unclear_corrected_expression"

    return current_level, current_reason


def build_stt_result(raw_text="", corrected_text="", language="", probability=0.0, correction_applied=False) -> dict:
    uncertainty_level, uncertain_reason = analyze_raw_stt(raw_text, probability)
    uncertainty_level, uncertain_reason = analyze_corrected_stt(
        corrected_text,
        uncertainty_level,
        uncertain_reason
    )
    should_call_llm = uncertainty_level == "confident"

    return {
        "raw_text": raw_text,
        "corrected_text": corrected_text,
        "text": corrected_text,
        "language": language,
        "probability": probability,
        "confidence": probability,
        "uncertainty_level": uncertainty_level,
        "is_uncertain": uncertainty_level != "confident",
        "uncertain_reason": uncertain_reason,
        "blocked_reason": "" if should_call_llm else uncertain_reason,
        "correction_applied": correction_applied,
        "should_call_llm": should_call_llm,
        "needs_llm_caution": False
    }


def speech_to_text(audio_path="input.wav") -> dict:
    try:
        segments, info = model.transcribe(
            audio_path,
            language="ko",
            vad_filter=True
        )

        raw_text = " ".join(segment.text for segment in segments).strip()
        probability = float(getattr(info, "language_probability", 0.0) or 0.0)
        language = getattr(info, "language", "")
        raw_level, _ = analyze_raw_stt(raw_text, probability)

        if raw_level == "very_uncertain":
            corrected_text = raw_text
            correction_applied = False
        else:
            corrected_text = apply_stt_corrections(raw_text)
            correction_applied = corrected_text != raw_text

        log_debug(f"[STT DEBUG] raw_text={raw_text}")
        log_debug(f"[STT DEBUG] corrected_text={corrected_text}")
        log_debug(f"[STT DEBUG] language={language}, probability={probability:.2f}")
        log_debug(f"[STT DEBUG] correction_applied={correction_applied}")

        return build_stt_result(
            raw_text=raw_text,
            corrected_text=corrected_text,
            language=language,
            probability=probability,
            correction_applied=correction_applied
        )

    except Exception as e:
        log_error(f"[STT ERROR] {e}")
        return build_stt_result(probability=0.0)
