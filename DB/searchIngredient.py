import sqlite3

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# 검색할 식재료명(임시)
search_name = "양파"

# 특정 Ingredient 조회
cursor.execute("""
SELECT
    Ingredient.ingredient_name,
    Ingredient.category,
    Inventory.quantity,
    Inventory.purchase_date,
    Inventory.expiration_date

FROM Inventory

JOIN Ingredient
ON Inventory.ingredient_id = Ingredient.ingredient_id

WHERE Ingredient.ingredient_name = ?
""", (search_name,))

# 결과 가져오기
rows = cursor.fetchall()
print(f"\n===== {search_name} 조회 결과 =====")

# 결과 출력
if rows:
    for row in rows:

        name = row[0]
        category = row[1]
        quantity = row[2]
        purchase_date = row[3]
        expiration_date = row[4]

        print(f"""
식재료명: {name}
카테고리: {category}
수량: {quantity}
구매일: {purchase_date}
유통기한: {expiration_date}
""")
else:
    print("해당 식재료가 없습니다.")

conn.close()