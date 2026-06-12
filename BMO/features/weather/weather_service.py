# features/weather/weather_service.py
from datetime import datetime, timedelta
from typing import Optional

import requests

from features.weather.weather_config import (
    CITY_DISPLAY_MAP,
    CITY_NAME_MAP,
    OPENWEATHER_API_KEY,
    WEATHER_CITY,
    WEATHER_CITY_DISPLAY_NAME,
    WEATHER_LANG,
    WEATHER_TIMEOUT,
)

WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_API_URL = "https://api.openweathermap.org/data/2.5/forecast"

WEEKDAY_KR = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


# ──────────────────────────────────────────────────────────────────────
#  도시명 추출
# ──────────────────────────────────────────────────────────────────────

def extract_city_from_text(text: str) -> tuple[str, str]:
    """
    발화에서 도시명을 추출해 (영문 API 도시명, 한글 표시명) 튜플을 반환한다.
    없으면 기본 도시(전주)를 반환한다.
    """
    for kor, eng in CITY_NAME_MAP.items():
        if kor in text:
            return eng, kor
    return WEATHER_CITY, WEATHER_CITY_DISPLAY_NAME


def detect_forecast_type(text: str) -> str:
    """
    발화에서 예보 유형을 감지한다.
    반환값: "current" | "tomorrow" | "dayafter" | "weekly"
    """
    if "모레" in text:
        return "dayafter"
    if "내일" in text:
        return "tomorrow"
    if any(kw in text for kw in ["이번 주", "이번주", "일주일", "주간", "한 주", "한주", "며칠"]):
        return "weekly"
    return "current"


# ──────────────────────────────────────────────────────────────────────
#  현재 날씨
# ──────────────────────────────────────────────────────────────────────

