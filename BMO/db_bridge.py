import sqlite3
import os

DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "DB", "capstonedb.db")
)


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# 냉장고 전체 재고를 Ollama 프롬프트용 문자열로 반환
def get_fridge_context() -> str:
    conn = _conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT Ingredient.ingredient_name, Ingredient.category,
               SUM(Inventory.quantity) AS total,
               Inventory.unit
        FROM Inventory
        JOIN Ingredient ON Inventory.ingredient_id = Ingredient.ingredient_id
        GROUP BY Ingredient.ingredient_id
        HAVING total > 0
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "현재 냉장고에 재료가 없어."

    lines = ["현재 냉장고 재료:"]
    for row in rows:
        unit = row['unit'] or '개'
        total = row['total']
        # 정수면 소수점 없이 표시
        qty_str = str(int(total)) if total == int(total) else str(total)
        lines.append(f"- {row['ingredient_name']} ({row['category']}): {qty_str}{unit}")

    return "\n".join(lines)


# 냉장고 재료 이름 목록 반환
def get_fridge_ingredient_names() -> list[str]:
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT Ingredient.ingredient_name
        FROM Inventory
        JOIN Ingredient ON Inventory.ingredient_id = Ingredient.ingredient_id
        GROUP BY Ingredient.ingredient_id
        HAVING SUM(Inventory.quantity) > 0
    """)
    names = [row["ingredient_name"] for row in cursor.fetchall()]
    conn.close()
    return names


# 냉장고 재료로 만들 수 있는 레시피 목록 반환 (재료가 모두 있는 레시피만)
def get_matching_recipes() -> list[dict]:
    conn = _conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT Ingredient.ingredient_name
        FROM Inventory
        JOIN Ingredient ON Inventory.ingredient_id = Ingredient.ingredient_id
        GROUP BY Ingredient.ingredient_id
        HAVING SUM(Inventory.quantity) > 0
    """)
    fridge = {row["ingredient_name"] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT r.recipe_id, r.recipe_name, r.calories, r.protein, r.sugar,
               r.sodium, r.fiber, r.saturated_fat,
               GROUP_CONCAT(i.ingredient_name, '||') AS ingredient_list
        FROM Recipe r
        LEFT JOIN RecipeIngredient ri ON r.recipe_id = ri.recipe_id
        LEFT JOIN Ingredient i ON ri.ingredient_id = i.ingredient_id
        GROUP BY r.recipe_id
    """)
    recipes = cursor.fetchall()
    conn.close()

    matching = []
    for recipe in recipes:
        raw = recipe["ingredient_list"] or ""
        required = set(filter(None, raw.split("||"))) if raw else set()
        if required and required.issubset(fridge):
            matching.append({
                "recipe_name": recipe["recipe_name"],
                "calories": recipe["calories"],
                "protein": recipe["protein"],
                "sugar": recipe["sugar"],
                "sodium": recipe["sodium"],
                "fiber": recipe["fiber"],
                "saturated_fat": recipe["saturated_fat"],
                "required_ingredients": sorted(required),
            })

    return matching


# 전체 레시피 목록(재료 + 영양정보)을 Ollama 프롬프트용 문자열로 반환 (레시피 추천 시 사용)
def get_recipe_list_context() -> str:
    conn = _conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.recipe_id, r.recipe_name, r.calories, r.protein, r.sugar,
               r.sodium, r.fiber, r.saturated_fat,
               GROUP_CONCAT(i.ingredient_name || ' ' || ri.amount, ', ') AS ingredients
        FROM Recipe r
        LEFT JOIN RecipeIngredient ri ON r.recipe_id = ri.recipe_id
        LEFT JOIN Ingredient i ON ri.ingredient_id = i.ingredient_id
        GROUP BY r.recipe_id
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "등록된 레시피가 없어."

    lines = ["등록된 레시피 목록:"]
    for row in rows:
        lines.append(
            f"- {row['recipe_name']}: "
            f"{row['calories']}kcal, "
            f"단백질 {row['protein']}g, 당류 {row['sugar']}g, "
            f"나트륨 {row['sodium']}mg, 식이섬유 {row['fiber']}g, 포화지방 {row['saturated_fat']}g | "
            f"재료: {row['ingredients'] or '없음'}"
        )

    return "\n".join(lines)

# 음식 이름으로 ConsumedRecipe에 저장 (Recipe 테이블에 없으면 자동 추가)
def save_consumed_recipe(food_name: str, nutrition: dict = None):
    """
    food_name: 음식 이름
    nutrition: 영양 정보 dict (calories, protein, sugar, sodium, fiber, saturated_fat)
               값이 있으면 Recipe 테이블에 영양소도 함께 저장/업데이트한다.
    """
    if not food_name:
        return
    conn = _conn()
    cursor = conn.cursor()
    try:
        # Recipe 테이블에 있는지 확인
        cursor.execute("SELECT recipe_id, calories FROM Recipe WHERE recipe_name = ?", (food_name,))
        row = cursor.fetchone()

        if row:
            recipe_id = row["recipe_id"]
            # 기존 레시피의 영양소가 0이고 새로운 영양 정보가 있으면 업데이트
            if nutrition and nutrition.get("calories", 0) > 0 and (row["calories"] or 0) == 0:
                cursor.execute(
                    """UPDATE Recipe SET
                        calories = ?, protein = ?, sugar = ?,
                        sodium = ?, fiber = ?, saturated_fat = ?
                    WHERE recipe_id = ?""",
                    (
                        nutrition.get("calories", 0),
                        nutrition.get("protein", 0),
                        nutrition.get("sugar", 0),
                        nutrition.get("sodium", 0),
                        nutrition.get("fiber", 0),
                        nutrition.get("saturated_fat", 0),
                        recipe_id,
                    )
                )
                print(f"[DB] 레시피 영양소 업데이트: {food_name}")
        else:
            # 없으면 영양소와 함께 새로 추가
            n = nutrition or {}
            cursor.execute(
                """INSERT INTO Recipe
                    (recipe_name, calories, protein, sugar, sodium, fiber, saturated_fat)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    food_name,
                    n.get("calories", 0),
                    n.get("protein", 0),
                    n.get("sugar", 0),
                    n.get("sodium", 0),
                    n.get("fiber", 0),
                    n.get("saturated_fat", 0),
                )
            )
            recipe_id = cursor.lastrowid
            print(f"[DB] 새 레시피 추가 (영양소 포함): {food_name}")

        # ConsumedRecipe에 저장
        cursor.execute(
            "INSERT INTO ConsumedRecipe (recipe_id, consumed_date) VALUES (?, DATE('now'))",
            (recipe_id,)
        )
        conn.commit()
        print(f"[DB] 먹은 음식 저장: {food_name}")
    except Exception as e:
        print(f"[DB] 먹은 음식 저장 실패: {e}")
    finally:
        conn.close()


