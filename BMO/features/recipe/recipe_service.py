"""
레시피 화면을 위한 레시피 데이터 서비스.

- get_recommended_recipes(): DB(냉장고 재료 + 유저 프로필 + 오늘 영양)를
  백엔드 /ask 에 보내 Gemini 추천 결과를 받아 반환한다.
- get_recipe_steps(recipe_name): 백엔드 /select-recipe 에 보내
  Gemini가 생성한 조리 순서를 받아 반환한다.
- UI는 이 메서드를 호출하고 결과를 렌더링하는 기능만 수행한다.
"""

import json
import re
import sqlite3
import os
import time

import requests

# ── DB 경로 (db_bridge.py 와 동일 기준) ───────────────────────────────
_DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "..", "..", "DB", "capstonedb.db")
)

# ── 백엔드 URL (backend_client.py 와 동일 기준) ────────────────────────
_BACKEND_URL = os.getenv("BMO_BACKEND_URL", "http://175.202.111.234:5000").rstrip("/")
_TIMEOUT = 60 

# ── 선택한 레시피 저장 경로 ──────────────────────────────────────────
_SELECTED_RECIPE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "..", "selected_recipe.json")
)

# ── 추천 목록 캐시 경로 ───────────────────────────────────────────────
_CACHED_RECIPES_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "..", "cached_recipes.json")
)

# ── 마지막 추천 목록 (재추천 시 제외용) ──────────────────────────────
_last_recommended: list = []
_exclude_on_next: list = []


_CACHE_TTL = 3600  # 1시간


