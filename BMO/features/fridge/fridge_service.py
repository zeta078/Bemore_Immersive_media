import sys
import os

# db_bridge 경로: BMO/ 디렉토리
_BMO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
if _BMO_ROOT not in sys.path:
    sys.path.insert(0, _BMO_ROOT)


class FridgeService:
    """
    냉장고 화면용 데이터 서비스.
    db_bridge를 통해 Inventory + Ingredient 테이블에서 실제 재고를 조회한다.
    """

    def __init__(self, backend_client=None):
        self.backend_client = backend_client

    def get_ingredient_items(self):
        items = self._get_db_items()
        return self.prepare_ingredient_rows(items)

    def prepare_ingredient_rows(self, items):
        if not items:
            return self.get_empty_state_rows()

        return [self._normalize_item(item) for item in items]

    def get_empty_state_rows(self):
        return [
            {
                "name": "등록된 재료 없음",
                "quantity": "-",
                "source": "재료를 먼저 등록해 주세요",
            }
        ]

    def _normalize_item(self, item):
        if isinstance(item, dict):
            return {
                "name": str(item.get("name", "")),
                "quantity": str(item.get("quantity", "")),
                "source": str(item.get("source", "")),
            }
        name, quantity, source = item
        return {
            "name": str(name),
            "quantity": str(quantity),
            "source": str(source),
        }

    def _get_db_items(self):
        """
        Inventory JOIN Ingredient 에서 수량 > 0 인 재료를 가져온다.
        db_bridge import 실패 시 빈 리스트를 반환해 화면이 깨지지 않게 한다.
        """
        try:
            import sqlite3

            db_path = os.path.normpath(
                os.path.join(_BMO_ROOT, "..", "DB", "capstonedb.db")
            )
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    i.ingredient_name  AS name,
                    SUM(inv.quantity)  AS quantity,
                    inv.unit           AS unit,
                    i.category         AS source
                FROM Inventory inv
                JOIN Ingredient i ON inv.ingredient_id = i.ingredient_id
                GROUP BY inv.ingredient_id
                HAVING SUM(inv.quantity) > 0
                ORDER BY i.ingredient_name
            """)
            rows = cursor.fetchall()
            conn.close()

            result = []
            for row in rows:
                qty = row["quantity"]
                unit = row["unit"] or "개"
                qty_str = str(int(qty)) if qty == int(qty) else str(qty)
                result.append({
                    "name": row["name"],
                    "quantity": f"{qty_str}{unit}",
                    "source": row["source"] or "직접 등록",
                })
            return result

        except Exception as e:
            print(f"[FRIDGE SERVICE] DB 조회 실패: {e}")
            return []


def get_ingredient_items():
    return FridgeService().get_ingredient_items()