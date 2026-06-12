import sqlite3
from datetime import datetime

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# 오늘 날짜
today = datetime.now().strftime("%Y-%m-%d")

# 오늘 섭취한 레시피 영양 조회
cursor.execute("""
SELECT
    Recipe.calories,
    Recipe.protein,
    Recipe.sugar,
    Recipe.sodium,
    Recipe.fiber,
    Recipe.saturated_fat
FROM ConsumedRecipe

JOIN Recipe
ON ConsumedRecipe.recipe_id = Recipe.recipe_id

WHERE ConsumedRecipe.consumed_date = ?
""", (today,))

rows = cursor.fetchall()

# 총 영양 계산
total_calories = 0
total_protein = 0
total_sugar = 0
total_sodium = 0
total_fiber = 0
total_saturated_fat = 0

for row in rows:
    total_calories += row[0]
    total_protein += row[1]
    total_sugar += row[2]
    total_sodium += row[3]
    total_fiber += row[4]
    total_saturated_fat += row[5]

print("\n===== 오늘 총 섭취 영양 =====")
print(f"칼로리 : {total_calories}")
print(f"단백질 : {total_protein}")
print(f"당류 : {total_sugar}")
print(f"나트륨 : {total_sodium}")
print(f"식이섬유 : {total_fiber}")
print(f"포화지방 : {total_saturated_fat}")

# 기존 DailyNutrition 존재 확인
cursor.execute("""
SELECT date
FROM DailyNutrition
WHERE date = ?
""", (today,))
result = cursor.fetchone()

# 이미 존재하면 UPDATE
if result:
    cursor.execute("""
    UPDATE DailyNutrition
    SET
        total_calories = ?,
        total_protein = ?,
        total_sugar = ?,
        total_sodium = ?,
        total_fiber = ?,
        total_saturated_fat = ?

    WHERE date = ?
    """, (
        total_calories,
        total_protein,
        total_sugar,
        total_sodium,
        total_fiber,
        total_saturated_fat,

        today
    ))
    print("\n기존 DailyNutrition 업데이트 완료")

# 없으면 INSERT
else:
    cursor.execute("""
    INSERT INTO DailyNutrition(
        date,
        total_calories,
        total_protein,
        total_sugar,
        total_sodium,
        total_fiber,
        total_saturated_fat
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        today,
        total_calories,
        total_protein,
        total_sugar,
        total_sodium,
        total_fiber,
        total_saturated_fat
    ))
    print("\n새로운 하루 영양분 데이터 저장 완료")

conn.commit()
conn.close()

print("\n하루 영양분 데이터 저장 완료")