def purge_expired_inventory():
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Inventory WHERE expiration_date < DATE('now')")
    conn.commit()
    conn.close()


# 7일 지난 ConsumedRecipe 삭제
def purge_old_consumed_recipes():
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ConsumedRecipe WHERE consumed_date < DATE('now', '-7 days')")
    conn.commit()
    conn.close()


# 7일 지난 DailyNutrition 삭제
def purge_old_nutrition():
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM DailyNutrition WHERE date < DATE('now', '-7 days')")
    conn.commit()
    conn.close()


# 하루 영양 누적 저장 (같은 날짜면 합산)
def add_daily_nutrition(nutrition: dict):
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO DailyNutrition (
            date, total_calories, total_protein, total_sugar,
            total_sodium, total_fiber, total_saturated_fat
        )
        VALUES (DATE('now'), ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            total_calories    = total_calories    + excluded.total_calories,
            total_protein     = total_protein     + excluded.total_protein,
            total_sugar       = total_sugar       + excluded.total_sugar,
            total_sodium      = total_sodium      + excluded.total_sodium,
            total_fiber       = total_fiber       + excluded.total_fiber,
            total_saturated_fat = total_saturated_fat + excluded.total_saturated_fat
    """, (
        nutrition.get("calories", 0),
        nutrition.get("protein", 0),
        nutrition.get("sugar", 0),
        nutrition.get("sodium", 0),
        nutrition.get("fiber", 0),
        nutrition.get("saturated_fat", 0),
    ))
    conn.commit()
    conn.close()


# 오늘 날짜 영양 합계 조회
def get_today_nutrition() -> dict:
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM DailyNutrition WHERE date = DATE('now')")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}


# 영양 균형 분석
def analyze_nutrition_balance(data: dict) -> dict:
    if not data:
        return {"analysis": "아직 데이터 없음", "부족한영양소": [], "과다영양소": []}

    부족 = []
    과다 = []

    if (data.get("total_protein") or 0) < 50:
        부족.append("단백질")
    if (data.get("total_fiber") or 0) < 20:
        부족.append("식이섬유")
    if (data.get("total_sodium") or 0) > 2000:
        과다.append("나트륨")
    if (data.get("total_sugar") or 0) > 50:
        과다.append("당류")

    return {"analysis": "영양 상태 분석 완료", "부족한영양소": 부족, "과다영양소": 과다}


def get_user_allergy() -> str:
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("SELECT allergy FROM User LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row["allergy"] if row and row["allergy"] else ""


def add_user_allergy(new_item: str):
    """기존 알레르기 목록에 new_item을 추가한다. 중복은 무시."""
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("SELECT rowid, allergy FROM User LIMIT 1")
    row = cursor.fetchone()

    if row:
        existing = [a.strip() for a in (row["allergy"] or "").split(",") if a.strip()]
        if new_item not in existing:
            existing.append(new_item)
        updated = ", ".join(existing)
        cursor.execute("UPDATE User SET allergy = ? WHERE rowid = ?", (updated, row["rowid"]))
    else:
        cursor.execute(
            "INSERT INTO User (name, allergy, preferred_food, disliked_food, diet_habit, health_status) VALUES (?, ?, '', '', '', '')",
            ("사용자", new_item),
        )
    conn.commit()
    conn.close()


def remove_user_allergy(item: str):
    """알레르기 목록에서 item을 제거한다."""
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("SELECT rowid, allergy FROM User LIMIT 1")
    row = cursor.fetchone()
    if row:
        existing = [a.strip() for a in (row["allergy"] or "").split(",") if a.strip() and a.strip() != item]
        cursor.execute("UPDATE User SET allergy = ? WHERE rowid = ?", (", ".join(existing), row["rowid"]))
        conn.commit()
    conn.close()


# 레시피에 필요하지만 재고가 없는 부족 재료를 Ollama 프롬프트용 문자열로 반환
def get_missing_context(recipe_name: str) -> str:
    conn = _conn()
    cursor = conn.cursor()

    cursor.execute("SELECT recipe_id FROM Recipe WHERE recipe_name = ?", (recipe_name,))
    recipe = cursor.fetchone()

    if not recipe:
        conn.close()
        return f"'{recipe_name}' 레시피가 없어."

    cursor.execute("""
        SELECT i.ingredient_name, ri.amount, ri.unit
        FROM RecipeIngredient ri
        JOIN Ingredient i ON ri.ingredient_id = i.ingredient_id
        WHERE ri.recipe_id = ?
    """, (recipe["recipe_id"],))
    recipe_ingredients = cursor.fetchall()

    missing = []
    for item in recipe_ingredients:
        cursor.execute("""
            SELECT SUM(Inventory.quantity)
            FROM Inventory
            WHERE Inventory.ingredient_id = (
                SELECT ingredient_id FROM Ingredient WHERE ingredient_name = ?
            )
        """, (item["ingredient_name"],))
        result = cursor.fetchone()
        if result[0] is None:
            missing.append(f"- {item['ingredient_name']} ({item['amount']}{item['unit']})")

    conn.close()

    if not missing:
        return f"'{recipe_name}' 재료 모두 보유 중."

    return f"'{recipe_name}' 부족 재료:\n" + "\n".join(missing)

# 단위 정규화 테이블 (db_bridge 전역 공유)
_UNIT_ALIASES = {
    "g": "g", "그램": "g",
    "kg": "kg", "킬로그램": "kg", "킬로": "kg",
    "ml": "ml", "밀리": "ml", "밀리리터": "ml",
    "l": "L", "리터": "L", "L": "L",
    "개": "개", "ea": "개",
    "봉": "봉지", "봉지": "봉지", "봉투": "봉지",
    "팩": "팩", "pack": "팩",
    "병": "병", "캔": "캔", "통": "통",
    "장": "장", "묶음": "묶음", "알": "알",
    "컵": "컵", "인분": "인분", "마리": "마리",
}

_UNIT_PATTERN = r'(\d+(?:\.\d+)?)\s*(g|kg|ml|l|L|그램|킬로그램|킬로|밀리리터|밀리|리터|개|봉지|봉투?|팩|병|캔|통|장|묶음|알|컵|인분|마리|ea)'


def _parse_qty_unit(text: str):
    """
    문자열에서 (수량:float, 단위:str) 추출.
    예) '300g' → (300.0, 'g'), '3개' → (3.0, '개'), '2' → (2.0, '개')
    """
    import re as _re
    m = _re.search(_UNIT_PATTERN, str(text), _re.IGNORECASE)
    if m:
        qty = float(m.group(1))
        raw = m.group(2).lower().rstrip('투')  # 봉투 → 봉지 처리
        unit = _UNIT_ALIASES.get(raw, raw)
        return qty, unit
    m2 = _re.search(r'(\d+(?:\.\d+)?)', str(text))
    if m2:
        return float(m2.group(1)), "개"
    return None, None


# 재료 목록을 Ingredient + Inventory 테이블에 저장 (영수증 OCR 결과 등에서 사용)
def save_ingredient_items(items: list) -> int:
    """
    items: [{"ingredient_name": str, "quantity": int/float/str, "unit": str(optional)}, ...]
    - unit 필드가 있으면 그걸 사용, 없으면 quantity 문자열에서 파싱 ("300g", "2개" 등)
    - 같은 재료라도 단위가 다르면 별도 행으로 저장
    - 저장 성공한 재료 수를 반환
    """
    if not items:
        return 0

    conn = _conn()
    cursor = conn.cursor()
    saved = 0

    try:
        for item in items:
            name = str(item.get("ingredient_name") or item.get("name") or "").strip()
            if not name:
                continue

            raw_qty = item.get("quantity") or item.get("count")
            raw_unit = str(item.get("unit", "") or "").strip()

            if raw_unit:
                unit = _UNIT_ALIASES.get(raw_unit.lower(), raw_unit)
                try:
                    quantity = float(raw_qty) if raw_qty is not None else 1.0
                except (ValueError, TypeError):
                    quantity = 1.0
            else:
                # quantity에 "300g" 같은 복합 문자열이 올 수 있음
                parsed_qty, parsed_unit = _parse_qty_unit(str(raw_qty) if raw_qty is not None else "")
                if parsed_qty is not None:
                    quantity, unit = parsed_qty, parsed_unit
                else:
                    quantity, unit = 1.0, "개"

            if quantity <= 0:
                continue

            # Ingredient 확인 / 추가
            cursor.execute(
                "SELECT ingredient_id FROM Ingredient WHERE ingredient_name = ?",
                (name,)
            )
            row = cursor.fetchone()
            if row:
                ingredient_id = row["ingredient_id"]
            else:
                cursor.execute(
                    "INSERT INTO Ingredient (ingredient_name, category) VALUES (?, ?)",
                    (name, "기타")
                )
                ingredient_id = cursor.lastrowid

            # 같은 재료 + 같은 단위 행만 합산 (단위 다르면 별도 행)
            cursor.execute(
                "SELECT inventory_id FROM Inventory WHERE ingredient_id = ? AND unit = ?",
                (ingredient_id, unit)
            )
            inv = cursor.fetchone()
            if inv:
                cursor.execute(
                    "UPDATE Inventory SET quantity = quantity + ? WHERE inventory_id = ?",
                    (quantity, inv["inventory_id"])
                )
            else:
                cursor.execute(
                    "INSERT INTO Inventory (ingredient_id, quantity, unit) VALUES (?, ?, ?)",
                    (ingredient_id, quantity, unit)
                )

            saved += 1
            qty_str = str(int(quantity)) if quantity == int(quantity) else str(quantity)
            print(f"[DB] 재료 저장: {name} x{qty_str}{unit}")

        conn.commit()
    except Exception as e:
        print(f"[DB] 재료 저장 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

    return saved


# 레시피 사용 시 재료 목록을 받아 Inventory에서 실제 사용량만큼 차감 (0 이하면 행 삭제)
def deduct_recipe_ingredients(ingredient_names: list) -> int:
    """
    ingredient_names: ["양파 1/2개", "당근 1/4개", "대파 2개", ...] — available_ingredients 리스트
    각 재료의 실제 사용량과 단위를 파싱해 Inventory quantity에서 차감한다.
    단위가 일치하는 행에서만 차감. 단위 없으면 아무 행에서나 차감.
    차감 후 0 이하가 되면 행을 삭제한다.
    처리된 재료 수를 반환한다.
    """
    import re as _re
    from fractions import Fraction as _Frac

    def _parse_amount_unit(text: str):
        # 분수 먼저 (1/2개 등)
        frac = _re.search(r'(\d+)\s*/\s*(\d+)', text)
        if frac:
            qty = float(_Frac(int(frac.group(1)), int(frac.group(2))))
            # 분수 뒤 단위
            um = _re.search(_UNIT_PATTERN, text[frac.end():], _re.IGNORECASE)
            unit = _UNIT_ALIASES.get(um.group(2).lower(), um.group(2)) if um else None
            return qty, unit
        # 수량+단위
        m = _re.search(_UNIT_PATTERN, text, _re.IGNORECASE)
        if m:
            return float(m.group(1)), _UNIT_ALIASES.get(m.group(2).lower(), m.group(2))
        # 숫자만
        num = _re.search(r'(\d+(?:\.\d+)?)', text)
        if num:
            return float(num.group(1)), None
        return 1.0, None

    if not ingredient_names:
        return 0

    conn = _conn()
    cursor = conn.cursor()
    deducted = 0

    try:
        # 현재 인벤토리 전체 로드 (부분 매칭용)
        cursor.execute("""
            SELECT Inventory.inventory_id, Inventory.quantity, Inventory.unit,
                   Ingredient.ingredient_name
            FROM Inventory
            JOIN Ingredient ON Inventory.ingredient_id = Ingredient.ingredient_id
            WHERE Inventory.quantity > 0
        """)
        inv_rows = [dict(r) for r in cursor.fetchall()]

        for ingr_text in ingredient_names:
            ingr_text = ingr_text.strip()
            if not ingr_text:
                continue

            use_amount, use_unit = _parse_amount_unit(ingr_text)

            # 부분 매칭: 재료명 포함 행 찾기
            candidates = []
            for row in inv_rows:
                iname = row["ingredient_name"] or ""
                if iname in ingr_text or ingr_text in iname:
                    candidates.append(row)

            if not candidates:
                print(f"[DB] 재료 차감 건너뜀 (인벤토리 없음): {ingr_text}")
                continue

            # 단위 일치 우선, 없으면 첫 번째 후보
            matched = None
            if use_unit:
                for row in candidates:
                    if row.get("unit") == use_unit:
                        matched = row
                        break
            if not matched:
                matched = candidates[0]

            new_qty = round(matched["quantity"] - use_amount, 4)
            if new_qty <= 0:
                cursor.execute(
                    "DELETE FROM Inventory WHERE inventory_id = ?",
                    (matched["inventory_id"],)
                )
                unit_str = matched.get("unit") or "개"
                print(f"[DB] 재료 소진 삭제: {matched['ingredient_name']} "
                      f"({matched['quantity']}{unit_str} - {use_amount}{unit_str} ≤ 0)")
            else:
                cursor.execute(
                    "UPDATE Inventory SET quantity = ? WHERE inventory_id = ?",
                    (new_qty, matched["inventory_id"])
                )
                unit_str = matched.get("unit") or "개"
                print(f"[DB] 재료 차감: {matched['ingredient_name']} "
                      f"{matched['quantity']}{unit_str} → {new_qty}{unit_str}")

            inv_rows = [r for r in inv_rows if r["inventory_id"] != matched["inventory_id"]]
            if new_qty > 0:
                inv_rows.append({
                    "inventory_id": matched["inventory_id"],
                    "quantity": new_qty,
                    "unit": matched.get("unit"),
                    "ingredient_name": matched["ingredient_name"]
                })

            deducted += 1

        conn.commit()
    except Exception as e:
        print(f"[DB] 재료 차감 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

    return deducted


def remove_ingredient_fully(ingredient_name: str) -> bool:
    """
    재료 이름으로 Inventory의 해당 재료 행을 전량 삭제한다.
    "양파 다 먹었어" 같은 전량 소비 발화에 사용.
    삭제 성공 시 True, 재료 없으면 False.
    """
    conn = _conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT ingredient_id FROM Ingredient WHERE ingredient_name = ?",
            (ingredient_name,)
        )
        row = cursor.fetchone()
        if not row:
            print(f"[DB] 전량 삭제 실패: '{ingredient_name}' Ingredient 없음")
            return False

        ingredient_id = row["ingredient_id"]
        cursor.execute(
            "DELETE FROM Inventory WHERE ingredient_id = ?",
            (ingredient_id,)
        )
        deleted = cursor.rowcount
        conn.commit()
        if deleted > 0:
            print(f"[DB] 전량 삭제 완료: {ingredient_name} ({deleted}행)")
            return True
        else:
            print(f"[DB] 전량 삭제: '{ingredient_name}' Inventory 행 없음")
            return False
    except Exception as e:
        print(f"[DB] 전량 삭제 실패: {e}")
        return False
    finally:
        conn.close()


def consume_ingredient(ingredient_name: str, quantity: float, unit: str) -> dict:
    """
    음성 소비 인텐트 전용 차감 함수.
    - quantity > 0, unit 있음: 해당 단위 행에서 지정 수량만큼 차감
    - quantity <= 0 또는 unit == 'all': 전량 삭제 (remove_ingredient_fully 위임)
    반환: {"success": bool, "removed_all": bool, "remaining": float, "unit": str}
    """
    if quantity <= 0 or unit == "all":
        ok = remove_ingredient_fully(ingredient_name)
        return {"success": ok, "removed_all": True, "remaining": 0.0, "unit": ""}

    conn = _conn()
    cursor = conn.cursor()
    try:
        # Ingredient 조회 (부분 매칭 포함)
        cursor.execute(
            "SELECT ingredient_id FROM Ingredient WHERE ingredient_name = ?",
            (ingredient_name,)
        )
        row = cursor.fetchone()
        if not row:
            # 부분 매칭 시도
            cursor.execute(
                "SELECT ingredient_id, ingredient_name FROM Ingredient WHERE ingredient_name LIKE ?",
                (f"%{ingredient_name}%",)
            )
            row = cursor.fetchone()
        if not row:
            print(f"[DB] 소비 차감 실패: '{ingredient_name}' 없음")
            return {"success": False, "removed_all": False, "remaining": 0.0, "unit": unit}

        ingredient_id = row["ingredient_id"]

        # 단위 일치 행 우선, 없으면 아무 행
        cursor.execute(
            "SELECT inventory_id, quantity, unit FROM Inventory WHERE ingredient_id = ? AND unit = ? AND quantity > 0",
            (ingredient_id, unit)
        )
        inv = cursor.fetchone()
        if not inv:
            cursor.execute(
                "SELECT inventory_id, quantity, unit FROM Inventory WHERE ingredient_id = ? AND quantity > 0",
                (ingredient_id,)
            )
            inv = cursor.fetchone()
        if not inv:
            print(f"[DB] 소비 차감 실패: '{ingredient_name}' Inventory 없음")
            return {"success": False, "removed_all": False, "remaining": 0.0, "unit": unit}

        actual_unit = inv["unit"] or unit
        new_qty = round(inv["quantity"] - quantity, 4)

        if new_qty <= 0:
            cursor.execute("DELETE FROM Inventory WHERE inventory_id = ?", (inv["inventory_id"],))
            conn.commit()
            print(f"[DB] 소비 소진 삭제: {ingredient_name} {inv['quantity']}{actual_unit} - {quantity}{actual_unit}")
            return {"success": True, "removed_all": True, "remaining": 0.0, "unit": actual_unit}
        else:
            cursor.execute("UPDATE Inventory SET quantity = ? WHERE inventory_id = ?", (new_qty, inv["inventory_id"]))
            conn.commit()
            print(f"[DB] 소비 차감: {ingredient_name} {inv['quantity']}{actual_unit} → {new_qty}{actual_unit}")
            return {"success": True, "removed_all": False, "remaining": new_qty, "unit": actual_unit}

    except Exception as e:
        print(f"[DB] 소비 차감 오류: {e}")
        return {"success": False, "removed_all": False, "remaining": 0.0, "unit": unit}
    finally:
        conn.close()