# brain/bmo_brain.py
from brain.emotion_engine import analyze_emotion
from brain.emotion_response_engine import get_response_style
from commands.speech_commands import (
    detect_command_intent,
    normalize_text,
    remove_wake_word
)


def analyze_user_text(text: str) -> dict:
    """
    사용자 발화를 분석해서 감정과 의도를 반환한다.
    감정 판단은 emotion_rules.json을 기반으로 한다.
    """

    normalized_text = remove_wake_word(normalize_text(text))

    if not normalized_text:
        return {
            "emotion": "neutral",
            "emotion_confidence": 0.0,
            "emotion_scores": {},
            "emotion_reasons": ["empty_text"],
            "intent": "chat",
            "style": ""
        }

    emotion_result = analyze_emotion(normalized_text)
    emotion = emotion_result.get("emotion", "neutral")
    intent = detect_command_intent(normalized_text)
    style = get_response_style(emotion, intent)

    return {
        "emotion": emotion,
        "emotion_confidence": emotion_result.get("confidence", 0.0),
        "emotion_scores": emotion_result.get("scores", {}),
        "emotion_reasons": emotion_result.get("reasons", []),
        "intent": intent,
        "style": style
    }
