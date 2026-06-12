# BMO

작은 휴대용 게임기 모양의 AI 친구 로봇. 음성으로 대화하고, 냉장고 재료를 확인하고, 레시피를 추천해준다.
Raspberry Pi 5 기반으로 동작하도록 설계되었으며, 로컬 LLM(Ollama)과 외부 백엔드 서버를 함께 사용한다.

---

## 전체 동작 흐름

```
마이크 입력
    └─▶ mic.py (음성 감지 + 녹음)
            └─▶ stt.py (Whisper STT → 텍스트)
                    └─▶ brain/bmo_brain.py (의도 + 감정 분석)
                            ├─▶ [일반 대화]    bmoAPI.py (Ollama LLM 호출)
                            ├─▶ [냉장고/레시피] db_bridge/ (SQLite 조회) + bmoAPI.py
                            └─▶ [음식 추천]    backend_client.py (외부 서버 /ask)
                                        └─▶ tts.py (TTS 음성 출력)
                                                └─▶ ui/bmo_face.py (표정 애니메이션)
```

---

## 파일별 역할

### 진입점

| 파일 | 역할 |
|------|------|
| `main.py` | 전체 진입점. GUI, 대화 루프, 만료 데이터 정리 스레드를 실행한다. |

---

### 음성 입출력

| 파일 | 역할 |
|------|------|
| `mic.py` | 마이크에서 음성을 감지해 WAV 파일로 녹음한다. 무음이 일정 시간 지속되면 녹음을 종료하거나 수면 상태로 전환한다. |
| `stt.py` | `faster-whisper` 모델(`base`)로 음성을 텍스트로 변환한다. confidence 기준으로 인식 신뢰도를 3단계(confident / uncertain / very_uncertain)로 분류하고, `stt_corrections.json` 오탈자 교정 테이블을 적용한다. |
| `tts.py` | 텍스트를 TTS 음성으로 변환해 재생한다. |
| `stt_corrections.json` | STT가 자주 틀리는 단어를 정확한 표현으로 교정하는 매핑 테이블. |

---

### LLM / 백엔드 통신

| 파일 | 역할 |
|------|------|
| `bmoAPI.py` | 로컬 Ollama 서버(`gemma4:e2b`)를 호출해 대화 응답을 생성한다. 시스템 프롬프트로 BMO 캐릭터를 정의하고, 응답을 `{emotion, confidence, reply}` JSON으로 파싱한다. 대화 히스토리 최대 8턴 유지. 파싱 실패 시 단계별 fallback 처리. |
| `backend_client.py` | 외부 Python 백엔드 서버와 HTTP 통신하는 클라이언트. 아래 엔드포인트를 사용한다. |

**BackendClient 엔드포인트**

| 엔드포인트 | 메서드 | 용도 |
|-----------|--------|------|
| `/` | GET | 서버 헬스 체크 |
| `/ask` | POST | 일반 대화 + 음식 추천 + 레시피 선택 |
| `/upload-image` | POST | 냉장고/식재료 이미지 분석 |
| `/upload-receipt` | POST | 영수증 OCR → 재료 목록 추출 |
| `/nutrition` | POST | 음식 이름으로 영양정보 조회 |
| `/select-recipe` | POST | 레시피 이름으로 조리 방법 조회 |

---

### 두뇌 (의도·감정 분석)

| 파일 | 역할 |
|------|------|
| `brain/bmo_brain.py` | 사용자 발화를 받아 감정과 의도를 분석한다. `emotion_engine`과 `speech_commands`를 조합해 최종 결과를 반환한다. |
| `brain/emotion_engine.py` | `emotion_rules.json` 키워드 패턴으로 감정(happy / sad / angry / neutral)을 점수화한다. 부정 표현(`emotion_negation.json`) 감지 시 sad 점수를 보정한다. |
| `brain/emotion_response_engine.py` | 감정과 의도 조합에 따라 LLM에 전달할 응답 스타일 힌트 문자열을 생성한다. |
| `brain/emotion_rules.json` | 감정별 트리거 패턴과 가중치 정의. |
| `brain/emotion_negation.json` | 부정 표현 감지 패턴 ("안 좋아", "좋지 않아" 등). |
| `brain/response_styles.json` | 감정·의도별 LLM 응답 스타일 템플릿. |

---

### 커맨드 처리

| 파일 | 역할 |
|------|------|
| `commands/speech_commands.py` | 발화에서 의도(intent)를 감지한다. `fridge / recommend / recipe / nutrition / weather / help` 등 키워드 매핑과 웨이크워드("비모야"), 종료 커맨드("안녕", "종료" 등)를 처리한다. |
| `commands/bmo_responses.py` | 고정 응답 문자열 모음 (웨이크, 수면 전환, STT 실패 등). |

---

### UI

