import sqlite3
import re

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# 섭취할 레시피명(임시)
recipe_name = "양파 달걀 볶음"

# recipe_id 조회
cursor.execute("""
SELECT recipe_id
FROM Recipe
WHERE recipe_name = ?
""", (recipe_name,))

recipe = cursor.fetchone()

if recipe is None:
    print("레시피가 없습니다.")
else:
    recipe_id = recipe[0]
    print(f"\n===== {recipe_name} 섭취 =====")

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

    # 식재료별 차감
    for item in recipe_ingredients:
        ingredient_name = item[0]
        amount_text = item[1]

        # 숫자만 추출
        amount = int(re.findall(r'\d+', amount_text)[0])
        print(f"\n{ingredient_name} {amount}개 차감")

        # Ingredient 조회
        # 유통기한 빠른 순
        cursor.execute("""
        SELECT

            Inventory.inventory_id,
            Inventory.quantity

        FROM Inventory

        JOIN Ingredient
        ON Inventory.ingredient_id = Ingredient.ingredient_id

        WHERE Ingredient.ingredient_name = ?

        ORDER BY Inventory.expiration_date ASC
        """, (ingredient_name,))
        inventories = cursor.fetchall()
        remaining = amount

        # FIFO 차감
        for inventory in inventories:
            inventory_id = inventory[0]
            quantity = inventory[1]

            # 이미 다 차감 완료
            if remaining <= 0:
                break

            # 현재 재고가 더 많음
            if quantity >= remaining:
                new_quantity = quantity - remaining

                cursor.execute("""
                UPDATE Inventory

                SET quantity = ?

                WHERE inventory_id = ?
                """, (
                    new_quantity,
                    inventory_id
                ))
                print(
                    f"inventory_id {inventory_id} "
                    f"{remaining}개 차감"
                )
                remaining = 0

            # 현재 재고가 부족함
            else:
                cursor.execute("""
                UPDATE Inventory

                SET quantity = 0

                WHERE inventory_id = ?
                """, (inventory_id,))

                print(
                    f"inventory_id {inventory_id} "
                    f"{quantity}개 전부 사용"
                )
                remaining -= quantity

        # 재고 부족
        if remaining > 0:
            print(
                f"{ingredient_name} "
                f"{remaining}개 부족"
            )

    conn.commit()

conn.close()

print("\n섭취 식재료 삭제 완료")
