import sqlite3

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# 조회할 레시피명(임시)
recipe_name = "양파 달걀 볶음"

# recipe_id 조회
cursor.execute("""
SELECT recipe_id
FROM Recipe
WHERE recipe_name = ?
""", (recipe_name,))

recipe = cursor.fetchone()

# 레시피 존재 확인
if recipe is None:
    print("레시피가 없습니다.")
else:
    recipe_id = recipe[0]

    print(f"\n===== {recipe_name} 부족 재료 조회 =====")

    # 레시피 재료 조회
    cursor.execute("""
    SELECT
        Ingredient.ingredient_name,
        RecipeIngredient.amount
    FROM RecipeIngredient
    JOIN Ingredient
    ON RecipeIngredient.ingredient_id = Ingredient.ingredient_id
    WHERE RecipeIngredient.recipe_id = ?
    """, (recipe_id,))

    recipe_ingredients = cursor.fetchall()
    missing_ingredients = []

    # 재고 비교
    for item in recipe_ingredients:
        ingredient_name = item[0]
        amount = item[1]

        # 현재 재고 수량 확인
        cursor.execute("""
        SELECT SUM(Inventory.quantity)

        FROM Inventory

        JOIN Ingredient
        ON Inventory.ingredient_id = Ingredient.ingredient_id

        WHERE Ingredient.ingredient_name = ?
        """, (ingredient_name,))

        result = cursor.fetchone()

        # 재고 없음
        if result[0] is None:
            missing_ingredients.append({
                "name": ingredient_name,
                "amount": amount
            })

    # 결과 출력
    if missing_ingredients:
        print("\n부족한 식재료")

        for item in missing_ingredients:
            print(
                f"- {item['name']} "
                f"({item['amount']})"
            )
    else:
        print("\n모든 식재료 보유 중")

conn.close()
print("\n조회 완료")
