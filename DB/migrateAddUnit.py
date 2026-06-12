"""
기존 capstonedb.db에 unit 컬럼과 REAL quantity를 추가하는 마이그레이션 스크립트.
DB를 새로 만들었으면 실행 불필요. 기존 DB가 있다면 한 번만 실행하면 된다.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capstonedb.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 현재 컬럼 목록 확인
cursor.execute("PRAGMA table_info(Inventory)")
cols = [row[1] for row in cursor.fetchall()]

if "unit" not in cols:
    cursor.execute("ALTER TABLE Inventory ADD COLUMN unit TEXT DEFAULT '개'")
    print("[MIGRATE] Inventory.unit 컬럼 추가 완료")
else:
    print("[MIGRATE] Inventory.unit 이미 존재 - 건너뜀")

# quantity가 INTEGER인 경우 SQLite는 ALTER COLUMN을 지원하지 않으므로
# 기존 정수 데이터는 REAL로 자동 호환됨 (SQLite 타입 시스템 유연성)
# 별도 작업 불필요.

conn.commit()
conn.close()
print("[MIGRATE] 완료")