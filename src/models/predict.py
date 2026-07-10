"""
Dùng model đã train (latest_model.joblib) để dự đoán sentiment cho toàn bộ
review đã tiền xử lý, ghi kết quả vào bảng sentiment_predictions.

Chạy: python -m src.models.predict
"""
import logging

import joblib
import numpy as np
from tqdm import tqdm

from src.config import MODEL_DIR
from src.db.db_utils import (
    get_connection,
    fetch_all_processed_for_prediction,
    insert_prediction,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_latest_model():
    model_path = MODEL_DIR / "latest_model.joblib"
    vectorizer_path = MODEL_DIR / "latest_vectorizer.joblib"

    if not model_path.exists() or not vectorizer_path.exists():
        raise FileNotFoundError(
            "Chưa tìm thấy model đã train. Hãy chạy: python -m src.models.train_sentiment"
        )

    model = joblib.load(model_path)
    vectorizer = joblib.load(vectorizer_path)
    return model, vectorizer


def run(batch_size: int = 500):
    model, vectorizer = load_latest_model()
    model_version = "latest_model"  # có thể đổi thành tên version cụ thể nếu muốn theo dõi

    with get_connection() as conn:
        rows = fetch_all_processed_for_prediction(conn)
        logger.info("Số review cần dự đoán: %d", len(rows))

        for i in tqdm(range(0, len(rows), batch_size), desc="Dự đoán sentiment"):
            batch = rows[i:i + batch_size]
            tokens_list = [r["tokens"] or "" for r in batch]

            X_vec = vectorizer.transform(tokens_list)
            preds = model.predict(X_vec)
            probs = model.predict_proba(X_vec)
            confidences = np.max(probs, axis=1)

            for row, pred_label, conf in zip(batch, preds, confidences):
                insert_prediction(
                    conn,
                    review_id=row["review_id"],
                    predicted_label=pred_label,
                    confidence=float(conf),
                    model_version=model_version,
                )

            conn.commit()

    logger.info("Hoàn tất dự đoán cho %d review.", len(rows))


if __name__ == "__main__":
    run()
