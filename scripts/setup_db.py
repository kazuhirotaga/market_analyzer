"""データベース初期化スクリプト"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import init_db


def main():
    print("🗄️ データベースを初期化中...")
    engine = init_db()
    print(f"✅ データベース初期化完了: {engine.url}")


if __name__ == "__main__":
    main()
