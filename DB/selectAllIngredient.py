import sqlite3

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# Ingredient 전체 조회
cursor.execute("""
SELECT
    ingredient_id,
    ingredient_name,
    category

FROM Ingredient
""")

ingredients = cursor.fetchall()

print("\n===== 전체 식재료 조회 =====")

# Ingredient 반복
for ingredient in ingredients:
    ingredient_id = ingredient[0]
    ingredient_name = ingredient[1]
    category = ingredient[2]

    # 해당 식재료 Inventory 조회
    cursor.execute("""
    SELECT
        quantity,
        purchase_date,
        expiration_date

    FROM Inventory

    WHERE ingredient_id = ?
    """, (ingredient_id,))

    inventory_rows = cursor.fetchall()

    # 총 수량 계산
    total_quantity = 0
    for row in inventory_rows:
        total_quantity += row[0]

    # 식재료 기본 정보 출력
    print(f"""
식재료명 : {ingredient_name}
카테고리 : {category}
총 수량 : {total_quantity}
""")

    # Inventory 상세 출력
    for row in inventory_rows:
        quantity = row[0]
        purchase_date = row[1]
        expiration_date = row[2]

        print(
            f"- {quantity}개 "
            f"({purchase_date} / {expiration_date})"
        )
    print()

conn.close()