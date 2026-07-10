"""
Script: lấy toàn bộ review chưa được tiền xử lý trong DB, làm sạch + tokenize
+ gán weak label (từ rating), rồi ghi vào bảng reviews_processed.

Chạy: python -m src.preprocessing.run_preprocessing
"""
import logging
from tqdm import tqdm

from src.config import rating_to_label
from src.db.db_utils import get_connection, fetch_unprocessed_reviews, insert_processed_review
from src.preprocessing.text_cleaner import preprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MIN_TOKEN_COUNT = 2  # bỏ qua review quá ngắn (vd chỉ có "ok", "tốt") để tránh nhiễu model


def run():
    with get_connection() as conn:
        rows = fetch_unprocessed_reviews(conn)
        logger.info("Có %d review cần tiền xử lý.", len(rows))

        processed_count = 0
        skipped_count = 0

        for row in tqdm(rows, desc="Tiền xử lý review"):
            clean, tokens_str, token_count = preprocess(row["raw_text"])

            if token_count < MIN_TOKEN_COUNT:
                skipped_count += 1
                # Vẫn insert để đánh dấu đã xử lý (tránh xử lý lại), nhưng weak_label để None
                insert_processed_review(
                    conn, review_id=row["review_id"], clean_text=clean,
                    tokens=tokens_str, token_count=token_count, weak_label=None,
                )
                continue

            weak_label = rating_to_label(row["rating"])
            insert_processed_review(
                conn, review_id=row["review_id"], clean_text=clean,
                tokens=tokens_str, token_count=token_count, weak_label=weak_label,
            )
            processed_count += 1

        conn.commit()

    logger.info(
        "Hoàn tất. Đã xử lý %d review hợp lệ, bỏ qua %d review quá ngắn.",
        processed_count, skipped_count,
    )


if __name__ == "__main__":
    run()
