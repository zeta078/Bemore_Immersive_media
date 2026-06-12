import sqlite3
from datetime import datetime

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# 임시 레시피 데이터
data = {
    "recipe_name": "양파 달걀 볶음",
    "content":
    """
    1. 양파를 썬다.
    2. 달걀을 푼다.
    3. 팬에 볶는다.
    """,
    "nutrition": {
        "calories": 350,
        "protein": 20,
        "sugar": 5,
        "sodium": 400,
        "fiber": 3,
        "saturated_fat": 2
    },
    "ingredients": [
        {
            "name": "양파",
            "amount": "1개"
        },
        {
            "name": "달걀",
            "amount": "2개"
        },
    ]
}

# Recipe 저장
recipe_name = data["recipe_name"]
content = data["content"]
nutrition = data["nutrition"]
recommended_date = datetime.now().strftime("%Y-%m-%d")

cursor.execute("""
INSERT INTO Recipe(
    recipe_name,
    content,
    calories,
    protein,
    sugar,
    sodium,
    fiber,
    saturated_fat,
    recommended_date
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    recipe_name,
    content,
    nutrition["calories"],
    nutrition["protein"],
    nutrition["sugar"],
    nutrition["sodium"],
    nutrition["fiber"],
    nutrition["saturated_fat"],
    recommended_date
))

conn.commit()

# 생성된 recipe_id 가져오기
recipe_id = cursor.lastrowid
print(f"{recipe_name} Recipe 저장 완료")

# RecipeIngredient 저장
for item in data["ingredients"]:
    ingredient_name = item["name"]
    amount = item["amount"]

    cursor.execute("""
    SELECT ingredient_id
    FROM Ingredient
    WHERE ingredient_name = ?
    """, (ingredient_name,))
    ingredient = cursor.fetchone()

    if ingredient is None:
        print(f"{ingredient_name} Ingredient not found")
        continue

    ingredient_id = ingredient[0]

    cursor.execute("""
    INSERT INTO RecipeIngredient(
        recipe_id,
        ingredient_id,
        amount
    )
    VALUES (?, ?, ?)
    """, (
        recipe_id,
        ingredient_id,
        amount
    ))
    print(f"{ingredient_name} RecipeIngredient 저장 완료")

conn.commit()
conn.close()

print("레시피 전체 저장 완료")
