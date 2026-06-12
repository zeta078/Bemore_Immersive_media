# 날씨 기능 설정
import os

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
WEATHER_CITY = "Jeonju"
WEATHER_CITY_DISPLAY_NAME = "전주"
WEATHER_LANG = "kr"
WEATHER_TIMEOUT = 5

# 한글 도시명 → OpenWeatherMap 영문 도시명
CITY_NAME_MAP = {
    "서울": "Seoul",
    "부산": "Busan",
    "대구": "Daegu",
    "인천": "Incheon",
    "광주": "Gwangju",
    "대전": "Daejeon",
    "울산": "Ulsan",
    "세종": "Sejong",
    "수원": "Suwon",
    "성남": "Seongnam",
    "고양": "Goyang",
    "용인": "Yongin",
    "창원": "Changwon",
    "전주": "Jeonju",
    "청주": "Cheongju",
    "천안": "Cheonan",
    "포항": "Pohang",
    "제주": "Jeju",
    "목포": "Mokpo",
    "여수": "Yeosu",
    "춘천": "Chuncheon",
    "강릉": "Gangneung",
    "원주": "Wonju",
}

# 영문 → 한글 역매핑
CITY_DISPLAY_MAP = {v: k for k, v in CITY_NAME_MAP.items()}
