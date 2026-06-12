# bmoAPI.py
# ollama 호출 담당 파이썬 코드
import json
import re
import time
import requests
from logger import log_simple, log_debug, log_trace, log_warn, log_error
from config.settings import ENABLE_OLLAMA_WARMUP, OLLAMA_WARMUP_PROMPT

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gemma4:e2b-it-qat"

OLLAMA_OPTIONS = {
    "num_predict": 80,
    "temperature": 0.7,
    "top_p": 0.9,
    "repeat_penalty": 1.2,
    "num_ctx": 512
}

OLLAMA_TIMEOUT = 90

SYSTEM_PROMPT = """
너는 비모야. AI 친구. 한국어 반말 1~2문장.
다정하되 짧게. 힘들면 다정하게, 기쁘면 같이 기뻐해. 이모지·존댓말·역질문 금지. 추천엔 바로 답해.
JSON만 반환: {“emotion”:”neutral”,”confidence”:0.0,”reply”:”답변”}
emotion: neutral/happy/sad/angry. confidence: 0.0~1.0.
"""

MAX_HISTORY = 4

chat_history = []


def clean_llm_response(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"[^\w\s가-힣.,!?~]", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_json_object(text: str) -> dict:
    if not text:
        return {}

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or start >= end:
        return {}

    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def normalize_llm_emotion(emotion: str) -> str:
    if emotion in ["happy", "sad", "angry", "neutral"]:
        return emotion

    return "neutral"


def normalize_confidence(confidence) -> float:
    try:
        value = float(confidence or 0.0)
    except (TypeError, ValueError):
        value = 0.0

    return max(0.0, min(value, 1.0))


def strip_wrapping_quotes(text: str) -> str:
    if not text:
        return ""

    return text.strip().strip("\"'{} ")


def extract_loose_field(text: str, field: str, next_fields: list[str]) -> str:
    if not text:
        return ""

    next_pattern = "|".join(next_fields)
    pattern = rf'["\']?{field}["\']?\s*[:=]?\s*(.*?)(?=,\s*(?:{next_pattern})\b|$|}})'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

    if not match:
        return ""

    return strip_wrapping_quotes(match.group(1))


def parse_loose_bmo_response(raw_content: str) -> dict:
    if not raw_content:
        return {}

    emotion = extract_loose_field(
        raw_content,
        "emotion",
        ["confidence", "reply"]
    )
    confidence = extract_loose_field(
        raw_content,
        "confidence",
        ["emotion", "reply"]
    )
    reply = extract_loose_field(
        raw_content,
        "reply",
        ["emotion", "confidence"]
    )

    if not reply:
        return {}

    return {
        "emotion": normalize_llm_emotion(emotion),
        "confidence": normalize_confidence(confidence),
        "reply": reply
    }


def looks_like_structured_response(text: str) -> bool:
    if not text:
        return False

    lowered = text.lower()
    return (
        "emotion" in lowered
        or "confidence" in lowered
        or "reply" in lowered
    )


def build_bmo_result(reply: str, emotion="neutral", confidence=0.0, source="fallback") -> dict:
    return {
        "reply": clean_llm_response(reply),
        "emotion": normalize_llm_emotion(emotion),
        "confidence": normalize_confidence(confidence),
        "source": source
    }


def parse_bmo_response(raw_content: str) -> dict:
    parsed = extract_json_object(raw_content)

    if not parsed:
        parsed = parse_loose_bmo_response(raw_content)

    if not parsed:
        if looks_like_structured_response(raw_content):
            log_warn("[OLLAMA WARN] 구조화 응답 파싱 실패, 안전 응답으로 대체")
            return build_bmo_result(
                "내가 대답을 조금 이상하게 정리했어. 다시 말해줄래?",
                source="structured_parse_failed"
            )

        log_warn("[OLLAMA WARN] JSON 파싱 실패, 일반 문장으로 처리")
        return build_bmo_result(raw_content, source="plain_text_fallback")

    reply = parsed.get("reply", "")
    emotion = normalize_llm_emotion(parsed.get("emotion", "neutral"))
    confidence = parsed.get("confidence", 0.0)

    if not reply:
        log_warn("[OLLAMA WARN] JSON reply 비어 있음")
        return build_bmo_result("", emotion=emotion, confidence=confidence, source="empty_reply")

    return build_bmo_result(
        reply,
        emotion=emotion,
        confidence=confidence,
        source="llm_structured"
    )


def get_response_body(response) -> str:
    try:
        return response.text.strip()
    except Exception:
        return ""


def log_ollama_http_error(response, elapsed: float):
    body = get_response_body(response)
    if body:
        log_error(
            f"[ERROR] Ollama HTTP {response.status_code}: {elapsed:.2f}s, "
            f"응답본문={body[:500]}"
        )
    else:
        log_error(f"[ERROR] Ollama HTTP {response.status_code}: {elapsed:.2f}s")

def warmup_ollama() -> bool:
    """
    프로그램 시작 시 Ollama 모델을 미리 로딩한다.

    중요:
    - 사용자 대화용 chat_history에는 기록하지 않는다.
    - warmup 응답은 TTS 또는 GUI 응답으로 출력하지 않는다.
    - 실패하더라도 프로그램 실행은 계속된다.
    - Raspberry Pi 5에서도 부담을 줄이기 위해 출력 토큰 수를 최소화한다.
    """
    if not ENABLE_OLLAMA_WARMUP:
        log_debug("[WARMUP] Ollama warmup 비활성화")
        return False

    warmup_payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": f"{OLLAMA_WARMUP_PROMPT}\n/no_think"
            }
        ],
        "stream": False,
        "think": False,
        "options": {
            "num_predict": 1,
            "temperature": 0.0,
            "num_ctx": OLLAMA_OPTIONS.get("num_ctx", 1024)
        }
    }

    start_time = time.time()
    log_simple("[WARMUP] Ollama 모델 준비 시작")

    try:
        response = requests.post(
            OLLAMA_URL,
            json=warmup_payload,
            timeout=OLLAMA_TIMEOUT
        )

        elapsed = time.time() - start_time

        if not response.ok:
            log_ollama_http_error(response, elapsed)

        response.raise_for_status()

        log_simple(f"[WARMUP] Ollama 모델 준비 완료: {elapsed:.2f}s")
        return True

    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        log_warn(
            f"[WARMUP WARN] Ollama 모델 준비 시간 초과: "
            f"{elapsed:.2f}s / limit={OLLAMA_TIMEOUT}s"
        )

    except requests.exceptions.ConnectionError as e:
        elapsed = time.time() - start_time
        log_warn(f"[WARMUP WARN] Ollama 서버 연결 실패: {elapsed:.2f}s, {e}")

    except requests.RequestException as e:
        elapsed = time.time() - start_time
        log_warn(f"[WARMUP WARN] Ollama 모델 준비 요청 실패: {elapsed:.2f}s, {e}")

    except Exception as e:
        elapsed = time.time() - start_time
        log_warn(f"[WARMUP WARN] 예상하지 못한 warmup 오류: {elapsed:.2f}s, {e}")

    return False