| 파일 | 역할 |
|------|------|
| `ui/bmo_face.py` | Tkinter 기반 BMO 얼굴 GUI. 상태(sleep / wake / idle / listen / think / speak)와 감정(happy / sad / angry)에 따라 `assets/images/faces/` 폴더의 이미지를 전환한다. |
| `ui/asset_paths.py` | 이미지 경로 상수 모음. 폴더 구조 변경 시 이 파일만 수정하면 된다. |
| `ui/screens/fridge_screen.py` | 냉장고 재고 목록 화면. `FridgeService`에서 데이터를 받아 렌더링. |
| `ui/screens/recipe_screen.py` | 추천 레시피 목록 화면. `RecipeService`에서 데이터를 받아 렌더링. |
| `ui/screens/camera_screen.py` | 카메라 프리뷰 및 촬영 화면. |
| `ui/screens/minigame_screen.py` | 미니게임 화면. |
| `ui/screens/common_widgets.py` | 뒤로가기 버튼 등 화면 간 공용 위젯. |

**얼굴 상태 이미지 (`faces/`)**

| 폴더 | 표시 타이밍 |
|------|------------|
| `sleep/` | 수면 대기 중 (애니메이션 6프레임) |
| `wake/` | 깨어나는 순간 |
| `idle/` | 대기 중 |
| `listen/` | 음성 듣는 중 |
| `think/` | 생각 중 (좌/우) |
| `speak/` | 말하는 중 (기본) |
| `speak_happy/` | 기쁜 표정으로 말할 때 |
| `speak_sad/` | 슬픈 표정으로 말할 때 |
| `speak_angry/` | 화난 표정으로 말할 때 |

---

### 기능 모듈 (`features/`)

| 파일 | 역할 |
|------|------|
| `features/camera/camera_service.py` | OpenCV 또는 PiCamera2로 사진을 촬영한다. `settings.py`의 `CAMERA_BACKEND` 설정에 따라 자동 선택. |
| `features/fridge/fridge_service.py` | 냉장고 재료 목록을 UI용으로 가공해 반환한다. `FridgeScreen`에서 사용. |
| `features/recipe/recipe_service.py` | 레시피 추천·조리순서를 백엔드 API에서 받아 UI용으로 가공한다. `RecipeScreen`과 `main.py`에서 사용. 재추천 시 이전 추천 목록 제외 처리 포함. |
| `features/weather/weather_service.py` | 날씨 정보 조회. |
| `features/minigame/color_guess_game.py` | 색 맞추기 미니게임. |

---

### DB 브릿지 (`db_bridge.py`)

SQLite 데이터베이스(`capstonedb.db`)를 직접 조작하는 함수 모음. 단일 파일로 구성되어 있다.

| 담당 테이블 | 주요 함수 |
|------------|----------|
| `Ingredient`, `Inventory` | `get_fridge_context`, `get_fridge_ingredient_names`, `save_ingredient_items`, `consume_ingredient`, `deduct_recipe_ingredients`, `remove_ingredient_fully`, `purge_expired_inventory` |
| `Recipe`, `RecipeIngredient` | `get_matching_recipes`, `get_recipe_list_context`, `save_consumed_recipe` |
| `ConsumedRecipe` | `save_consumed_recipe`, `purge_old_consumed_recipes` |
| `DailyNutrition` | `add_daily_nutrition`, `get_today_nutrition`, `analyze_nutrition_balance`, `purge_old_nutrition` |
| `User` | `get_user_profile`, `save_user_profile` |

---

## 데이터베이스 테이블

DB 파일 위치: 프로젝트 상위 디렉토리의 `capstonedb.db`

### `Ingredient` — 식재료 마스터

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `ingredient_id` | INTEGER PK | 자동 증가 |
| `ingredient_name` | TEXT | 재료 이름 (유일) |
| `category` | TEXT | 분류 (채소, 육류 등) |

### `Inventory` — 냉장고 재고

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `inventory_id` | INTEGER PK | 자동 증가 |
| `ingredient_id` | INTEGER FK | `Ingredient` 참조 |
| `quantity` | INTEGER | 수량 |
| `purchase_date` | TEXT | 구매일 (YYYY-MM-DD) |
| `expiration_date` | TEXT | 유통기한 (만료 시 자동 삭제) |

### `Recipe` — 레시피

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `recipe_id` | INTEGER PK | 자동 증가 |
| `recipe_name` | TEXT | 레시피 이름 |
| `content` | TEXT | 조리 방법 (백엔드에서 조회 후 업데이트) |
| `calories` | REAL | 칼로리 (kcal) |
| `protein` | REAL | 단백질 (g) |
| `sugar` | REAL | 당류 (g) |
| `sodium` | REAL | 나트륨 (mg) |
| `fiber` | REAL | 식이섬유 (g) |
| `saturated_fat` | REAL | 포화지방 (g) |
| `recommended_date` | TEXT | 추천된 날짜 |

