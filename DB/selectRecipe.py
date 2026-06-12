import sqlite3

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# 조회할 레시피명(임시)
search_recipe = "양파 달걀 볶음"

# Recipe 조회
cursor.execute("""
SELECT
    recipe_id,
    recipe_name,
    content,
    calories,
    protein,
    sugar,
    sodium,
    fiber,
    saturated_fat,
    recommended_date
FROM Recipe

WHERE recipe_name = ?
""", (search_recipe,))

recipe = cursor.fetchone()

# 레시피 존재 확인
if recipe:
    recipe_id = recipe[0]
    recipe_name = recipe[1]
    content = recipe[2]
    calories = recipe[3]
    protein = recipe[4]
    sugar = recipe[5]
    sodium = recipe[6]
    fiber = recipe[7]
    saturated_fat = recipe[8]
    recommended_date = recipe[9]

    print(f"""
===== 레시피 조회 =====

레시피명 : {recipe_name}

레시피 설명 : {content}

추천 날짜 : {recommended_date}

===== 영양 정보 =====

칼로리 : {calories}
단백질 : {protein}
당류 : {sugar}
나트륨 : {sodium}
식이섬유 : {fiber}
포화지방 : {saturated_fat}
""")
    
    # 사용 식재료 조회
    cursor.execute("""
    SELECT
        Ingredient.ingredient_name,
        RecipeIngredient.amount
    FROM RecipeIngredient
    JOIN Ingredient
    ON RecipeIngredient.ingredient_id = Ingredient.ingredient_id
    WHERE RecipeIngredient.recipe_id = ?
    """, (recipe_id,))

    ingredients = cursor.fetchall()

    print("===== 사용 재료 =====")

    for item in ingredients:
        ingredient_name = item[0]
        amount = item[1]

        print(f"- {ingredient_name} : {amount}")
else:
    print("해당 레시피가 없습니다.")

conn.close()

print("\n조회 완료")
