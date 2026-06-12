# config/settings.py

"""
STT_MODEL = "small"
MAX_HISTORY = 6
GUI_WIDTH = 800
GUI_HEIGHT = 480
USE_TTS = True
SAMPLERATE = 16000
THRESHOLD = 100
SILENCE_LIMIT = 1.0
TIMEOUT = 10
"""


# 가능한 값: "SIMPLE", "DEBUG", "TRACE"
"""
"SIMPLE" : 시연 같이 간단하게 보기 위한 로그
"DEBUG" : 문제 발생시 디버그 체크용 로그
"TRACE" : 문제 원인 분석시 추적하기 위한 로그
"""
LOG_LEVEL = "DEBUG"   #"SIMPLE", "DEBUG", "TRACE" 모드 중에서 선택

# OLLAMA을 미리 깨우는 WARMUP 함수 세팅
ENABLE_OLLAMA_WARMUP = True
OLLAMA_WARMUP_PROMPT = "준비"


# 카메라 설정 : pc환경인지 라즈베리 파이 환경인지에 따라 설정
CAMERA_BACKEND = "auto"
# "auto"      : 실행 환경과 사용 가능 라이브러리에 따라 자동 선택
# "opencv"    : PC 웹캠 또는 USB 웹캠 강제 사용
# "picamera2" : Raspberry Pi 카메라 모듈 강제 사용

CAMERA_PREVIEW_WIDTH = 720
CAMERA_PREVIEW_HEIGHT = 400

CAPTURE_SAVE_DIR = "captured_images"