def save_cached_recipes(recipes: list) -> None:
    try:
        payload = {"timestamp": time.time(), "recipes": recipes}
        with open(_CACHED_RECIPES_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[RECIPE CACHE] 목록 저장 실패: {e}")


def load_cached_recipes() -> list:
    try:
        if os.path.exists(_CACHED_RECIPES_PATH):
            with open(_CACHED_RECIPES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 구형 포맷(list) 호환
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                age = time.time() - data.get("timestamp", 0)
                if age < _CACHE_TTL and isinstance(data.get("recipes"), list) and data["recipes"]:
                    print(f"[RECIPE CACHE] 캐시 사용 (경과 {int(age)}초)")
                    return data["recipes"]
                if age >= _CACHE_TTL:
                    print(f"[RECIPE CACHE] 캐시 만료 ({int(age)}초 경과)")
    except Exception as e:
        print(f"[RECIPE CACHE] 목록 로드 실패: {e}")
    return []


def clear_cached_recipes() -> None:
    try:
        if os.path.exists(_CACHED_RECIPES_PATH):
            os.remove(_CACHED_RECIPES_PATH)
    except Exception as e:
        print(f"[RECIPE CACHE] 목록 초기화 실패: {e}")


def set_exclude_next(names: list) -> None:
    global _exclude_on_next
    _exclude_on_next = list(names)


def get_last_recommended() -> list:
    return list(_last_recommended)


def save_selected_recipe(recipe: dict) -> None:
    """사용자가 선택한 레시피 1개를 저장한다."""
    try:
        with open(_SELECTED_RECIPE_PATH, "w", encoding="utf-8") as f:
            json.dump(recipe, f, ensure_ascii=False, indent=2)
        print(f"[RECIPE CACHE] 선택 레시피 저장: {recipe.get('recipe_name', '')}")
    except Exception as e:
        print(f"[RECIPE CACHE] 저장 실패: {e}")


def load_selected_recipe() -> dict:
    """마지막으로 선택한 레시피를 반환한다. 없으면 빈 dict."""
    try:
        if not os.path.exists(_SELECTED_RECIPE_PATH):
            return {}
        with open(_SELECTED_RECIPE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data:
            print(f"[RECIPE CACHE] 선택 레시피 로드: {data.get('recipe_name', '')}")
            return data
    except Exception as e:
        print(f"[RECIPE CACHE] 로드 실패: {e}")
    return {}


def clear_selected_recipe() -> None:
    """선택된 레시피 캐시를 초기화한다. 새 추천 흐름 시작 시 호출."""
    try:
        if os.path.exists(_SELECTED_RECIPE_PATH):
            os.remove(_SELECTED_RECIPE_PATH)
            print("[RECIPE CACHE] 선택 레시피 초기화 완료")
    except Exception as e:
        print(f"[RECIPE CACHE] 초기화 실패: {e}")


# ──────────────────────────────────────────────────────────────────────
#  내부 DB 헬퍼
# ──────────────────────────────────────────────────────────────────────

def _conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_user_profile() -> dict:
    """User 테이블에서 알레르기·선호·비선호 정보를 읽어 반환."""
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM User LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if row:
            return {
                "allergies": row["allergy"] or "",
                "preferred_foods": row["preferred_food"] or "",
                "disliked_foods": row["disliked_food"] or "",
            }
    except Exception as e:
        print(f"[RECIPE SERVICE] 유저 프로필 조회 실패: {e}")
    return {"allergies": "", "preferred_foods": "", "disliked_foods": ""}


def _get_fridge_ingredients() -> list:
    """Inventory+Ingredient에서 현재 냉장고 재료 목록을 반환."""
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT Ingredient.ingredient_name, SUM(Inventory.quantity) AS total
            FROM Inventory
            JOIN Ingredient ON Inventory.ingredient_id = Ingredient.ingredient_id
            GROUP BY Ingredient.ingredient_id
            HAVING total > 0
        """)
        rows = cur.fetchall()
        conn.close()
        return [{"ingredient_name": r["ingredient_name"], "quantity": r["total"]}
                for r in rows]
    except Exception as e:
        print(f"[RECIPE SERVICE] 냉장고 재료 조회 실패: {e}")
    return []


def _get_today_nutrition() -> dict:
    """DailyNutrition 테이블에서 오늘 영양 합계를 반환."""
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM DailyNutrition WHERE date = DATE('now')")
        row = cur.fetchone()
        conn.close()
        if row:
            return {
                "total_calories": row["total_calories"],
                "total_protein": row["total_protein"],
                "total_sugar": row["total_sugar"],
                "total_sodium": row["total_sodium"],
                "total_fiber": row["total_fiber"],
                "total_saturated_fat": row["total_saturated_fat"],
            }
    except Exception as e:
        print(f"[RECIPE SERVICE] 영양 정보 조회 실패: {e}")
    return {}


def _get_recent_recipes() -> list:
    """최근 7일 내 먹은 레시피 이름 목록을 반환 (중복 제거)."""
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT Recipe.recipe_name
            FROM ConsumedRecipe
            JOIN Recipe ON ConsumedRecipe.recipe_id = Recipe.recipe_id
            WHERE ConsumedRecipe.consumed_date >= DATE('now', '-7 days')
        """)
        rows = cur.fetchall()
        conn.close()
        return [r["recipe_name"] for r in rows]
    except Exception as e:
        print(f"[RECIPE SERVICE] 최근 레시피 조회 실패: {e}")
    return []


# ──────────────────────────────────────────────────────────────────────
#  백엔드 응답 파싱
# ──────────────────────────────────────────────────────────────────────

def _match_ingredient(ingr_text: str, fridge_names: set) -> bool:
    """
    재료 문자열("밥 1공기", "양파 1/4개", "마늘 2쪽" 등)과
    냉장고 재료 이름 set("밥", "양파", "마늘" 등)을 비교한다.

    백엔드가 재료를 '이름+수량' 형태로 반환하므로
    단순 동등 비교 대신 '냉장고 재료 이름이 재료 문자열에 포함되는지' 확인한다.
    예) "양파 1/4개" → "양파" in "양파 1/4개"  → True
    """
    ingr_lower = ingr_text.strip()
    for fname in fridge_names:
        if fname and fname in ingr_lower:
            return True
    return False


def _parse_recommendation_response(bmo_response: str,
                                   fridge_names: set) -> list:
    """
    백엔드 /ask 의 bmo_response(Gemini 추천 텍스트)를 파싱해서
    RecipeScreen이 사용하는 dict 목록으로 변환한다.

    Gemini 출력 형식 예:
        1. 음식명: 김치볶음밥
        추천 이유: ...
        난이도: 쉬움
    """
    if not bmo_response:
        return []

    results = []
    blocks = re.split(r"\n(?=\d+\.\s)", bmo_response.strip())

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # 음식명
        name_match = re.search(
            r"(?:음식명\s*[:：]\s*|^\d+\.\s+)(.+?)(?:\n|$)", block
        )
        if not name_match:
            continue
        name = re.sub(r"^음식명\s*[:：]\s*", "", name_match.group(1)).strip()
        if not name:
            continue

        # 추천 이유 → description
        reason_match = re.search(r"추천\s*이유\s*[:：]\s*(.+?)(?:\n|$)", block)
        description = reason_match.group(1).strip() if reason_match else ""

        # 난이도
        diff_match = re.search(r"난이도\s*[:：]\s*(.+?)(?:\n|$)", block)
        difficulty = diff_match.group(1).strip() if diff_match else "-"

        # 조리 시간 (텍스트 안에 있으면 추출, 없으면 -)
        time_match = re.search(r"(\d+[~\-]?\d*\s*분)", block)
        cook_time = time_match.group(1).strip() if time_match else "-"

        # 재료 분류: 냉장고에 있는 것 vs 없는 것
        # 블록에서 재료 목록을 뽑아내기 (있으면 활용)
        ingr_match = re.search(r"재료\s*[:：]\s*(.+?)(?:\n|$)", block)
        if ingr_match:
            all_ingr = [i.strip() for i in re.split(r"[,，、]", ingr_match.group(1)) if i.strip()]
        else:
            all_ingr = []

        available = [i for i in all_ingr if _match_ingredient(i, fridge_names)]
        missing = [i for i in all_ingr if not _match_ingredient(i, fridge_names)]

        # Gemini 응답에 재료 목록이 없거나 매칭이 전혀 안 된 경우
        # → 냉장고 재료 전체를 available로 표시 (사용 가능 재료: 없음 방지)
        if not available and fridge_names:
            available = sorted(fridge_names)
            missing = []

        results.append({
            "recipe_name": name,
            "description": description,
            "difficulty": difficulty,
            "cook_time": cook_time,
            "available_ingredients": available,
            "missing_ingredients": missing,
            "steps": [],  # 조리순서는 선택하기 시점에 백엔드에서 받음
        })

    return results


def _parse_steps_response(steps_text: str) -> list:
    """
    백엔드 /select-recipe 의 result 텍스트에서 조리 단계만 추출한다.

    Gemini 출력 형식:
        조리 단계:
        1. ...
        2. ...
    """
    if not steps_text:
        return []

    steps = []
    in_steps = False
    for line in steps_text.splitlines():
        stripped = line.strip()
        if re.search(r"조리\s*단계", stripped):
            in_steps = True
            continue
        if in_steps:
            m = re.match(r"^(\d+)[.)]\s+(.+)", stripped)
            if m:
                steps.append(f"{m.group(1)}. {m.group(2)}")
            elif stripped.startswith("마지막"):
                steps.append(stripped)
            elif stripped and re.search(r"[:：]$", stripped):
                break  # 다음 섹션 시작

    # 조리 단계 섹션을 못 찾았으면 번호로 시작하는 줄 전체를 steps로
    if not steps:
        for line in steps_text.splitlines():
            m = re.match(r"^(\d+)[.)]\s+(.+)", line.strip())
            if m:
                steps.append(f"{m.group(1)}. {m.group(2)}")

    # 번호를 1. 2. 3. ... 으로 재정렬 (예: "3-1. ..." → "1. ...")
    renumbered = []
    for i, step in enumerate(steps, start=1):
        # "3-1. 내용", "1. 내용" 등 앞의 번호 패턴을 제거하고 새 번호 부여
        clean = re.sub(r"^\d+[-]?\d*[.)]\s*", "", step).strip()
        renumbered.append(f"{i}. {clean}")
    return renumbered


# ──────────────────────────────────────────────────────────────────────
#  RecipeService
# ──────────────────────────────────────────────────────────────────────

class RecipeService:

    def __init__(self):
        pass

    # ── 공개 API ──────────────────────────────────────────────────────

    def get_recommended_recipes(self, use_cache: bool = True) -> list:
        """
        냉장고 재료 + 유저 프로필 + 오늘 영양을 백엔드 /ask 에 보내
        Gemini 추천 결과를 파싱해 반환한다.
        실패 시 빈 리스트 반환.
        """
        global _last_recommended, _exclude_on_next
        profile = _get_user_profile()
        ingredients = _get_fridge_ingredients()
        today_nutrition = _get_today_nutrition()
        recent_recipes = _get_recent_recipes()
        fridge_names = {i["ingredient_name"] for i in ingredients}

        exclude = _exclude_on_next[:]
        _exclude_on_next = []

        # ── DB 우선 매칭 ───────────────────────────────────────────────
        try:
            import sys as _sys, os as _os
            _root = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
            if _root not in _sys.path:
                _sys.path.insert(0, _root)
            from db_bridge import get_matching_recipes as _get_matching
            db_matches = [r for r in _get_matching() if r["recipe_name"] not in exclude]
        except Exception as _e:
            print(f"[RECIPE SERVICE] DB 매칭 조회 실패: {_e}")
            db_matches = []

        if db_matches:
            # 커버되지 않는 냉장고 재료 확인
            covered = set()
            for r in db_matches:
                covered.update(r.get("required_ingredients", []))
            uncovered = fridge_names - covered

            if not uncovered:
                # 냉장고 재료가 전부 DB 레시피로 커버됨 → DB 결과 반환
                print(f"[RECIPE SERVICE] DB 매칭 사용: {[r['recipe_name'] for r in db_matches[:3]]}")
                result = []
                for r in db_matches[:3]:
                    ingr = r.get("required_ingredients", [])
                    result.append({
                        "recipe_name": r["recipe_name"],
                        "description": f"칼로리 {r.get('calories') or '-'}kcal",
                        "difficulty": "-",
                        "cook_time": "-",
                        "available_ingredients": ingr,
                        "missing_ingredients": [],
                        "steps": [],
                    })
                _last_recommended = [r["recipe_name"] for r in result]
                return result
            else:
                print(f"[RECIPE SERVICE] 커버 안 되는 재료 있음({uncovered}) → Gemini 호출")
        else:
            print("[RECIPE SERVICE] DB 매칭 없음 → Gemini 호출")

        # ── Gemini API 호출 ────────────────────────────────────────────
        exclude_text = ""
        if exclude:
            exclude_text = f" 다음 음식들은 이미 추천했으니 반드시 제외해줘: {', '.join(exclude)}."

        payload = {
            "text": (
                "냉장고 재료와 내 영양 상태를 고려해서 "
                "만들 수 있는 요리 3가지를 자유롭게 추천해줘. "
                "DB에 등록된 레시피에 한정하지 말고 다양하게 추천해줘."
                + exclude_text
            ),
            "profile": profile,
            "ingredients": ingredients,
            "today_nutrition": today_nutrition,
            "recent_meals": recent_recipes,
            "force_recommendation": True,
        }

        print(f"[RECIPE SERVICE] /ask 요청 — 재료 {len(ingredients)}개, "
              f"알레르기: {profile.get('allergies') or '없음'}")

        try:
            resp = requests.post(
                f"{_BACKEND_URL}/ask",
                json=payload,
                timeout=_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
            bmo_response = data.get("result", {}).get("bmo_response", "")
            parsed = data.get("result", {}).get("parsed_recommendations", [])
            print(f"[RECIPE SERVICE] 추천 응답 수신 ({len(bmo_response)}자)")

            if parsed:
                recipes = []
                for p in parsed:
                    name = p.get("name", "")
                    if not name:
                        continue
                    all_ingr = [i.strip() for i in re.split(r"[,，、]", p.get("ingredients", "")) if i.strip()]
                    available = [i for i in all_ingr if _match_ingredient(i, fridge_names)]
                    missing = [i for i in all_ingr if not _match_ingredient(i, fridge_names)]
                    # 재료 매칭 실패 시 냉장고 재료 전체를 available로 표시
                    if not available and fridge_names:
                        available = sorted(fridge_names)
                        missing = []
                    recipes.append({
                        "recipe_name": name,
                        "description": p.get("reason", ""),
                        "difficulty": p.get("difficulty", "-"),
                        "cook_time": p.get("cook_time", "-"),
                        "available_ingredients": available,
                        "missing_ingredients": missing,
                        "steps": p.get("steps", []),
                    })
            else:
                recipes = _parse_recommendation_response(bmo_response, fridge_names)

            print(f"[RECIPE SERVICE] 파싱 결과: {[r['recipe_name'] for r in recipes]}")

            _last_recommended = [r["recipe_name"] for r in recipes]
            save_cached_recipes(recipes)
            return recipes

        except requests.RequestException as e:
            print(f"[RECIPE SERVICE] 백엔드 연결 실패: {e}")
            return []
        except Exception as e:
            print(f"[RECIPE SERVICE] 추천 처리 중 오류: {e}")
            return []

    def get_recipe_steps(self, recipe_name: str) -> list:
        """
        백엔드 /select-recipe 에 레시피 이름을 보내
        Gemini가 생성한 조리 단계 리스트를 반환한다.
        """
        print(f"[RECIPE SERVICE] /select-recipe 요청: {recipe_name}")
        try:
            resp = requests.post(
                f"{_BACKEND_URL}/select-recipe",
                json={"recipe_name": recipe_name},
                timeout=_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
            steps_text = data.get("result", "")
            steps = _parse_steps_response(steps_text)
            print(f"[RECIPE SERVICE] 조리 단계 {len(steps)}개 수신")
            return steps, steps_text
        except requests.RequestException as e:
            print(f"[RECIPE SERVICE] /select-recipe 실패: {e}")
            return [], ""
        except Exception as e:
            print(f"[RECIPE SERVICE] 조리 단계 처리 중 오류: {e}")
            return [], ""

    def select_recipe(self, recipe) -> dict | None:
        """UI에서 선택된 레시피 dict를 그대로 반환 (None 가드 포함)."""
        if recipe is None:
            return None
        if isinstance(recipe, dict):
            return recipe
        return None

    def build_selected_recipe_log(self, recipe: dict) -> str:
        name = recipe.get("recipe_name", "알 수 없음")
        return f"[RECIPE UI] 선택한 레시피: {name}"