"""
Các hàm tiện ích kết nối và thao tác với PostgreSQL.
Dùng psycopg2 thuần (không ORM) để dễ hiểu và dễ debug cho pet project.
"""
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

from src.config import DB_CONFIG


@contextmanager
def get_connection():
    """Context manager mở/đóng kết nối DB an toàn."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_category(conn, name: str, url: str = None) -> int:
    """Thêm danh mục mới hoặc lấy category_id nếu đã tồn tại."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO categories (name, url)
            VALUES (%s, %s)
            ON CONFLICT (name)
            DO UPDATE SET url = COALESCE(EXCLUDED.url, categories.url)
            RETURNING category_id;
            """,
            (name, url),
        )
        return cur.fetchone()[0]


def upsert_product(conn, source: str, external_id: str, name: str,
                    category_id: int = None, url: str = None) -> int:
    """Thêm sản phẩm mới hoặc lấy product_id nếu đã tồn tại."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO products (source, external_id, name, category_id, url)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (source, external_id)
            DO UPDATE SET name = EXCLUDED.name, category_id = COALESCE(EXCLUDED.category_id, products.category_id)
            RETURNING product_id;
            """,
            (source, external_id, name, category_id, url),
        )
        return cur.fetchone()[0]


def insert_review(conn, product_id: int, external_review_id: str, rating: int,
                   raw_text: str, review_title: str = None,
                   review_date=None, author_name: str = None):
    """Thêm 1 review, bỏ qua nếu đã tồn tại (dựa trên unique constraint)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO reviews
                (product_id, external_review_id, rating, raw_text,
                 review_title, review_date, author_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (product_id, external_review_id) DO NOTHING;
            """,
            (product_id, external_review_id, rating, raw_text,
             review_title, review_date, author_name),
        )


def fetch_unprocessed_reviews(conn):
    """Lấy các review chưa có bản ghi trong reviews_processed."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT r.review_id, r.raw_text, r.rating
            FROM reviews r
            LEFT JOIN reviews_processed rp ON r.review_id = rp.review_id
            WHERE rp.review_id IS NULL;
            """
        )
        return cur.fetchall()


def insert_processed_review(conn, review_id: int, clean_text: str,
                             tokens: str, token_count: int, weak_label: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO reviews_processed
                (review_id, clean_text, tokens, token_count, weak_label)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (review_id) DO UPDATE
            SET clean_text = EXCLUDED.clean_text,
                tokens = EXCLUDED.tokens,
                token_count = EXCLUDED.token_count,
                weak_label = EXCLUDED.weak_label,
                processed_at = NOW();
            """,
            (review_id, clean_text, tokens, token_count, weak_label),
        )


def fetch_labeled_dataset(conn):
    """Lấy toàn bộ dữ liệu đã tiền xử lý kèm nhãn để train model."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT rp.review_id, rp.tokens, rp.weak_label
            FROM reviews_processed rp
            WHERE rp.weak_label IS NOT NULL AND rp.tokens IS NOT NULL;
            """
        )
        return cur.fetchall()


def fetch_all_processed_for_prediction(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT review_id, tokens FROM reviews_processed
            WHERE tokens IS NOT NULL;
            """
        )
        return cur.fetchall()


def insert_prediction(conn, review_id: int, predicted_label: str,
                       confidence: float, model_version: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sentiment_predictions
                (review_id, predicted_label, confidence, model_version)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (review_id) DO UPDATE
            SET predicted_label = EXCLUDED.predicted_label,
                confidence = EXCLUDED.confidence,
                model_version = EXCLUDED.model_version,
                predicted_at = NOW();
            """,
            (review_id, predicted_label, confidence, model_version),
        )


def insert_model_run(conn, model_version: str, algorithm: str, train_size: int,
                      test_size: int, accuracy: float, macro_f1: float,
                      notes: str = None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO model_runs
                (model_version, algorithm, train_size, test_size, accuracy, macro_f1, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (model_version) DO UPDATE
            SET accuracy = EXCLUDED.accuracy, macro_f1 = EXCLUDED.macro_f1;
            """,
            (model_version, algorithm, train_size, test_size, accuracy, macro_f1, notes),
        )
