# brain/emotion_engine.py
import json
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RULE_PATH = os.path.join(BASE_DIR, "emotion_rules.json")
NEGATION_PATH = os.path.join(BASE_DIR, "emotion_negation.json")


def load_json_file(path: str, error_label: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[{error_label} ERROR] {e}")
        return {}


def load_emotion_rules() -> dict:
    return load_json_file(RULE_PATH, "EMOTION")


def load_negation_rules() -> dict:
    return load_json_file(NEGATION_PATH, "NEGATION")


def match_pattern(text: str, pattern: str) -> bool:
    """
    pattern = "기분 좋아"
    text = "나 지금 기분이 좋아"
    → "기분", "좋아"가 모두 포함되므로 True
    """
    words = pattern.split()
    return all(word in text for word in words)


def has_negative_expression(text: str) -> bool:
    """
    부정 감정 문장 감지
    예:
    - 안 좋아
    - 좋지 않아
    - 기분 별로
    - 행복하지 않아
    """
    rules = load_negation_rules()

    if not rules:
        return False

    negative_patterns = rules.get("negative_patterns", [])
    negative_words = rules.get("negative_words", [])
    positive_base_words = rules.get("positive_base_words", [])

    # 1. 직접 부정 패턴 우선 검사
    for pattern in negative_patterns:
        if match_pattern(text, pattern):
            return True

    # 2. 긍정 어근 + 부정 단서 조합 검사
    has_positive = any(word in text for word in positive_base_words)
    has_negative = any(word in text for word in negative_words)

    if has_positive and has_negative:
        return True

    return False


def detect_emotion(text: str) -> str:
    return analyze_emotion(text).get("emotion", "neutral")


def analyze_emotion(text: str) -> dict:
    if not text:
        return {
            "emotion": "neutral",
            "confidence": 0.0,
            "scores": {},
            "reasons": ["empty_text"]
        }

    reasons = []
    if has_negative_expression(text):
        reasons.append("negative_expression")

    rules = load_emotion_rules()

    if not rules:
        return {
            "emotion": "neutral",
            "confidence": 1.0,
            "scores": {},
            "reasons": ["rules_not_loaded"]
        }

    scores = {}

    for emotion, data in rules.items():
        scores[emotion] = 0

        weight = data.get("weight", 1)
        patterns = data.get("patterns", [])

        for pattern in patterns:
            if match_pattern(text, pattern):
                scores[emotion] += weight
                reasons.append(f"{emotion}:{pattern}+{weight}")

    if "negative_expression" in reasons:
        scores["sad"] = scores.get("sad", 0) + 3
        reasons.append("sad:negation_boost+3")

    best_emotion = max(scores, key=scores.get)
    best_score = scores[best_emotion]

    if best_score == 0:
        return {
            "emotion": "neutral",
            "confidence": 0.0,
            "scores": scores,
            "reasons": reasons or ["no_emotion_match"]
        }

    total_score = sum(score for score in scores.values() if score > 0)
    tied_emotions = [
        emotion for emotion, score in scores.items()
        if score == best_score
    ]

    confidence = best_score / total_score if total_score else 0.0

    if len(tied_emotions) > 1:
        confidence *= 0.6
        reasons.append("tie_penalty")

    return {
        "emotion": best_emotion,
        "confidence": round(confidence, 2),
        "scores": scores,
        "reasons": reasons
    }
