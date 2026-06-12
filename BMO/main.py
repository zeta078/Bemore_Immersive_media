import threading
import time
import os
import re
import keyboard
from queue import Empty, Queue
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from bmoAPI import ask_bmo, warmup_ollama
from mic import record_audio
from stt import speech_to_text, is_rest_command
from tts import speak, stop_tts
from ui.bmo_face import BMOFace
from commands.bmo_responses import get_response
from commands.speech_commands import (
    contains_wake_word,
    detect_command_intent,
    normalize_text as normalize_command_text,
    remove_wake_word,
)
from brain.bmo_brain import analyze_user_text
from features.weather.weather_service import handle_weather
from logger import log_simple, log_debug, log_trace, log_warn, log_error
from db_bridge import *
from backend_client import BackendClient as _BackendClient
_backend_client = _BackendClient()

from config.states import (
    STATE_SLEEP,
    STATE_WAKE,
    STATE_IDLE,
    STATE_LISTEN,
    STATE_THINK,
    STATE_SPEAK,
    EMOTION_NEUTRAL,
    EMOTION_HAPPY,
    EMOTION_SAD,
    EMOTION_ANGRY,
    EMOTION_LONELY,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_PATH = os.path.join(BASE_DIR, "input.wav")

gui = None
face_update_queue = Queue()
ui_action_queue = Queue()

last_recommendation_text = ""

current_state = STATE_SLEEP
current_emotion = EMOTION_NEUTRAL
previous_emotion = EMOTION_NEUTRAL
sleep_touch_wake_event = threading.Event()
_return_narrate_active = threading.Event()

# 감정 여운 시간
EMOTION_HOLD_TIME = {
    EMOTION_HAPPY: 2.0,
    EMOTION_SAD: 4.0,
    EMOTION_ANGRY: 2.5
}

emotion_timer_id = 0

STT_CONFIDENCE_THRESHOLD = 0.55
EMOTION_CONFIDENCE_THRESHOLD = 0.55
LLM_EMOTION_CONFIDENCE_THRESHOLD = 0.45

STT_REASK_MESSAGE = "방금은 조금 잘 못 들었어. 다시 한 번 말해줄래?"
WAKE_SILENCE_LIMIT = 0.6
WAKE_MAX_RECORD_TIME = 2.2
WAKE_PRE_SPEECH_BLOCKS = 4
WAKE_FACE_HOLD_TIME = 0.25

FEATURE_SCREEN_INTENTS = {
    "photo_analysis": "camera",
    "fridge": "fridge",
    # "recommend"는 clear_selected_recipe() 선처리 필요 -> 아래 intent 블록에서 직접 처리
    # "recipe"는 음성으로만 응답 -> 아래 intent 블록에서 직접 처리
    "minigame": "minigame",
    "open_camera": "camera",
    "view_inventory": "fridge",
    "recommend_recipe": "recipe",
    "open_minigame": "minigame",
}

FEATURE_SCREEN_CONFIRM_MESSAGES = {
    "camera": "카메라 화면을 보여줄게.",
    "fridge": "냉장고 화면을 보여줄게.",
    "recipe": "레시피 화면을 보여줄게.",
    "minigame": "미니게임 화면을 보여줄게.",
}

def force_exit():
    log_warn("\n[강제 종료]")
    stop_tts()
    os._exit(0)


def normalize_emotion(emotion):
    if emotion == EMOTION_LONELY:
        return EMOTION_SAD

    if emotion in [EMOTION_HAPPY, EMOTION_SAD, EMOTION_ANGRY]:
        return emotion

    return EMOTION_NEUTRAL


def is_real_emotion(emotion):
    emotion = normalize_emotion(emotion)
    return emotion in [EMOTION_HAPPY, EMOTION_SAD, EMOTION_ANGRY]


def set_face(face_state):
    if not gui:
        return

    root = getattr(gui, "root", None)
    if root is None:
        log_warn("[UI WARN] Tk 루트가 아직 준비되지 않아 얼굴 상태 변경을 건너뜁니다")
        return

    face_update_queue.put(face_state)


def process_face_updates():
    if not gui:
        return

    root = getattr(gui, "root", None)
    if root is None:
        log_warn("[UI WARN] Tk 루트가 아직 준비되지 않아 얼굴 상태 변경 처리를 건너뜁니다")
        return

    try:
        while True:
            face_state = face_update_queue.get_nowait()
            gui.set_state(face_state)
    except Empty:
        pass
    except Exception as e:
        log_warn(f"[UI WARN] 얼굴 상태 변경 실패: {e}")

    root.after(16, process_face_updates)


def process_ui_actions():
    if not gui:
        return

    root = getattr(gui, "root", None)
    if root is None:
        log_warn("[UI WARN] Tk 루트가 아직 준비되지 않아 UI 액션 처리를 건너뜁니다")
        return

    try:
        while True:
            action, payload, done_event = ui_action_queue.get_nowait()

            try:
                if action == "open_feature_screen":
                    gui.open_feature_screen(payload)
                elif action == "close_feature_screen":
                    gui.close_current_feature_screen()
                elif action == "show_weather_icon":
                    gui.show_weather_icon(payload)
                elif action == "set_mic_muted":
                    gui.set_mic_muted(bool(payload))
            except Exception as e:
                log_warn(f"[UI WARN] UI 액션 처리 실패: {e}")
            finally:
                if done_event is not None:
                    done_event.set()
    except Empty:
        pass

    root.after(16, process_ui_actions)


def request_feature_screen(screen_name):
    if not gui:
        return False

    done_event = threading.Event()
    ui_action_queue.put(("open_feature_screen", screen_name, done_event))

    if not done_event.wait(timeout=1.0):
        log_warn(f"[UI WARN] 기능 화면 전환 대기 시간 초과: {screen_name}")
        return False

    return True


def request_close_feature_screen():
    if not gui:
        return False

    done_event = threading.Event()
    ui_action_queue.put(("close_feature_screen", None, done_event))

    if not done_event.wait(timeout=1.0):
        log_warn("[UI WARN] 기능 화면 닫기 대기 시간 초과")
        return False

    return True


def request_weather_icon(icon_name):
    if not gui or not icon_name:
        return

    ui_action_queue.put(("show_weather_icon", icon_name, None))


def request_mic_muted(muted):
    if not gui:
        return False

    done_event = threading.Event()
    ui_action_queue.put(("set_mic_muted", muted, done_event))

    if not done_event.wait(timeout=1.0):
        log_warn("[UI WARN] 마이크 음소거 상태 변경 대기 시간 초과")
        return False

    return True


def request_sleep_touch_wake():
    if current_state == STATE_SLEEP:
        log_debug("[TOUCH WAKE] 수면 상태에서 화면 터치 감지")
        sleep_touch_wake_event.set()


def narrate_on_screen(text):
    """
    기능 화면을 유지한 채 짧은 안내 음성만 재생한다.
    얼굴 상태 전환은 하지 않는다.
    """
    if not text:
        return

    threading.Thread(target=speak, args=(text,), daemon=True).start()


def narrate_after_return(text):
    """
    메인 얼굴 화면 복귀 후 기존 speak -> idle 흐름으로 짧은 안내를 재생한다.
    """
    if not text:
        return

    _return_narrate_active.set()

    def _run():
        try:
            speak_with_face(text, after_state=STATE_IDLE)
            time.sleep(2.2)  # SILENCE_LIMIT(2.0) 초과 대기 후 해제
        finally:
            _return_narrate_active.clear()

    threading.Thread(target=_run, daemon=True).start()


def get_feature_screen_for_intent(intent):
    return FEATURE_SCREEN_INTENTS.get(intent)


def get_voice_mode():
    if not gui:
        return "full_chat"

    mode_getter = getattr(gui, "get_voice_mode", None)
    if mode_getter is None:
        return "full_chat"

    return mode_getter()


def is_voice_input_enabled():
    if not gui:
        return True

    return get_voice_mode() != "muted"


def is_inactivity_sleep_allowed():
    if not gui:
        return True

    return getattr(gui, "current_screen", "face") == "face"


def is_main_face_screen():
    if not gui:
        return True

    return getattr(gui, "current_screen", "face") == "face"


def get_weather_icon_name(weather_id):
    if weather_id is None:
        return None

    if 200 <= weather_id < 300:
        return "weather_thunderstorm.png"

    if 300 <= weather_id < 600:
        return "weather_rain.png"

    if 600 <= weather_id < 700:
        return "weather_snow.png"

    if 700 <= weather_id < 800:
        return "weather_clouds.png"

    if weather_id == 800:
        return "weather_clear.png"

    if 801 <= weather_id < 900:
        return "weather_clouds.png"

    return None


def handle_weather_request(user_text: str = ""):
    response, weather_id = handle_weather(user_text)
    request_weather_icon(get_weather_icon_name(weather_id))
    speak_with_emotion(response, EMOTION_NEUTRAL)


def is_weather_request_text(text):
    normalized = normalize_command_text(text)
    weather_keywords = [
        "날씨",
        "기온",
        "온도",
        "우산",
        "비 와",
        "비와",
        "추워",
        "더워",
    ]
    return any(keyword in normalized for keyword in weather_keywords)


def wait_until_voice_input_enabled():
    logged = False

    while not is_voice_input_enabled() or _return_narrate_active.is_set():
        if not logged:
            log_debug("[VOICE] 음성 입력 차단 중 - 새 STT 시작 대기")
            logged = True
        time.sleep(0.2)


def handle_recording_start():
    if not is_voice_input_enabled():
        log_debug("[VOICE] 입력 차단 상태에서 말소리 감지를 무시")
        return

    if get_voice_mode() == "exit_only":
        log_debug("[VOICE] exit_only 화면에서는 listen 표정 전환을 생략")
        return

    change_state(STATE_LISTEN)


def detect_exit_screen_intent(text):
    normalized = remove_wake_word(normalize_command_text(text))
    return detect_command_intent(normalized) == "exit_screen"


def handle_exit_only_stt(stt_result):
    user_text = stt_result.get("corrected_text", "")
    log_simple(f"[STT:EXIT_ONLY] {user_text}")

    if not user_text:
        return

    if detect_exit_screen_intent(user_text):
        log_simple("[VOICE NAV] exit_only -> face")
        request_close_feature_screen()
        return

    log_debug("[VOICE] exit_only 화면에서 나가기 의도가 아닌 발화를 무시")


def update_face():
    emotion = normalize_emotion(current_emotion)

    if current_state in [STATE_WAKE, STATE_THINK]:
        set_face(current_state)
        return

    if current_state in [STATE_SLEEP, STATE_LISTEN]:
        if emotion == EMOTION_NEUTRAL:
            set_face(current_state)
        else:
            set_face(emotion)
        return

    if current_state == STATE_SPEAK:
        if emotion == EMOTION_NEUTRAL:
            set_face(STATE_SPEAK)
        else:
            set_face(f"speak_{emotion}")
        return

    if current_state == STATE_IDLE:
        if emotion == EMOTION_NEUTRAL:
            set_face(STATE_IDLE)
        else:
            set_face(emotion)
        return

    set_face(current_state)


def change_state(state):
    global current_state

    previous_state = current_state
    current_state = state
    if previous_state == current_state:
        log_debug(f"[STATE] {previous_state} -> {current_state}")
    else:
        log_simple(f"[STATE] {previous_state} -> {current_state}")
    update_face()


def change_emotion(emotion):
    """
    감정 변경 함수.

    중요:
    - happy/sad/angry 같은 실제 감정은 current_emotion과 previous_emotion에 저장한다.
    - neutral은 이전 감정을 다시 불러오지 않는다.
    - 그래야 neutral 입력이 들어올 때마다 sad/angry 여운이 계속 연장되지 않는다.
    """
    global current_emotion, previous_emotion

    emotion = normalize_emotion(emotion)

    if emotion == EMOTION_NEUTRAL:
        current_emotion = EMOTION_NEUTRAL
    else:
        current_emotion = emotion
        previous_emotion = emotion

    log_debug(f"[EMOTION] -> {current_emotion}")
    update_face()


def reset_emotion():
    global current_emotion, previous_emotion

    current_emotion = EMOTION_NEUTRAL
    previous_emotion = EMOTION_NEUTRAL
    log_debug(f"[EMOTION] -> {current_emotion}")
    update_face()


def start_emotion_decay():
    global emotion_timer_id, previous_emotion

    emotion = normalize_emotion(current_emotion)

    if emotion == EMOTION_NEUTRAL:
        return

    emotion_timer_id += 1
    my_timer_id = emotion_timer_id

    hold_time = EMOTION_HOLD_TIME.get(emotion, 3.0)

    def decay():
        global previous_emotion

        time.sleep(hold_time)

        if my_timer_id != emotion_timer_id:
            return

        if current_state == STATE_IDLE:
            previous_emotion = EMOTION_NEUTRAL
            reset_emotion()

    threading.Thread(target=decay, daemon=True).start()


def speak_with_face(text, after_state=STATE_IDLE):
    if not text:
        return

    log_debug("[SYNC] TTS 준비 시작 - 화면은 THINK 유지")
    start_time = time.time()

    speak(text, on_play_start=lambda: change_state(STATE_SPEAK))

    total_time = time.time() - start_time
    log_debug(f"[SYNC] TTS 준비+재생 전체 완료: {total_time:.2f}s")

    time.sleep(0.7)

    if after_state:
        change_state(after_state)


def speak_with_emotion(text, emotion, after_state=STATE_IDLE):
    """
    감정이 있는 응답은 감정 표정으로 말하고,
    neutral 응답은 현재 감정 여운을 강제로 다시 연장하지 않는다.
    """
    if not text:
        return

    emotion = normalize_emotion(emotion)

    # 실제 감정일 때만 감정 표정 적용
    if is_real_emotion(emotion):
        change_emotion(emotion)
    else:
        change_emotion(EMOTION_NEUTRAL)

    change_state(STATE_SPEAK)
    speak(text)
    time.sleep(0.7)

    if after_state:
        change_state(after_state)

        # 실제 감정 응답일 때만 여운 타이머 시작
        if is_real_emotion(emotion):
            start_emotion_decay()


def wake_sequence():
    reset_emotion()
    change_state(STATE_WAKE)
    time.sleep(WAKE_FACE_HOLD_TIME)
    change_state(STATE_IDLE)


def enter_sleep_and_wait(return_response_key="sleep_return"):
    reset_emotion()
    sleep_touch_wake_event.clear()
    change_state(STATE_SLEEP)
    log_debug("BMO 수면 상태...")

    while True:
        logged_voice_block = False

        while not is_voice_input_enabled() and not sleep_touch_wake_event.is_set():
            if not logged_voice_block:
                log_debug("[VOICE] 음성 입력 차단 중 - wake 호출어 대기 일시 정지")
                logged_voice_block = True
            time.sleep(0.2)

        if sleep_touch_wake_event.is_set():
            log_debug("[TOUCH WAKE] 터치 입력으로 수면 해제")
            break

        audio_file = record_audio(
            AUDIO_PATH,
            silence_limit=WAKE_SILENCE_LIMIT,
            max_record_time=WAKE_MAX_RECORD_TIME,
            pre_speech_blocks=WAKE_PRE_SPEECH_BLOCKS,
            should_stop=sleep_touch_wake_event.is_set
        )

        if sleep_touch_wake_event.is_set():
            log_debug("[TOUCH WAKE] 터치 입력으로 수면 해제")
            break

        if not is_voice_input_enabled():
            log_debug("[VOICE] 입력 차단 상태에서 감지된 깨우기 신호를 무시")
            continue

        if not audio_file:
            continue

        stt_result = speech_to_text(audio_file)
        wake_text = stt_result.get("corrected_text", "")
        log_simple(f"[WAKE STT] {wake_text}")

        if contains_wake_word(wake_text):
            break

        log_debug("[WAKE] 호출어가 없어 수면 상태를 유지")
        change_state(STATE_SLEEP)

    sleep_touch_wake_event.clear()
    wake_sequence()
    speak_with_face(get_response(return_response_key))


def get_llm_style(emotion, style):
    """
    LLM에 넘길 감정 지침을 정리한다.

    핵심:
    - 현재 입력 감정이 neutral이면 감정 프롬프트를 보내지 않는다.
    - 그래야 이전 sad/angry 여운이 LLM 답변까지 계속 오염시키지 않는다.
    """
    emotion = normalize_emotion(emotion)

    if emotion == EMOTION_NEUTRAL:
        return ""

    return style or ""


def print_analysis_log(stt_result, brain_result, llm_will_call):
    log_debug(f"[STT DEBUG] raw={stt_result.get('raw_text', '')}")
    log_debug(f"[STT DEBUG] corrected={stt_result.get('corrected_text', '')}")
    log_debug(
        "[STT DEBUG] "
        f"lang={stt_result.get('language', '')}, "
        f"conf={stt_result.get('confidence', 0.0):.2f}, "
        f"level={stt_result.get('uncertainty_level', '')}, "
        f"correction={stt_result.get('correction_applied', False)}"
    )
    log_debug(
        "[FLOW DEBUG] "
        f"llm_call={llm_will_call}, "
        f"blocked={stt_result.get('blocked_reason', '')}"
    )
    log_trace(f"[EMOTION TRACE] emotion={brain_result.get('emotion', EMOTION_NEUTRAL)}")
    log_trace(f"[EMOTION TRACE] confidence={brain_result.get('emotion_confidence', 0.0):.2f}")
    log_trace(f"[EMOTION TRACE] scores={brain_result.get('emotion_scores', {})}")
    log_trace(f"[EMOTION TRACE] reasons={brain_result.get('emotion_reasons', [])}")
    log_trace(f"[INTENT TRACE] intent={brain_result.get('intent', 'chat')}")


def should_ask_again(stt_result, brain_result):
    emotion = normalize_emotion(brain_result.get("emotion", EMOTION_NEUTRAL))
    emotion_confidence = brain_result.get("emotion_confidence", 0.0)

    if emotion != EMOTION_NEUTRAL and emotion_confidence < EMOTION_CONFIDENCE_THRESHOLD:
        log_debug("[CONFIDENCE] 감정 판단 confidence 낮음")
        return True

    return False


def build_neutral_brain_result(reason):
    return {
        "emotion": EMOTION_NEUTRAL,
        "emotion_confidence": 0.0,
        "emotion_scores": {},
        "emotion_reasons": [reason],
        "intent": "chat",
        "style": ""
    }


def choose_response_emotion(rule_emotion, llm_result):
    llm_emotion = normalize_emotion(llm_result.get("emotion", EMOTION_NEUTRAL))
    llm_confidence = llm_result.get("confidence", 0.0)

    log_debug(
        "[EMOTION DEBUG] "
        f"llm={llm_emotion}, "
        f"conf={llm_confidence:.2f}, "
        f"source={llm_result.get('source', '')}, "
        f"rule={rule_emotion}"
    )

    if llm_emotion != EMOTION_NEUTRAL and llm_confidence >= LLM_EMOTION_CONFIDENCE_THRESHOLD:
        log_debug("[EMOTION SELECT] LLM 감정 사용")
        return llm_emotion

    if rule_emotion != EMOTION_NEUTRAL:
        log_debug("[EMOTION SELECT] 룰 기반 감정 fallback 사용")
        return rule_emotion

    log_debug("[EMOTION SELECT] neutral 사용")
    return EMOTION_NEUTRAL


def extract_recipe_name_from_response(response_text, candidates=None):
    candidates = candidates or []

    for name in candidates:
        if name and name in response_text:
            return name

    patterns = [
        r"음식\s*이름\s*[:：]\s*([^\n,]+)",
        r"음식명\s*[:：]\s*([^\n,]+)",
        r"레시피\s*이름\s*[:：]\s*([^\n,]+)",
        r"요리\s*이름\s*[:：]\s*([^\n,]+)",
        r"^\s*\d+\.\s*([^\n:：]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, response_text)
        if match:
            return match.group(1).strip()

    return candidates[0] if candidates else ""


def conversation_loop():
    """
    BMO의 전체 음성 대화 루프.

    GUI가 먼저 실행된 뒤 별도 스레드에서 이 함수가 동작하므로,
    warmup 중에도 화면 자체는 정상적으로 표시된다.
    warmup이 끝난 뒤에만 실제 음성 대기를 시작하여
    첫 사용자 입력과 Ollama 준비 요청이 겹치지 않도록 한다.
    """
    global last_recommendation_text
    change_state(STATE_SLEEP)
    warmup_ollama()

    enter_sleep_and_wait(return_response_key="wake")

    while True:
        log_debug("\n--- 대기 중 ---")
        if get_voice_mode() != "exit_only":
            change_state(STATE_IDLE)

        wait_until_voice_input_enabled()

        audio_file = record_audio(
            AUDIO_PATH,
            on_start=handle_recording_start,
            wait_timeout=15
        )

        if not is_voice_input_enabled():
            log_debug("[VOICE] 입력 차단 상태에서 종료된 녹음 결과를 처리하지 않음")
            continue

        if audio_file and _return_narrate_active.is_set():
            log_debug("[VOICE] 복귀 TTS 재생 중 녹음된 오디오 무시")
            continue

        if not audio_file:
            if not is_inactivity_sleep_allowed():
                log_debug("[SLEEP] 기능 화면에서는 무응답 수면 복귀를 건너뜁니다")
                continue

            speak_with_face(get_response("sleep_notice"), after_state=None)
            time.sleep(0.3)

            enter_sleep_and_wait(return_response_key="sleep_return")
            continue

        if get_voice_mode() == "exit_only":
            stt_result = speech_to_text(audio_file)

            if not is_voice_input_enabled():
                log_debug("[VOICE] 입력 차단 상태에서 종료된 exit_only STT 결과를 처리하지 않음")
                continue

            handle_exit_only_stt(stt_result)
            continue

        change_state(STATE_THINK)
        stt_result = speech_to_text(audio_file)

        if not is_voice_input_enabled():
            log_debug("[VOICE] 입력 차단 상태에서 종료된 STT 결과를 처리하지 않음")
            change_state(STATE_IDLE)
            continue

        user_text = stt_result.get("corrected_text", "")
        log_simple(f"[STT] {user_text}")

        if not stt_result.get("should_call_llm", False):
            reason = stt_result.get("blocked_reason", "stt_uncertain")
            brain_result = build_neutral_brain_result(reason)
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            speak_with_emotion(STT_REASK_MESSAGE, EMOTION_NEUTRAL)
            continue

        if not user_text:
            brain_result = build_neutral_brain_result("empty_text")
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            log_warn("음성이 인식되지 않았어.")
            speak_with_emotion(get_response("stt_fail"), EMOTION_NEUTRAL)
            continue

        if get_voice_mode() == "context_chat" and detect_exit_screen_intent(user_text):
            brain_result = build_neutral_brain_result("exit_screen")
            brain_result["intent"] = "exit_screen"
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            log_simple("[VOICE NAV] context_chat -> face")
            request_close_feature_screen()
            continue

        if is_rest_command(user_text):
            speak_with_face(get_response("rest"), after_state=None)
            time.sleep(0.3)

            enter_sleep_and_wait(return_response_key="sleep_return")
            continue

        if is_weather_request_text(user_text) and is_main_face_screen():
            brain_result = build_neutral_brain_result("weather_request")
            brain_result["intent"] = "weather"
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            handle_weather_request(user_text)
            continue

        brain_result = analyze_user_text(user_text)

        emotion = brain_result.get("emotion", EMOTION_NEUTRAL)
        intent = brain_result.get("intent", "chat")
        style = brain_result.get("style", "")

        if intent == "weather" and is_main_face_screen():
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            handle_weather_request(user_text)
            continue

        if intent == "mic-mute":
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            speak_with_emotion("마이크를 음소거할게.", EMOTION_NEUTRAL)
            request_mic_muted(True)
            change_state(STATE_IDLE)
            continue

        feature_screen = get_feature_screen_for_intent(intent)
        if feature_screen:
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            log_simple(f"[VOICE NAV] intent={intent} -> screen={feature_screen}")
            speak_with_emotion(
                FEATURE_SCREEN_CONFIRM_MESSAGES.get(
                    feature_screen,
                    "화면을 보여줄게."
                ),
                EMOTION_NEUTRAL
            )
            request_feature_screen(feature_screen)
            change_state(STATE_IDLE)
            continue

        emotion = normalize_emotion(emotion)
        llm_style = get_llm_style(emotion, style)

        if should_ask_again(stt_result, brain_result):
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            speak_with_emotion(
                "내가 제대로 알아들은 게 맞는지 잘 모르겠어. 한 번만 다시 말해줄래?",
                EMOTION_NEUTRAL
            )
            continue

        if intent == "add_ingredient":
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            change_state(STATE_THINK)

            # 발화에서 재료명과 수량 파싱
            # 예) "냉장고에 계란 10개 추가해줘", "양파 3개랑 당근 2개 넣어줘"
            import re as _re

            def _parse_ingredients_from_text(text: str) -> list:
                """
                텍스트에서 "재료명 N단위" 패턴을 추출한다.
                단위(g, kg, ml 등 포함), 수량이 없으면 1개로 처리.
                예) "돼지고기 300g 추가해줘" → [{"ingredient_name": "돼지고기", "quantity": 300.0, "unit": "g"}]
                    "계란 10개 추가해줘"     → [{"ingredient_name": "계란", "quantity": 10.0, "unit": "개"}]
                    "양파랑 당근 넣어줘"     → [{"ingredient_name": "양파", "quantity": 1.0, "unit": "개"}, ...]
                """
                from db_bridge import _UNIT_ALIASES

                # 불필요한 동사/조사 제거
                stopwords = [
                    "냉장고에", "냉장고", "추가해줘", "추가해", "넣어줘", "넣어",
                    "등록해줘", "등록해", "추가", "넣기", "해줘", "줘", "좀",
                ]
                cleaned = text
                for sw in stopwords:
                    cleaned = cleaned.replace(sw, " ")

                # 재료명 뒤 조사 제거
                cleaned = _re.sub(r"([가-힣])(이랑|랑|과|와|을|를|은|는|이|가)(\s|$)", r"\1 ", cleaned)

                UNIT_PAT = r"(g|kg|ml|l|L|그램|킬로그램|킬로|밀리리터|밀리|리터|개|마리|봉지|봉투?|팩|병|캔|통|장|묶음|알|컵|인분)"

                # "재료명 숫자단위" 패턴 (예: 돼지고기 300g, 우유 1L)
                pattern = _re.findall(
                    r"([가-힣a-zA-Z]+)\s*(\d+(?:\.\d+)?)\s*" + UNIT_PAT,
                    cleaned
                )
                result = []
                seen = set()
                for name, qty, unit in pattern:
                    name = name.strip()
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    unit = _UNIT_ALIASES.get(unit.lower().rstrip('투'), unit)
                    result.append({"ingredient_name": name, "quantity": float(qty), "unit": unit})

                # 단위 없이 숫자만 있는 경우 (예: 계란 10)
                if not result:
                    pattern2 = _re.findall(
                        r"([가-힣a-zA-Z]+)\s*(\d+(?:\.\d+)?)",
                        cleaned
                    )
                    for name, qty in pattern2:
                        name = name.strip()
                        if not name or name in seen:
                            continue
                        seen.add(name)
                        result.append({"ingredient_name": name, "quantity": float(qty), "unit": "개"})

                # 수량/단위 없는 재료 (예: 양파랑 당근)
                if not result:
                    names_only = _re.findall(r"([가-힣]{2,})", cleaned)
                    for name in names_only:
                        if name not in seen:
                            seen.add(name)
                            result.append({"ingredient_name": name, "quantity": 1.0, "unit": "개"})

                return result

            items = _parse_ingredients_from_text(user_text)

            if not items:
                speak_with_emotion("어떤 재료를 추가할지 다시 말해줄래? 예를 들어 '계란 10개 추가해줘' 처럼 말해줘.", EMOTION_NEUTRAL)
                continue

            saved = save_ingredient_items(items)

            if saved > 0:
                def _fmt(i):
                    qty = i['quantity']
                    qty_str = str(int(qty)) if qty == int(qty) else str(qty)
                    unit = i.get('unit', '개')
                    return f"{i['ingredient_name']} {qty_str}{unit}"
                names_str = ", ".join(_fmt(i) for i in items)
                speak_with_emotion(f"{names_str} 냉장고에 추가했어!", EMOTION_NEUTRAL)
                log_simple(f"[ADD INGREDIENT] 저장 완료: {items}")
            else:
                speak_with_emotion("재료 추가에 실패했어. 다시 시도해줘.", EMOTION_SAD)
                log_warn(f"[ADD INGREDIENT] 저장 실패: {items}")

            change_state(STATE_IDLE)
            continue

        if intent == "consume_ingredient":
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            change_state(STATE_THINK)

            import re as _re

            # "다" 키워드 감지 → 전량 삭제
            ALL_KEYWORDS = ["다 먹", "다 소비", "다 소모", "다 썼", "다 없", "다 떨어", "다 됐", "다 쓴"]
            is_all = any(kw in user_text for kw in ALL_KEYWORDS)

            # 재료명 + 수량 + 단위 파싱 (add_ingredient와 동일한 파서 재활용)
            def _parse_consume_from_text(text: str) -> list:
                """
                반환: [{"ingredient_name": str, "quantity": float, "unit": str, "all": bool}, ...]
                """
                stopwords = [
                    "냉장고에서", "냉장고", "소비했어", "소모했어", "다 먹었어", "다 썼어",
                    "소진했어", "먹었어", "먹어버렸어", "다 떨어졌어", "없어졌어", "써버렸어",
                    "해줘", "줘", "좀", "다",
                ]
                cleaned = text
                for sw in stopwords:
                    cleaned = cleaned.replace(sw, " ")

                cleaned = _re.sub(r"([가-힣])(이랑|랑|과|와|을|를|은|는|이|가)(\s|$)", r"\1 ", cleaned)

                UNIT_PAT = r"(g|kg|ml|l|L|그램|킬로그램|킬로|밀리리터|밀리|리터|개|봉지|봉투?|팩|병|캔|통|장|묶음|알|컵|인분|마리)"
                pattern = _re.findall(
                    r"([가-힣a-zA-Z]+)\s*(\d+(?:\.\d+)?)\s*" + UNIT_PAT,
                    cleaned
                )
                result = []
                seen = set()
                for name, qty, unit in pattern:
                    name = name.strip()
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    from db_bridge import _UNIT_ALIASES
                    unit = _UNIT_ALIASES.get(unit.lower(), unit)
                    result.append({"ingredient_name": name, "quantity": float(qty), "unit": unit, "all": False})

                # 수량 없는 재료 (전량 or 기본 1개)
                if not result:
                    names_only = _re.findall(r"([가-힣]{2,})", cleaned)
                    for name in names_only:
                        if name not in seen:
                            seen.add(name)
                            result.append({"ingredient_name": name, "quantity": 0.0, "unit": "개", "all": is_all})

                # 전량 플래그 보정
                if is_all:
                    for r in result:
                        r["all"] = True

                return result

            from db_bridge import consume_ingredient as _consume_ingredient, remove_ingredient_fully as _remove_fully

            items = _parse_consume_from_text(user_text)

            if not items:
                speak_with_emotion("어떤 재료를 소비했는지 다시 말해줄래? 예를 들어 '양파 3개 소모했어' 처럼 말해줘.", EMOTION_NEUTRAL)
                continue

            success_msgs = []
            fail_names = []

            for item in items:
                name = item["ingredient_name"]
                if item["all"] or item["quantity"] <= 0:
                    ok = _remove_fully(name)
                    if ok:
                        success_msgs.append(f"{name} 전량")
                    else:
                        fail_names.append(name)
                else:
                    result = _consume_ingredient(name, item["quantity"], item["unit"])
                    if result["success"]:
                        qty = item["quantity"]
                        qty_str = str(int(qty)) if qty == int(qty) else str(qty)
                        if result["removed_all"]:
                            success_msgs.append(f"{name} {qty_str}{item['unit']} (소진)")
                        else:
                            rem = result["remaining"]
                            rem_str = str(int(rem)) if rem == int(rem) else str(rem)
                            success_msgs.append(f"{name} {qty_str}{item['unit']} (남은 재고: {rem_str}{result['unit']})")
                    else:
                        fail_names.append(name)

            if success_msgs:
                speak_with_emotion(f"{', '.join(success_msgs)} 냉장고에서 차감했어!", EMOTION_NEUTRAL)
                log_simple(f"[CONSUME] 차감 완료: {success_msgs}")
            if fail_names:
                speak_with_emotion(f"{', '.join(fail_names)}은(는) 냉장고에서 찾지 못했어.", EMOTION_NEUTRAL)
                log_warn(f"[CONSUME] 차감 실패: {fail_names}")

            change_state(STATE_IDLE)
            continue

        if intent == "recommend":
            try:
                from features.recipe.recipe_service import clear_selected_recipe
                clear_selected_recipe()
            except Exception as _ce:
                log_warn(f"[RECIPE CACHE] clear 실패: {_ce}")
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            speak_with_emotion("레시피 추천해줄게.", EMOTION_HAPPY)
            request_feature_screen("recipe")
            change_state(STATE_IDLE)
            continue


        if intent == "rerecommend":
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            try:
                from features.recipe.recipe_service import get_last_recommended, set_exclude_next, clear_selected_recipe
                last = get_last_recommended()
                if last:
                    set_exclude_next(last)
                clear_selected_recipe()
            except Exception as _e:
                log_warn(f"[RERECOMMEND] 제외 목록 설정 실패: {_e}")
            speak_with_emotion("다른 레시피 추천해줄게.", EMOTION_HAPPY)
            request_feature_screen("recipe")
            change_state(STATE_IDLE)
            continue


        if intent == "recipe":
            print_analysis_log(stt_result, brain_result, llm_will_call=True)
            change_state(STATE_THINK)
            db_context = get_recipe_list_context()
            log_debug(f"[DB DEBUG] recipe_context={db_context}")

            augmented = f"{user_text}\n\n[레시피 정보]\n{db_context}"
            try:
                response_result = ask_bmo(
                    augmented,
                    emotion_prompt=llm_style,
                    stt_needs_caution=stt_result.get("needs_llm_caution", False)
                )
            except Exception as e:
                log_error(f"[ERROR] ask_bmo(recipe) 실패: {e}")
                speak_with_emotion("레시피 찾다가 문제가 생겼어.", EMOTION_SAD)
                continue
            response_emotion = choose_response_emotion(emotion, response_result)
            speak_with_emotion(response_result.get("reply", ""), response_emotion)

            continue

        if intent == "nutrition":
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            data = get_today_nutrition()
            if not data:
                speak_with_emotion("오늘은 아직 먹은 기록이 없어.", EMOTION_NEUTRAL)
            else:
                analysis = analyze_nutrition_balance(data)
                cal = data.get("total_calories", 0)
                protein = data.get("total_protein", 0)
                lacking = ", ".join(analysis["부족한영양소"]) or "없음"
                excess  = ", ".join(analysis["과다영양소"]) or "없음"
                msg = (
                    f"오늘 칼로리는 {cal:.0f}kcal, 단백질은 {protein:.0f}g야. "
                    f"부족한 영양소는 {lacking}, 과다한 영양소는 {excess}이야."
                )
                speak_with_emotion(msg, EMOTION_NEUTRAL)
            continue

        if intent == "update_allergy":
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            change_state(STATE_THINK)

            import re as _re
            # 불필요한 동사/표현 제거 후 음식명 추출
            _stop = [
                "알레르기 있어", "알레르기야", "알레르기 등록해줘", "알레르기 추가해줘",
                "알레르기 등록", "알레르기 추가", "알레르기 반응", "알레르기 알려줄게",
                "못 먹어", "먹으면 안돼", "먹으면 안 돼", "먹지 못해",
                "두드러기 나", "나는", "나", "저는", "저",
            ]
            _cleaned = user_text
            for _s in _stop:
                _cleaned = _cleaned.replace(_s, " ")
            _cleaned = _re.sub(r"[이가은는을를이랑랑과와](\s|$)", " ", _cleaned)
            _tokens = [t.strip() for t in _re.findall(r"[가-힣a-zA-Z]{2,}", _cleaned)]
            _food = _tokens[0] if _tokens else None

            if _food:
                from db_bridge import add_user_allergy as _add_allergy
                _add_allergy(_food)
                speak_with_emotion(f"{_food} 알레르기 등록했어! 레시피 추천할 때 빼줄게.", EMOTION_HAPPY)
                log_simple(f"[ALLERGY] 등록: {_food}")
            else:
                speak_with_emotion("어떤 음식에 알레르기가 있어? 예를 들어 '새우 알레르기 있어' 처럼 말해줘.", EMOTION_NEUTRAL)
            change_state(STATE_IDLE)
            continue

        if intent == "check_allergy":
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            from db_bridge import get_user_allergy as _get_allergy
            _allergy = _get_allergy()
            if _allergy:
                speak_with_emotion(f"등록된 알레르기는 {_allergy}야.", EMOTION_NEUTRAL)
            else:
                speak_with_emotion("아직 등록된 알레르기가 없어.", EMOTION_NEUTRAL)
            continue

        if intent == "remove_allergy":
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            change_state(STATE_THINK)

            import re as _re
            _stop2 = [
                "알레르기 삭제해줘", "알레르기 빼줘", "알레르기 없애줘", "알레르기 지워줘",
                "알레르기 삭제", "알레르기", "나", "나는",
            ]
            _cleaned2 = user_text
            for _s in _stop2:
                _cleaned2 = _cleaned2.replace(_s, " ")
            _tokens2 = [t.strip() for t in _re.findall(r"[가-힣a-zA-Z]{2,}", _cleaned2)]
            _food2 = _tokens2[0] if _tokens2 else None

            if _food2:
                from db_bridge import remove_user_allergy as _rm_allergy
                _rm_allergy(_food2)
                speak_with_emotion(f"{_food2} 알레르기 삭제했어.", EMOTION_NEUTRAL)
                log_simple(f"[ALLERGY] 삭제: {_food2}")
            else:
                speak_with_emotion("어떤 알레르기를 삭제할까? '새우 알레르기 삭제해줘' 처럼 말해줘.", EMOTION_NEUTRAL)
            change_state(STATE_IDLE)
            continue

        if intent == "help":
            print_analysis_log(stt_result, brain_result, llm_will_call=False)
            message = style or "나는 대화도 하고, 나중에는 냉장고 재료 확인이랑 레시피 추천도 도와줄 수 있어."
            speak_with_emotion(message, emotion)
            continue

        log_debug("\n--- BMO 턴 ---")
        print_analysis_log(stt_result, brain_result, llm_will_call=True)
        change_state(STATE_THINK)

        try:
            response_result = ask_bmo(
                user_text,
                emotion_prompt=llm_style,
                stt_needs_caution=stt_result.get("needs_llm_caution", False)
            )
        except Exception as e:
            log_error(f"[ERROR] ask_bmo 실패: {e}")
            speak_with_emotion(
                "미안, 지금 잠깐 생각이 꼬였어. 다시 말해줄래?",
                EMOTION_SAD
            )
            continue

        response = response_result.get("reply", "")

        if not response:
            log_error("[ERROR] BMO 응답이 비어 있음")
            speak_with_emotion(
                "음... 내가 제대로 대답을 못 했어. 다시 말해줄래?",
                EMOTION_SAD
            )
            continue

        response_emotion = choose_response_emotion(emotion, response_result)
        speak_with_emotion(response, response_emotion)

        # 대화에서 음식 섭취 감지 → DB 저장 (백그라운드)
        def _try_save_meal_from_chat(text):
            try:
                result = _backend_client.ask(text=text)
                if not result:
                    return
                meal = result.get("meal", {})
                nutrition = result.get("nutrition", {})
                food_name = meal.get("food", "")
                if meal.get("mentioned") and food_name:
                    save_consumed_recipe(food_name, nutrition)
                    if nutrition and nutrition.get("calories", 0) > 0:
                        add_daily_nutrition(nutrition)
                        log_debug(f"[MEAL SAVE] {food_name} 영양 저장 완료")
            except Exception as e:
                log_warn(f"[MEAL SAVE] 저장 실패: {e}")

        import threading as _threading
        _threading.Thread(
            target=_try_save_meal_from_chat,
            args=(user_text,),
            daemon=True
        ).start()



# 한 시간 마다 만료일 제거
def _expiry_check_loop():
    while True:
        try:
            purge_expired_inventory()
            purge_old_consumed_recipes()
            purge_old_nutrition()
        except Exception as e:
            log_warn(f"[EXPIRY] 갱신 실패: {e}")
        time.sleep(3600)


def main():
    global gui

    log_simple("=== BMO 시작 ===")
    log_simple("ESC 키를 누르면 강제 종료됩니다.")

    try:
        keyboard.add_hotkey("esc", force_exit)
    except Exception as e:
        log_warn(f"ESC 단축키 등록 실패: {e}")

    gui = BMOFace(
        on_sleep_touch=request_sleep_touch_wake,
        on_screen_narrate=narrate_on_screen,
        on_return_narrate=narrate_after_return
    )
    gui.root.after(0, process_face_updates)
    gui.root.after(0, process_ui_actions)

    threading.Thread(target=_expiry_check_loop, daemon=True).start()
    threading.Thread(target=conversation_loop, daemon=True).start()

    gui.run()


if __name__ == "__main__":
    main()
