"""一次性迁移：删除分类体系 (articles.category_id 与 categories 表)。

幂等，可重复执行。执行前先确认前后端代码已不再引用分类。
用法：venv/Scripts/python.exe migrate_drop_categories.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.core.database import engine


def scalar(conn, sql, **params):
    return conn.execute(text(sql), params).scalar()


def main():
    with engine.begin() as conn:
        db = scalar(conn, "SELECT DATABASE()")

        fk = scalar(
            conn,
            """
            SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = :db AND TABLE_NAME = 'articles'
              AND COLUMN_NAME = 'category_id' AND REFERENCED_TABLE_NAME IS NOT NULL
            """,
            db=db,
        )
        if fk:
            conn.execute(text(f"ALTER TABLE articles DROP FOREIGN KEY `{fk}`"))
            print(f"[1/3] 已移除外键约束 {fk}")
        else:
            print("[1/3] 无外键约束，跳过")

        col = scalar(
            conn,
            """
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :db AND TABLE_NAME = 'articles' AND COLUMN_NAME = 'category_id'
            """,
            db=db,
        )
        if col:
            conn.execute(text("ALTER TABLE articles DROP COLUMN category_id"))
            print("[2/3] 已删除列 articles.category_id")
        else:
            print("[2/3] 列 articles.category_id 不存在，跳过")

        tbl = scalar(
            conn,
            "SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA = :db AND TABLE_NAME = 'categories'",
            db=db,
        )
        if tbl:
            conn.execute(text("DROP TABLE categories"))
            print("[3/3] 已删除表 categories")
        else:
            print("[3/3] 表 categories 不存在，跳过")

    print("分类体系清理完成。")


if __name__ == "__main__":
    main()
