# commands/speech_commands.py

COMMAND_WORDS = {
    "photo_analysis": [
        "사진 보여줄게", "사진 분석해줘", "사진 보여줘",
        "사진 분석 보여줘", "이거 읽어줘", "사진 모드",
        "카메라", "촬영"
    ],
    "memo": [
        "이거 메모해줘", "메모해줘", "메모하자",
        "메모 시작하자", "메모 시작해줘", "메모 모드"
    ],
    "datetime_check": [
        "몇 시야", "현재 시간 알려줘", "오늘 몇월 몇일이야",
        "오늘 날짜 알려줘", "시간 알려줘", "날짜 알려줘"
    ],
    "weather": [
        "날씨",
        "오늘 날씨 어때",
        "날씨 알려줘",
        "날씨 알려 줘",
        "날씨 정보 알려줘",
        "날씨 정보 알려 줘",
        "기온",
        "온도",
        "우산",
        "비 와",
        "비와",
        "추워",
        "더워"
    ],

    "mic-mute" : [
        "음소거 해줘", "마이크 음소거 해줘" , "마이크 음소거"
    ],

    "add_ingredient": [
        "냉장고에 넣어", "냉장고에 추가", "재료 추가", "재료 넣어",
        "추가해줘", "넣어줘", "등록해줘", "냉장고에 등록",
        "냉장고에 넣어줘", "냉장고에 추가해줘"
    ],
    "consume_ingredient": [
        "소비했어", "소모했어", "다 먹었어", "다 썼어", "소진했어",
        "다 없어졌어", "써버렸어", "다 떨어졌어", "없어졌어", "다 됐어",
        "먹었어", "먹어버렸어", "다 쓴 것 같아", "다 쓴거 같아"
    ],
    "fridge": [
        "냉장고", "식재료", "재료 봐", "재료 확인", "재료"
    ],
    "recommend": [
        "뭐 먹", "메뉴 추천", "음식 추천", "요리 추천",
        "뭐가 좋을까", "뭐 먹을까", "뭐 해먹", "뭐 해먹을까",
        "점심 추천", "저녁 추천", "아침 추천", "식사 추천",
        "반찬 추천", "간식 추천",
        "추천해줘", "추천해", "레시피 추천", "음식 추천해",
    ],
    "rerecommend": [
        "다른거", "다른 거", "다른 것", "다른 음식", "다른 메뉴", "다른 레시피",
        "다시 추천", "딴 거", "딴거", "재추천", "또 추천", "다른 걸로",
    ],
    "recipe": [
        "레시피", "요리법", "만드는 법", "만드는 방법", "조리법", "어떻게 만들어"
    ],
    "help": [
        "도움말", "help", "헬프", "기능", "뭐 할 수", "너는 어떤 친구야?"
    ],
    "nutrition": [
        "영양", "영양소", "오늘 뭐 먹었어", "오늘 영양", "영양 상태",
        "단백질", "칼로리", "오늘 얼마나 먹었어", "영양 분석"
    ],
    "update_allergy": [
        "알레르기 있어", "알레르기야", "알레르기 등록", "알레르기 추가",
        "못 먹어", "먹으면 안돼", "먹으면 안 돼", "먹지 못해",
        "알레르기 반응", "두드러기 나", "알레르기 알려줄게",
    ],
    "check_allergy": [
        "알레르기 알려줘", "알레르기 뭐야", "알레르기 뭐 있어",
        "내 알레르기", "등록된 알레르기",
    ],
    "remove_allergy": [
        "알레르기 삭제", "알레르기 빼줘", "알레르기 없애줘", "알레르기 지워줘",
    ],
    "exit_screen": [
        "뒤로",
        "나갈",
        "나가",
        "그만",
        "메인",
        "돌아가",
        "돌아갈",
        "종료",
        "끝"
    ]

}


WAKE_WORDS = [
    "비모야", "비모", "안녕 비모야", "안녕 비모", "비무여",
    "hey bmo", "hi bmo", "피모야", "비무야", "삐모야", "미모야"
]


REST_WORDS = [
    "종료", "끝", "그만", "잘가", "끝내자",
    "오늘은 여기까지", "다음에 보자", "또 보자",
    "안녕", "bye", "goodbye", "대화 종료", "자러 갈게", "자러 가볼게"
]


def normalize_text(text: str) -> str:
    if not text:
        return ""

    return text.strip()


def contains_wake_word(text: str) -> bool:
    normalized = normalize_text(text)
    return any(word in normalized for word in WAKE_WORDS)


def remove_wake_word(text: str) -> str:
    normalized = normalize_text(text)

    for word in WAKE_WORDS:
        normalized = normalized.replace(word, "")

    return normalized.strip()


def is_rest_command(text: str) -> bool:
    normalized = normalize_text(text)
    return any(word in normalized for word in REST_WORDS)


def detect_command_intent(text: str) -> str:
    normalized = normalize_text(text)

    if any(pattern in normalized for pattern in COMMAND_WORDS["exit_screen"]):
        return "exit_screen"

    # 재료 추가: 추가/넣어/등록 동사가 있으면 fridge보다 먼저 잡음
    # 예) "냉장고 안에 계란 10개 추가했어", "양파 넣어줘", "당근 등록해줘"
    ADD_VERBS = ["추가해", "추가했", "넣어줘", "넣었어", "넣어", "등록해줘", "등록했", "샀어", "사왔어", "구매했"]
    if any(v in normalized for v in ADD_VERBS):
        return "add_ingredient"

    # 재료 소비: 소비/소모/먹었어 등 소진 동사가 있으면 consume_ingredient
    CONSUME_VERBS = ["소비했", "소모했", "다 먹었", "다 썼", "소진했", "다 없어졌", "써버렸", "다 떨어졌", "없어졌", "먹었어", "먹어버렸"]
    if any(v in normalized for v in CONSUME_VERBS):
        return "consume_ingredient"

    has_fridge_context = any(pattern in normalized for pattern in COMMAND_WORDS["fridge"])
    has_recommend_request = any(pattern in normalized for pattern in COMMAND_WORDS["recommend"])

    if has_fridge_context and has_recommend_request:
        return "recommend"

    for intent, patterns in COMMAND_WORDS.items():
        for pattern in patterns:
            if pattern in normalized:
                return intent

    return "chat"