def should_retry_without_strict_json(response) -> bool:
    return response.status_code >= 500


def ask_bmo(user_input: str, emotion_prompt: str = "", stt_needs_caution=False) -> dict:
    global chat_history
    request_start = time.time()

    full_system_prompt = SYSTEM_PROMPT.strip()

    if emotion_prompt:
        full_system_prompt += (
            "\n\n룰 기반 1차 감정 힌트:\n"
            + emotion_prompt.strip()
            + "\n이 힌트는 참고만 하고, 최종 emotion은 사용자 문맥을 보고 직접 판단해."
        )

    messages = [
        {"role": "system", "content": full_system_prompt}
    ]

    messages.extend(chat_history)

    user_content = user_input

    if stt_needs_caution:
        user_content = (
            "이 문장은 STT 음성 인식 결과라 일부 단어가 틀렸을 수 있다.\n"
            "의미가 불분명하면 단정하지 말고 자연스럽게 다시 물어봐라.\n"
            f"STT 결과: {user_input}"
        )

    messages.append({
        "role": "user",
        "content": user_content + "\n/no_think"
    })

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "think": False,
        "format": "json",
        "options": OLLAMA_OPTIONS
    }

    try:
        log_trace("\n--- Ollama 요청 로그 ---")
        log_trace(f"[OLLAMA TRACE] url={OLLAMA_URL}")
        log_trace(f"[OLLAMA TRACE] model={MODEL_NAME}")
        log_trace(f"[OLLAMA TRACE] timeout={OLLAMA_TIMEOUT}s")
        log_trace(f"[OLLAMA TRACE] history_messages={len(chat_history)}")
        log_trace(f"[OLLAMA TRACE] total_messages={len(messages)}")
        log_debug(f"[OLLAMA DEBUG] emotion_prompt={'yes' if emotion_prompt else 'no'}")
        log_debug(f"[OLLAMA DEBUG] stt_needs_caution={stt_needs_caution}")
        log_trace(f"[OLLAMA TRACE] user_text_length={len(user_input)}")
        log_trace(f"[OLLAMA TRACE] options={OLLAMA_OPTIONS}")

        post_start = time.time()
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=OLLAMA_TIMEOUT
        )
        post_elapsed = time.time() - post_start
        log_debug(f"[OLLAMA DEBUG] response_received={post_elapsed:.2f}s")

        if not response.ok:
            log_ollama_http_error(response, time.time() - request_start)

            if should_retry_without_strict_json(response):
                retry_payload = dict(payload)
                retry_payload.pop("format", None)
                retry_payload.pop("think", None)

                log_warn("[OLLAMA WARN] 엄격한 JSON 요청 실패, format/think 없이 재시도합니다")
                retry_start = time.time()
                response = requests.post(
                    OLLAMA_URL,
                    json=retry_payload,
                    timeout=OLLAMA_TIMEOUT
                )
                log_debug(f"[OLLAMA DEBUG] retry_response_received={time.time() - retry_start:.2f}s")

                if not response.ok:
                    log_ollama_http_error(response, time.time() - request_start)

        response.raise_for_status()
        log_trace(f"[OLLAMA TRACE] status_code={response.status_code}")

        parse_start = time.time()
        data = response.json()
        parse_elapsed = time.time() - parse_start
        log_trace(f"[OLLAMA TRACE] json_parse={parse_elapsed:.2f}s")

        raw_content = data["message"]["content"].strip()
        bmo_result = parse_bmo_response(raw_content)
        total_elapsed = time.time() - request_start
        log_simple(f"[LLM] {total_elapsed:.2f}s / parse={bmo_result.get('source')}")
        log_debug(
            "[LLM DEBUG] "
            f"emotion={bmo_result.get('emotion')}, "
            f"confidence={bmo_result.get('confidence'):.2f}, "
            f"fallback={bmo_result.get('source') != 'llm_structured'}"
        )
        log_trace(f"[OLLAMA TRACE] raw_response_length={len(raw_content)}")
        log_trace(f"[OLLAMA TRACE] reply_length={len(bmo_result.get('reply', ''))}")

        chat_history.append({
            "role": "user",
            "content": user_input
        })

        chat_history.append({
            "role": "assistant",
            "content": bmo_result.get("reply", "")
        })

        chat_history = chat_history[-MAX_HISTORY:]

        return bmo_result

    except requests.exceptions.Timeout:
        elapsed = time.time() - request_start
        log_error(f"[ERROR] Ollama 응답 시간 초과: {elapsed:.2f}s / limit={OLLAMA_TIMEOUT}s")
        return build_bmo_result(
            "생각이 너무 오래 걸렸어. 다시 한 번 말해줄래?",
            source="timeout"
        )

    except requests.exceptions.ConnectionError as e:
        elapsed = time.time() - request_start
        log_error(f"[ERROR] Ollama 서버 연결 실패: {elapsed:.2f}s, {e}")
        return build_bmo_result(
            "지금 머리랑 연결이 끊긴 것 같아. Ollama가 켜져 있는지 확인해줘.",
            source="connection_error"
        )

    except requests.RequestException as e:
        elapsed = time.time() - request_start
        response = getattr(e, "response", None)
        if response is not None:
            body = get_response_body(response)
            log_error(f"[ERROR] API 요청 실패: {elapsed:.2f}s, {e}, 응답본문={body[:500]}")
        else:
            log_error(f"[ERROR] API 요청 실패: {elapsed:.2f}s, {e}")
        return build_bmo_result(
            "지금 연결 설정이 잘못된 것 같아. 다시 시도해줘.",
            source="request_error"
        )

    except KeyError as e:
        elapsed = time.time() - request_start
        log_error(f"[ERROR] 응답 형식 이상: {elapsed:.2f}s, {e}")
        log_trace(f"[DEBUG] 응답 데이터: {data}")
        return build_bmo_result("응답 형식이 이상해.", source="bad_response")