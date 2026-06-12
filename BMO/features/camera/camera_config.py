# camera/camera_config.py

# ==================================================
# 카메라 실행 설정
# ==================================================

# PC에서 개발 및 테스트할 때는 "opencv"
# Raspberry Pi 카메라 모듈로 실행할 때는 "picamera2"
# 충분히 테스트한 뒤 자동 선택을 원하면 "auto"
CAMERA_BACKEND = "picamera2"

# PC 웹캠 또는 카메라 장치 번호
CAMERA_INDEX = 0

# GUI 안에서 보여줄 실시간 미리보기 크기
CAMERA_PREVIEW_SIZE = (720, 400)

# OCR 분석용으로 저장할 촬영 이미지 요청 크기
CAMERA_CAPTURE_SIZE = (1920, 1080)

# 촬영 이미지 저장 폴더
CAPTURE_SAVE_DIR = "captured_images"