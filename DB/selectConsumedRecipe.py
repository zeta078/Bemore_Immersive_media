import sqlite3

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# 조회할 레시피명(임시)
recipe_name = "양파 달걀 볶음"

# 섭취 기록 조회
cursor.execute("""
SELECT
    Recipe.recipe_name,
    COUNT(ConsumedRecipe.consumed_id),
    MAX(ConsumedRecipe.consumed_date)
FROM ConsumedRecipe

JOIN Recipe
ON ConsumedRecipe.recipe_id = Recipe.recipe_id

WHERE Recipe.recipe_name = ?

GROUP BY Recipe.recipe_name
""", (recipe_name,))

result = cursor.fetchone()

# 결과 출력
if result:
    recipe_name = result[0]
    total_count = result[1]
    last_consumed_date = result[2]

    print(f"""
===== 레시피 섭취 기록 =====

레시피명 : {recipe_name}

총 섭취 횟수 : {total_count}회

마지막 섭취 날짜 : {last_consumed_date}
""")
else:
    print("섭취 기록이 없습니다.")

conn.close()

print("조회 완료")