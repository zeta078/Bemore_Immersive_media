# 라즈베리파이에서 'crontab -e'로 매일 자정 자동 실행 등록해야함


import sqlite3
import json

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# 7일 지난 DailyNutrition 삭제
cursor.execute("""
DELETE FROM DailyNutrition
WHERE date < DATE('now', '-7 day')
""")
print("오래된 DailyNutrition 삭제 완료")

# quantity 0 이하 Ingredient 조회
cursor.execute("""
SELECT
    inventory_id,
    ingredient_id
FROM Inventory

WHERE quantity <= 0
""")
zero_inventories = cursor.fetchall()

# Inventory 삭제
for item in zero_inventories:
    inventory_id = item[0]
    ingredient_id = item[1]

    cursor.execute("""
    DELETE FROM Inventory

    WHERE inventory_id = ?
    """, (inventory_id,))

    print(f"""
inventory_id {inventory_id}
삭제 완료
""")
    
    # 남은 Inventory 확인
    cursor.execute("""
    SELECT COUNT(*)

    FROM Inventory

    WHERE ingredient_id = ?
    """, (ingredient_id,))

    count = cursor.fetchone()[0]

    # 남은 재고 없으면 Ingredient 삭제
    if count == 0:
        cursor.execute("""
        DELETE FROM Ingredient

        WHERE ingredient_id = ?
        """, (ingredient_id,))

        print(f"""
ingredient_id {ingredient_id}
Ingredient 삭제 완료
""")

# 유통기한 지난 재고 조회
cursor.execute("""
SELECT
    Inventory.inventory_id,
    Ingredient.ingredient_name,
    Inventory.quantity,
    Inventory.expiration_date

FROM Inventory

JOIN Ingredient
ON Inventory.ingredient_id = Ingredient.ingredient_id

WHERE DATE(expiration_date)
< DATE('now')
""")

expired_rows = cursor.fetchall()
expired_list = []

for row in expired_rows:
    inventory_id = row[0]
    ingredient_name = row[1]
    quantity = row[2]
    expiration_date = row[3]

    expired_list.append({
        "inventory_id": inventory_id,
        "ingredient_name": ingredient_name,
        "quantity": quantity,
        "expiration_date": expiration_date
    })

# JSON 저장
with open(
    "expired_ingredients.json",
    "w",
    encoding="utf-8"
) as file:
    json.dump(
        expired_list,
        file,
        ensure_ascii=False,
        indent=4
    ) 
print("유통기한 지난 식재료 JSON 저장 완료")

conn.commit()
conn.close()

print("DB 정리 완료")
