import sqlite3

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# 임시로 저장할 데이터
data = {
    "ingredients": [
        {
            "name": "양파",
            "category": "채소",
            "quantity": 2,
            "purchase_date": "2026-05-20",
            "expiration_date": "2026-05-23"
        },
        {
            "name": "달걀",
            "category": "유제품",
            "quantity": 10,
            "purchase_date": "2026-05-20",
            "expiration_date": "2026-06-10"
        }
    ]
}

for item in data["ingredients"]:
        name = item["name"]
        category = item["category"]
        quantity = item["quantity"]
        purchase_date = item["purchase_date"]
        expiration_date = item["expiration_date"]

        # Ingredient 존재 확인
        cursor.execute("""
        SELECT ingredient_id
        FROM Ingredient
        WHERE ingredient_name = ?
        """, (name,))

        result = cursor.fetchone()

        # 없으면 새로 추가
        if result is None:
            cursor.execute("""
            INSERT INTO Ingredient(
                ingredient_name,
                category
            )
            VALUES (?, ?)
            """, (name, category))

            conn.commit()

            ingredient_id = cursor.lastrowid
            print(f"{name} Ingredient 추가")
        else:
            ingredient_id = result[0]
            print(f"{name} 기존 Ingredient 사용")

        # Inventory 저장
        cursor.execute("""
        INSERT INTO Inventory(
            ingredient_id,
            quantity,
            purchase_date,
            expiration_date
        )
        VALUES (?, ?, ?, ?)
        """, (
            ingredient_id,
            quantity,
            purchase_date,
            expiration_date
        ))
        print(f"{name} Inventory 추가")

conn.commit()
conn.close()

print("모든 데이터 저장 완료")