### `RecipeIngredient` — 레시피-재료 연결

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | 자동 증가 |
| `recipe_id` | INTEGER FK | `Recipe` 참조 |
| `ingredient_id` | INTEGER FK | `Ingredient` 참조 |
| `amount` | TEXT | 필요 수량 (예: "2개", "적당량") |

### `ConsumedRecipe` — 섭취 기록

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | 자동 증가 |
| `recipe_id` | INTEGER FK | `Recipe` 참조 |
| `consumed_date` | TEXT | 먹은 날짜 (7일 지나면 자동 삭제) |

### `DailyNutrition` — 일별 영양 합계

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER PK | 자동 증가 |
| `date` | TEXT UNIQUE | 날짜 (중복 시 누적 합산) |
| `total_calories` | REAL | 총 칼로리 |
| `total_protein` | REAL | 총 단백질 |
| `total_sugar` | REAL | 총 당류 |
| `total_sodium` | REAL | 총 나트륨 |
| `total_fiber` | REAL | 총 식이섬유 |
| `total_saturated_fat` | REAL | 총 포화지방 |

**영양 분석 기준:**
- 부족: 단백질 < 50g, 식이섬유 < 20g
- 과다: 나트륨 > 2000mg, 당류 > 50g

### `User` — 사용자 프로필

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `name` | TEXT PK | 사용자 식별자 (기본값 "user") |
| `allergy` | TEXT | 알레르기 |
| `preferred_food` | TEXT | 선호 음식 |
| `disliked_food` | TEXT | 비선호 음식 |
| `diet_habit` | TEXT | 식습관 |
| `health_status` | TEXT | 건강 상태 |

> 프로필은 대화 중 LLM이 파악한 정보를 점진적으로 업데이트한다. 기존 값이 있으면 덮어쓰지 않고 비어있는 항목만 채운다.

---

## 설정 (`config/`)

| 파일 | 역할 |
|------|------|
| `config/settings.py` | 로그 레벨(`SIMPLE` / `DEBUG` / `TRACE`), Ollama warmup 여부, 카메라 백엔드(`auto` / `opencv` / `picamera2`), 해상도 등 전역 설정. |
| `config/states.py` | 상태 상수(`STATE_SLEEP`, `STATE_IDLE` 등)와 감정 상수(`EMOTION_HAPPY` 등) 정의. |

---

## 의도(Intent) 종류

| intent | 트리거 키워드 예시 | 처리 방식 |
|--------|-----------------|----------|
| `fridge` | "냉장고", "재료 확인" | DB에서 재고 조회 후 Ollama에 컨텍스트 첨부 |
| `recommend` | "뭐 먹", "메뉴 추천", "추천해줘" | 레시피 화면 열기. `RecipeService`가 백엔드 `/ask`로 추천 요청 |
| `rerecommend` | "다른거", "재추천", "다시 추천" | 이전 추천 목록을 제외하고 레시피 화면 재진입 |
| `recipe` | "레시피", "만드는 법" | DB 레시피 목록 조회 후 Ollama에 컨텍스트 첨부 |
| `add_ingredient` | "냉장고에 넣어", "재료 추가", "샀어" | DB에 재료 추가 (`save_ingredient_items`) |
| `consume_ingredient` | "다 먹었어", "소비했어", "다 썼어" | DB에서 재료 수량 차감 (`consume_ingredient`) |
| `nutrition` | "영양", "칼로리", "오늘 뭐 먹었어" | `DailyNutrition` 조회 후 바로 응답 (LLM 미호출) |
| `mic-mute` | "마이크 음소거", "음소거 해줘" | 마이크 입력 차단 |
| `weather` | "날씨", "기온", "우산" | 날씨 API 조회 후 응답 |
| `help` | "도움말", "기능", "너는 어떤 친구야" | 고정 메시지 응답 |
| `chat` | 그 외 모든 발화 | Ollama 일반 대화 |

---

## 실행 방법

```bash
# 의존성 설치
pip install -r requirements.txt

# Ollama 서버 실행 (별도 터미널)
ollama serve

# BMO 실행
python main.py
```

**환경 변수:**

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `BMO_BACKEND_URL` | `http://175.202.111.234:5000` | 외부 백엔드 서버 주소 |

---

## 감정 여운 시스템

BMO는 감정 응답 후 일정 시간 동안 표정을 유지한다.

| 감정 | 유지 시간 |
|------|----------|
| happy | 2.0초 |
| angry | 2.5초 |
| sad | 4.0초 |

LLM 응답의 `emotion + confidence`와 룰 기반 감정 분석 결과를 비교해 최종 표정을 결정한다. LLM confidence가 0.45 이상이면 LLM 감정을 우선 사용하고, 그렇지 않으면 룰 기반 감정으로 fallback한다.
