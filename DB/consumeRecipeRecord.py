import sqlite3
from datetime import datetime

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# 섭취한 레시피명(임시)
recipe_name = "양파 달걀 볶음"

# recipe_id 조회
cursor.execute("""
SELECT recipe_id
FROM Recipe
WHERE recipe_name = ?
""", (recipe_name,))
recipe = cursor.fetchone()

# 레시피 확인
if recipe is None:
    print("레시피가 없습니다.")
else:
    recipe_id = recipe[0]

    # 오늘 날짜
    consumed_date = datetime.now().strftime("%Y-%m-%d")

    # ConsumedRecipe 저장
    cursor.execute("""
    INSERT INTO ConsumedRecipe(
        recipe_id,
        consumed_date
    )
    VALUES (?, ?)
    """, (
        recipe_id,
        consumed_date
    ))

    conn.commit()

conn.close()
print("레시피 섭취 기록 저장 완료")