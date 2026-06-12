# logger.py
# 디버그 및 오류 추적 상세 설정을 위한 파이썬 코드 파일,
# 최종 프로젝트 결과 확정 시에는 필요 없는 코드 
try:
    from config.settings import LOG_LEVEL
except Exception:
    LOG_LEVEL = "SIMPLE"


LOG_LEVELS = {
    "SIMPLE": 1,
    "DEBUG": 2,
    "TRACE": 3,
}


def _current_level() -> int:
    return LOG_LEVELS.get(str(LOG_LEVEL).upper(), LOG_LEVELS["SIMPLE"])


def _log(required_level: str, message: str):
    if _current_level() >= LOG_LEVELS[required_level]:
        print(message)


def log_simple(message: str):
    _log("SIMPLE", message)


def log_debug(message: str):
    _log("DEBUG", message)


def log_trace(message: str):
    _log("TRACE", message)


def log_warn(message: str):
    print(message)


def log_error(message: str):
    print(message)
