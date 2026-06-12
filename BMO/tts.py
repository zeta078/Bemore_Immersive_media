# tts.py
import re
import time
import os
import asyncio
import subprocess
import tempfile
import platform
import threading
import ctypes

import edge_tts

from logger import log_simple, log_debug, log_warn, log_error


USE_TTS = True

# =========================
# edge-tts 설정
# =========================
EDGE_VOICE = "ko-KR-SunHiNeural"
EDGE_RATE = "+5%"
EDGE_PITCH = "+30Hz"
EDGE_VOLUME = "+0%"

TTS_OUTPUT_PATH = os.path.join(tempfile.gettempdir(), "bmo_edge_tts.mp3")

# ffplay가 PATH에 잡혀 있으면 그대로 사용
# 안 잡혀 있으면 예: r"C:\ffmpeg\bin\ffplay.exe" 로 직접 지정 가능
FFPLAY_PATH = "ffplay"

_play_process = None
_mci_alias = None
_play_lock = threading.Lock()
_speak_lock = threading.Lock()


def clean_for_tts(text: str) -> str:
    """
    TTS가 이모지나 특수기호를 이상하게 읽지 않도록 제거
    한글, 영어, 숫자, 기본 문장부호만 남김
    """
    if not text:
        return ""

    cleaned = re.sub(r"[^\w\s가-힣.,!?~]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip()


async def _save_edge_tts(text: str, output_path: str):
    communicate = edge_tts.Communicate(
        text=text,
        voice=EDGE_VOICE,
        rate=EDGE_RATE,
        volume=EDGE_VOLUME,
    )
    await communicate.save(output_path)


def _generate_edge_tts(text: str, output_path: str):
    """
    edge-tts는 async 기반이지만,
    외부에서는 기존 pyttsx3처럼 동기 함수 speak(text)로 쓰기 위해 내부에서 처리
    """
    asyncio.run(_save_edge_tts(text, output_path))


def stop_tts():
    """
    현재 재생 중인 TTS가 있으면 즉시 중지한다.
    """
    global _play_process, _mci_alias

    with _play_lock:
        process = _play_process
        _play_process = None
        mci_alias = _mci_alias
        _mci_alias = None

    if mci_alias is not None:
        _mci_send(f"stop {mci_alias}", log_failure=False)
        _mci_send(f"close {mci_alias}", log_failure=False)

    if process is None:
        return

    if process.poll() is not None:
        return

    try:
        process.terminate()
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=0.5)
    except Exception as e:
        log_warn(f"[TTS WARN] 재생 중지 실패: {e}")


def _mci_send(command: str, log_failure=True) -> bool:
    error_code = ctypes.windll.winmm.mciSendStringW(command, None, 0, None)

    if error_code == 0:
        return True

    if log_failure:
        log_warn(f"[TTS WARN] MCI 명령 실패({error_code}): {command}")

    return False


def _play_audio_with_mci(output_path: str) -> bool:
    global _mci_alias

    if platform.system() != "Windows":
        return False

    alias = "bmo_tts"
    stop_tts()

    if not _mci_send(f'open "{output_path}" type mpegvideo alias {alias}'):
        return False

    with _play_lock:
        _mci_alias = alias

    try:
        played = _mci_send(f"play {alias} wait")
    finally:
        _mci_send(f"close {alias}", log_failure=False)
        with _play_lock:
            if _mci_alias == alias:
                _mci_alias = None

    return played


def _play_audio(output_path: str) -> bool:
    """
    ffplay로 미디어 플레이어 창 없이 재생
    ffplay 프로세스를 추적해서 강제 종료 시 재생을 중단할 수 있게 한다.
    """
    global _play_process

    creationflags = 0
    if platform.system() == "Windows":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        stop_tts()

        process = subprocess.Popen(
            [
                FFPLAY_PATH,
                "-nodisp",
                "-autoexit",
                "-loglevel",
                "quiet",
                output_path,
            ],
            creationflags=creationflags,
        )

        with _play_lock:
            _play_process = process

        return_code = process.wait()

        with _play_lock:
            if _play_process is process:
                _play_process = None

        if return_code != 0:
            log_error(f"[TTS ERROR] ffplay 재생 실패: returncode={return_code}")
            return False

        return True

    except FileNotFoundError:
        log_warn("[TTS WARN] ffplay를 찾을 수 없습니다.")
        return _play_audio_with_mci(output_path)

    except Exception as e:
        with _play_lock:
            _play_process = None
        log_error(f"[TTS ERROR] ffplay 재생 실패: {e}")
        return False


def speak(text: str, on_play_start=None):
    if not text:
        return

    log_simple(f"[BMO] {text}")

    text_for_voice = clean_for_tts(text)

    if not text_for_voice:
        return

    if not USE_TTS:
        if on_play_start:
            log_debug("[SYNC] TTS 비활성 상태 - SPEAK 전환")
            on_play_start()
        time.sleep(1)
        return

    output_path = None
    _speak_lock.acquire()

    try:
        fd, output_path = tempfile.mkstemp(
            prefix="bmo_edge_tts_",
            suffix=".mp3"
        )
        os.close(fd)

        start_time = time.time()

    # 1. 먼저 TTS 음성 파일 생성
        _generate_edge_tts(text_for_voice, output_path)

        tts_time = time.time() - start_time
        log_simple(f"[TTS] {tts_time:.2f}s")

    # 2. 실제 음성 재생 직전에 얼굴을 SPEAK 상태로 변경
        if on_play_start:
            log_debug("[SYNC] 실제 음성 재생 시작 - SPEAK 전환")
            on_play_start()

    # 3. 오디오 재생
        _play_audio(output_path)

    except Exception as e:
        log_error(f"[TTS ERROR] {e}")
        time.sleep(1.5)

    finally:
        if output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError as e:
                log_warn(f"[TTS WARN] 임시 파일 삭제 실패: {e}")

        _speak_lock.release()
