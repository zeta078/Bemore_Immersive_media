# mic.py
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from logger import log_debug, log_warn

SAMPLERATE = 44100
THRESHOLD = 1200         # 기존 500 → 낮춤
SILENCE_LIMIT = 2.0      # 기존 1.0 → 조금 늘림
PRE_SPEECH_BLOCKS = 8    # 기존 3 → 말 앞부분 보존 증가
BLOCK_DURATION = 0.2


def get_volume(audio_block):
    return np.abs(audio_block).mean()


def wait_for_voice(timeout=None):
    block_size = int(SAMPLERATE * BLOCK_DURATION)
    elapsed = 0

    log_debug("목소리 감지 대기 중...")

    with sd.InputStream(samplerate=SAMPLERATE, channels=1, dtype="int16") as stream:
        while True:
            audio_block, _ = stream.read(block_size)
            volume = get_volume(audio_block)

            # 디버그용: 필요 없으면 주석 처리
            # print(f"[VOL] {volume:.1f}")

            if volume > THRESHOLD:
                log_debug(f"목소리 감지: volume={volume:.1f}")
                return True

            if timeout is not None:
                elapsed += BLOCK_DURATION

                if elapsed >= timeout:
                    log_debug("목소리 감지 시간 초과")
                    return False


def record_audio(
    filename="input.wav",
    on_start=None,
    wait_timeout=None,
    silence_limit=SILENCE_LIMIT,
    max_record_time=None,
    pre_speech_blocks=PRE_SPEECH_BLOCKS,
    should_stop=None
):
    log_debug("BMO 듣는 중...")

    block_size = int(SAMPLERATE * BLOCK_DURATION)

    recording = []
    pre_buffer = []
    silence_time = 0
    wait_time = 0
    record_time = 0
    started = False

    with sd.InputStream(samplerate=SAMPLERATE, channels=1, dtype="int16") as stream:
        while True:
            if should_stop is not None and should_stop():
                log_debug("외부 중단 신호로 녹음 대기 종료")
                return None

            audio_block, _ = stream.read(block_size)
            volume = get_volume(audio_block)

            # 디버그용: 필요 없으면 주석 처리
            # print(f"[VOL] {volume:.1f}")

            if not started:
                wait_time += BLOCK_DURATION

                pre_buffer.append(audio_block)
                if len(pre_buffer) > pre_speech_blocks:
                    pre_buffer.pop(0)

                if wait_timeout is not None and wait_time >= wait_timeout:
                    log_debug("목소리 없음, 녹음 대기 종료")
                    return None

                if volume > THRESHOLD:
                    log_debug(f"말소리 감지, 녹음 시작: volume={volume:.1f}")
                    started = True

                    if on_start:
                        on_start()

                    recording.extend(pre_buffer)
                    silence_time = 0

            else:
                if should_stop is not None and should_stop():
                    log_debug("외부 중단 신호로 녹음 종료")
                    break

                recording.append(audio_block)
                record_time += BLOCK_DURATION

                if volume > THRESHOLD:
                    silence_time = 0
                else:
                    silence_time += BLOCK_DURATION

                if silence_time >= silence_limit:
                    log_debug("침묵 감지, 녹음 종료")
                    break

                if max_record_time is not None and record_time >= max_record_time:
                    log_debug("최대 녹음 시간 도달, 녹음 종료")
                    break

    if not recording:
        log_warn("녹음된 음성이 없습니다.")
        return None

    audio = np.concatenate(recording, axis=0)
    write(filename, SAMPLERATE, audio)
    log_debug(f"저장 완료: {filename}")

    return filename