def get_weather_data(city: str = WEATHER_CITY) -> Optional[dict]:
    """OpenWeather API에서 현재 날씨 정보를 받아온다."""
    params = {
        "q": f"{city},KR",
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": WEATHER_LANG,
    }

    try:
        response = requests.get(WEATHER_API_URL, params=params, timeout=WEATHER_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        weather_id = data["weather"][0]["id"]
        description = data["weather"][0]["description"]
        needs_umbrella = 200 <= weather_id < 700

        display_name = CITY_DISPLAY_MAP.get(city, WEATHER_CITY_DISPLAY_NAME if city == WEATHER_CITY else data.get("name", city))

        weather_data = {
            "city": display_name,
            "weather_id": weather_id,
            "temperature": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "description": description,
            "humidity": data["main"]["humidity"],
            "needs_umbrella": needs_umbrella,
        }

        print(
            f"[WEATHER] {weather_data['city']} / "
            f"{weather_data['description']} / "
            f"{weather_data['temperature']:.1f}도 / "
            f"습도 {weather_data['humidity']}%"
        )

        return weather_data

    except requests.RequestException as e:
        print(f"[WEATHER WARN] 날씨 API 요청 실패: {e}")
        return None
    except (KeyError, IndexError, TypeError) as e:
        print(f"[WEATHER WARN] 날씨 데이터 처리 실패: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────
#  예보 (내일 / 주간)
# ──────────────────────────────────────────────────────────────────────

def get_forecast_data(city: str = WEATHER_CITY) -> Optional[list]:
    """
    /forecast 에서 5일치 3시간 간격 예보를 받아 날짜별로 묶어 반환한다.
    반환: [{"date": "2026-06-11", "weekday": "목요일", "temp_min": 18, "temp_max": 26,
             "description": "맑음", "weather_id": 800, "needs_umbrella": False}, ...]
    """
    params = {
        "q": f"{city},KR",
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": WEATHER_LANG,
        "cnt": 40,
    }

    try:
        response = requests.get(FORECAST_API_URL, params=params, timeout=WEATHER_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        daily: dict[str, dict] = {}
        for item in data["list"]:
            dt = datetime.fromtimestamp(item["dt"])
            date_str = dt.strftime("%Y-%m-%d")

            if date_str not in daily:
                daily[date_str] = {
                    "date": date_str,
                    "weekday": WEEKDAY_KR[dt.weekday()],
                    "temps": [],
                    "descriptions": [],
                    "weather_ids": [],
                }

            daily[date_str]["temps"].append(item["main"]["temp"])
            daily[date_str]["descriptions"].append(item["weather"][0]["description"])
            daily[date_str]["weather_ids"].append(item["weather"][0]["id"])

        result = []
        for date_str, day in sorted(daily.items()):
            weather_id = day["weather_ids"][len(day["weather_ids"]) // 2]
            result.append({
                "date": date_str,
                "weekday": day["weekday"],
                "temp_min": round(min(day["temps"])),
                "temp_max": round(max(day["temps"])),
                "description": day["descriptions"][len(day["descriptions"]) // 2],
                "weather_id": weather_id,
                "needs_umbrella": 200 <= weather_id < 700,
            })

        print(f"[WEATHER] 예보 {len(result)}일치 수신")
        return result

    except requests.RequestException as e:
        print(f"[WEATHER WARN] 예보 API 요청 실패: {e}")
        return None
    except (KeyError, IndexError, TypeError) as e:
        print(f"[WEATHER WARN] 예보 데이터 처리 실패: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────
#  응답 문장 생성
# ──────────────────────────────────────────────────────────────────────

def make_weather_response(city: str, temperature: float, description: str, needs_umbrella: bool) -> str:
    umbrella = "나갈 때 우산 챙겨!" if needs_umbrella else "오늘은 우산 없어도 괜찮겠어."
    return f"{city}는 지금 {description}이고 {temperature:.0f}도야. {umbrella}"


def make_tomorrow_response(city: str, forecast_days: list, days_ahead: int = 1) -> str:
    label = "내일" if days_ahead == 1 else "모레"
    target = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    day = next((d for d in forecast_days if d["date"] == target), None)

    if day is None:
        return f"{city} {label} 날씨 정보를 가져오지 못했어."

    umbrella = "우산 챙겨!" if day["needs_umbrella"] else "우산은 필요 없겠어."
    return (
        f"{city} {label} {day['weekday']}은 {day['description']}이고 "
        f"{day['temp_min']}도에서 {day['temp_max']}도야. {umbrella}"
    )


def make_weekly_response(city: str, forecast_days: list) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    days = [d for d in forecast_days if d["date"] > today][:5]

    if not days:
        return f"{city} 주간 날씨 정보를 가져오지 못했어."

    parts = [f"{city} 이번 주 날씨야."]
    for day in days:
        umbrella = "☂" if day["needs_umbrella"] else ""
        parts.append(
            f"{day['weekday']} {day['description']} "
            f"{day['temp_min']}~{day['temp_max']}도{umbrella}."
        )
    return " ".join(parts)


# ──────────────────────────────────────────────────────────────────────
#  통합 진입점
# ──────────────────────────────────────────────────────────────────────

def handle_weather(user_text: str) -> tuple[str, Optional[int]]:
    """
    발화 분석 후 적절한 날씨 응답과 아이콘용 weather_id를 반환한다.
    반환: (응답 문장, weather_id or None)
    """
    city_eng, city_kor = extract_city_from_text(user_text)
    forecast_type = detect_forecast_type(user_text)

    if forecast_type == "current":
        data = get_weather_data(city_eng)
        if data is None:
            return "지금은 날씨 정보를 가져오지 못했어.", None
        return make_weather_response(
            city=city_kor,
            temperature=data["temperature"],
            description=data["description"],
            needs_umbrella=data["needs_umbrella"],
        ), data["weather_id"]

    forecast = get_forecast_data(city_eng)
    if forecast is None:
        return "지금은 날씨 예보를 가져오지 못했어.", None

    if forecast_type == "tomorrow":
        return make_tomorrow_response(city_kor, forecast, days_ahead=1), forecast[0]["weather_id"] if forecast else None

    if forecast_type == "dayafter":
        return make_tomorrow_response(city_kor, forecast, days_ahead=2), forecast[0]["weather_id"] if forecast else None

    return make_weekly_response(city_kor, forecast), None


def get_weather_response(city: str = WEATHER_CITY) -> str:
    data = get_weather_data(city)
    if data is None:
        return "지금은 날씨 정보를 불러오지 못했어. 잠시 뒤에 다시 물어봐 줘."
    return make_weather_response(
        city=data["city"],
        temperature=data["temperature"],
        description=data["description"],
        needs_umbrella=data["needs_umbrella"],
    )


if __name__ == "__main__":
    print(f"BMO: {get_weather_response()}")
