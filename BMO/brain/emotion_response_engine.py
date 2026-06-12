# brain/response_style_engine.py
import json
import os
import random


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STYLE_PATH = os.path.join(BASE_DIR, "response_styles.json")


def load_response_styles() -> dict:
    try:
        with open(STYLE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[STYLE ERROR] {e}")
        return {}


def get_response_style(emotion: str, intent: str) -> str:
    styles = load_response_styles()

    if not styles:
        return ""

    emotion_data = styles.get(emotion)

    if emotion_data is None:
        emotion_data = styles.get("neutral", {})

    candidates = emotion_data.get(intent)

    if not candidates:
        candidates = emotion_data.get("default", [])

    if not candidates:
        return ""

    if isinstance(candidates, str):
        return candidates.strip()

    return random.choice(candidates).strip()
