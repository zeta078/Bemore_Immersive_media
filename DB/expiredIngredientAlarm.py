import sqlite3
import json
import os

# JSON 파일 존재 확인
if not os.path.exists("expired_ingredients.json"):
    print("유통기한 알림 파일이 없습니다.")
else:
    # JSON 읽기
    with open(
        "expired_ingredients.json",
        "r",
        encoding="utf-8"
    ) as file:
        expired_list = json.load(file)

    # 유통기한 지난 식재료 없음
    if not expired_list:
        print("유통기한 지난 식재료가 없습니다.")

    # 유통기한 지난 식재료 존재
    else:
        print("\n===== 유통기한 지난 식재료 =====")

        for item in expired_list:
            print(f"""
식재료명 : {item["ingredient_name"]}

수량 : {item["quantity"]}

유통기한 : {item["expiration_date"]}
""")

        # 삭제 여부 입력
        answer = input(
            "\n유통기한 지난 식재료를 삭제하시겠습니까? (y/n) : "
        )

        # 삭제 진행
        if answer.lower() == "y":
            # DB 연결
            conn = sqlite3.connect("capstonedb.db")
            cursor = conn.cursor()

            for item in expired_list:
                inventory_id = item["inventory_id"]

                # ingredient_id 조회
                cursor.execute("""
                SELECT ingredient_id

                FROM Inventory

                WHERE inventory_id = ?
                """, (inventory_id,))

                result = cursor.fetchone()

                # 이미 삭제된 경우
                if result is None:
                    continue
                ingredient_id = result[0]

                # Inventory 삭제
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
                    
            conn.commit()
            conn.close()
            
            # JSON 초기화
            with open(
                "expired_ingredients.json",
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(
                    [],
                    file,
                    ensure_ascii=False,
                    indent=4
                )

            print("\n유통기한 지난 재고 삭제 완료")
        else:
            print("\n삭제 취소")