import os
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_USERNAME = os.getenv("DB_USERNAME")

db_uri = f"mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@shortline.proxy.rlwy.net:46708/railway"
 
db = SQLDatabase.from_uri(db_uri)

engine = create_engine(db_uri,
        connect_args = {
        "init_command": "SET time_zone = '+05:30'"
    })

create_orders_table = """
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(255) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    user_id INT NOT NULL,
    is_complaint TINYINT(1) DEFAULT 0,
    complaint_text TEXT,
    complaint_file_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

try:
    with engine.connect() as conn:
        conn.execute(text(create_orders_table))
        conn.commit()
        result = conn.execute(text("SELECT NOW();")).fetchone()
        print(f"Orders table is ready. Current DB Time (IST): {result[0]}")

    print("Orders table is ready.")
except Exception as e:
    print("Error creating orders table:", e)