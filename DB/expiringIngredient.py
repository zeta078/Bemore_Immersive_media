import sqlite3

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# 사용자가 요청한 기간(임시)
#days = data["days"]
days = 5

# 유통기한 임박 조회
query = f"""
SELECT
    Ingredient.ingredient_name,
    Ingredient.category,
    Inventory.quantity,
    Inventory.purchase_date,
    Inventory.expiration_date

FROM Inventory

JOIN Ingredient
ON Inventory.ingredient_id = Ingredient.ingredient_id

WHERE DATE(Inventory.expiration_date)
<= DATE('now', '+{days} day')

AND DATE(Inventory.expiration_date)
>= DATE('now')

ORDER BY Inventory.expiration_date ASC
"""

cursor.execute(query)

# 결과 가져오기
rows = cursor.fetchall()
print(f"\n===== {days}일 이내 유통기한 식재료 =====")

# 출력
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