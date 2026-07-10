"""
Script khởi tạo schema database mà KHÔNG cần dùng lệnh `psql`.
Hữu ích khi máy chưa cài PostgreSQL command line tools (thường gặp trên Windows).

Chạy: python -m src.db.init_schema
"""
import logging
from pathlib import Path

from src.config import DB_CONFIG

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "sql" / "schema.sql"


def run():
    import psycopg2  # import trễ để tránh lỗi nếu chưa cài đủ package khi chỉ xem code

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy file schema tại: {SCHEMA_PATH}")

    sql_content = SCHEMA_PATH.read_text(encoding="utf-8")

    logger.info("Đang kết nối tới database %s@%s ...", DB_CONFIG["dbname"], DB_CONFIG["host"])
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql_content)
        conn.commit()
        logger.info("Đã khởi tạo schema thành công.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run()
