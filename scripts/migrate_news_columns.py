import sys
import os
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.models import get_engine

def migrate():
    print("🔄 Migrating database: Adding columns to news_articles...")
    engine = get_engine()
    
    cols_to_add = [
        ("summary_llm", "TEXT"),
        ("impact_llm", "VARCHAR(50)"),
        ("reasoning_llm", "TEXT"),
        ("affected_sectors_llm", "VARCHAR(200)")
    ]
    
    with engine.connect() as conn:
        for col_name, col_type in cols_to_add:
            try:
                # SQLite syntax
                sql = f"ALTER TABLE news_articles ADD COLUMN {col_name} {col_type}"
                conn.execute(text(sql))
                print(f"✅ Added column: {col_name}")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print(f"ℹ️ Column already exists: {col_name}")
                else:
                    print(f"⚠️ Error adding {col_name}: {e}")
        conn.commit()
    
    print("✨ Migration completed.")

if __name__ == "__main__":
    migrate()
