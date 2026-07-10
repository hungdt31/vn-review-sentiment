"""
Huấn luyện model baseline phân loại sentiment: TF-IDF + Logistic Regression.

Chạy: python -m src.models.train_sentiment
"""
import logging
from datetime import datetime

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score, accuracy_score

from src.config import MODEL_DIR, LABELS
from src.db.db_utils import get_connection, fetch_labeled_dataset, insert_model_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_dataset() -> pd.DataFrame:
    with get_connection() as conn:
        rows = fetch_labeled_dataset(conn)
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError(
            "Không có dữ liệu đã gán nhãn. Hãy chạy crawler + run_preprocessing trước."
        )
    return df


def train(min_samples_per_class: int = 20, test_size: float = 0.2, random_state: int = 42):
    df = load_dataset()
    logger.info("Tổng số mẫu: %d", len(df))
    logger.info("Phân bố nhãn:\n%s", df["weak_label"].value_counts())

    # Cảnh báo nếu 1 lớp quá ít mẫu (thường gặp với 'neutral')
    counts = df["weak_label"].value_counts()
    for label in LABELS:
        n = counts.get(label, 0)
        if n < min_samples_per_class:
            logger.warning(
                "Lớp '%s' chỉ có %d mẫu (< %d) — model có thể học kém với lớp này. "
                "Cân nhắc crawl thêm dữ liệu hoặc dùng class_weight='balanced'.",
                label, n, min_samples_per_class,
            )

    X_train, X_test, y_train, y_test = train_test_split(
        df["tokens"], df["weak_label"],
        test_size=test_size, random_state=random_state, stratify=df["weak_label"],
    )

    vectorizer = TfidfVectorizer(max_features=8000, ngram_range=(1, 2), min_df=2)
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train_vec, y_train)

    y_pred = model.predict(X_test_vec)
    report = classification_report(y_test, y_pred, labels=LABELS, zero_division=0)
    acc = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)

    logger.info("Kết quả đánh giá trên tập test:\n%s", report)
    logger.info("Accuracy: %.4f | Macro-F1: %.4f", acc, macro_f1)

    model_version = f"tfidf_logreg_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    model_path = MODEL_DIR / f"{model_version}.joblib"
    vectorizer_path = MODEL_DIR / f"{model_version}_vectorizer.joblib"

    joblib.dump(model, model_path)
    joblib.dump(vectorizer, vectorizer_path)

    # Cũng lưu bản "latest" cố định tên để predict.py dùng mặc định
    joblib.dump(model, MODEL_DIR / "latest_model.joblib")
    joblib.dump(vectorizer, MODEL_DIR / "latest_vectorizer.joblib")

    with get_connection() as conn:
        insert_model_run(
            conn, model_version=model_version, algorithm="TF-IDF + LogisticRegression",
            train_size=len(X_train), test_size=len(X_test),
            accuracy=float(acc), macro_f1=float(macro_f1),
            notes="Baseline model, class_weight=balanced, ngram(1,2)",
        )

    logger.info("Đã lưu model tại: %s", model_path)
    return model_version, acc, macro_f1


if __name__ == "__main__":
    train()
