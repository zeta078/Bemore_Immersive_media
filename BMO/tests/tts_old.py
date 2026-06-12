# tts.py
import re
import time
import platform
import pyttsx3

USE_TTS = True
engine = None


def clean_for_tts(text: str) -> str:
    """
    TTS가 이모지나 특수기호를 이상하게 읽지 않도록 제거
    한글, 영어, 숫자, 기본 문장부호만 남김
    """
    if not text:
        return ""

    # 이모지 금지 명령어
    cleaned = re.sub(r"[^\w\s가-힣.,!?~]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip()

def init_engine() :
    global engine

    if engine is not None:
        return engine
    
    system = platform.system()

    if system == "Windows":
        engine = pyttsx3.init(driverName="sapi5")
    else:
        engine = pyttsx3.init()

        engine.setProperty("rate", 170)
        engine.setProperty("volume", 1.0)

        return engine


def speak(text: str):
    if not text:
        return

    print(f"BMO: {text}")

    text_for_voice = clean_for_tts(text)

    if not text_for_voice:
        return

    if not USE_TTS:
        time.sleep(1)
        return

    try:
        engine = pyttsx3.init(driverName="sapi5")
        engine.setProperty("rate", 180)
        engine.setProperty("volume", 1.0)

        engine.say(text_for_voice)
        engine.runAndWait()
        engine.stop()

    except Exception as e:
        print(f"TTS 오류: {e}")
        time.sleep(1.5)