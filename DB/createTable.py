import sqlite3

conn = sqlite3.connect("capstonedb.db")
cursor = conn.cursor()

# 사용자 테이블
cursor.execute("""
CREATE TABLE IF NOT EXISTS User (
    name TEXT PRIMARY KEY,
    allergy TEXT,
    preferred_food TEXT,
    disliked_food TEXT,
    diet_habit TEXT,
    health_status TEXT
)
""")

# 식재료 테이블
cursor.execute("""
CREATE TABLE IF NOT EXISTS Ingredient (
    ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_name TEXT NOT NULL UNIQUE,
    category TEXT
)
""")

# 실제 재고 테이블
cursor.execute("""
CREATE TABLE IF NOT EXISTS Inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL,
    quantity REAL DEFAULT 0,
    unit TEXT DEFAULT '개',
    purchase_date DATE,
    expiration_date DATE,

    FOREIGN KEY (ingredient_id)
    REFERENCES Ingredient(ingredient_id)
)
""")

# 레시피 테이블
cursor.execute("""
CREATE TABLE IF NOT EXISTS Recipe (
    recipe_id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_name TEXT NOT NULL,
    content TEXT,
    calories REAL,
    protein REAL,
    sugar REAL,
    sodium REAL,
    fiber REAL,
    saturated_fat REAL,
    recommended_date DATE
)
""")

# 레시피-식재료 관계 테이블 (레시피에 쓰이는 식재료의 종류와 수량을 확인할 때 사용)
cursor.execute("""
CREATE TABLE IF NOT EXISTS RecipeIngredient (
    recipe_id INTEGER,
    ingredient_id INTEGER,
    amount TEXT,

    PRIMARY KEY (recipe_id, ingredient_id),

    FOREIGN KEY(recipe_id) REFERENCES Recipe(recipe_id),
    FOREIGN KEY(ingredient_id) REFERENCES Ingredient(ingredient_id)
)
""")

# 하루 영양 섭취 테이블
cursor.execute("""
CREATE TABLE IF NOT EXISTS DailyNutrition (
    date DATE PRIMARY KEY,
    total_calories REAL,
    total_protein REAL,
    total_sugar REAL,
    total_sodium REAL,
    total_fiber REAL,
    total_saturated_fat REAL
)
""")

# 섭취한 레시피 기록 테이블
cursor.execute("""
CREATE TABLE IF NOT EXISTS ConsumedRecipe (
    consumed_id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER,
    consumed_date DATE,

    FOREIGN KEY(recipe_id) REFERENCES Recipe(recipe_id)
)
""")

conn.commit()
conn.close()

print("모든 테이블 생성 완료")