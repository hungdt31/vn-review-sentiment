"""
Cấu hình chung của project, đọc từ file .env.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Tự động tìm file .env ở thư mục gốc project
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "vn_review_sentiment"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    # Aiven yêu cầu SSL bắt buộc -> đặt DB_SSLMODE=require trong .env
    "sslmode": os.getenv("DB_SSLMODE", "disable"),
}

# Chỉ thêm sslrootcert vào config nếu người dùng có khai báo
# (cần thiết khi dùng sslmode=verify-ca hoặc verify-full)
_sslrootcert = os.getenv("DB_SSLROOTCERT", "").strip()
if _sslrootcert:
    DB_CONFIG["sslrootcert"] = _sslrootcert

CRAWL_DELAY_SECONDS = float(os.getenv("CRAWL_DELAY_SECONDS", "1.0"))
MODEL_DIR = Path(os.getenv("MODEL_DIR", str(BASE_DIR / "models_artifacts")))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Nhãn chuẩn dùng xuyên suốt project
LABELS = ["negative", "neutral", "positive"]


def rating_to_label(rating: int) -> str:
    """Suy ra 'weak label' cảm xúc từ số sao rating (1-5)."""
    if rating is None:
        return None
    if rating <= 2:
        return "negative"
    if rating == 3:
        return "neutral"
    return "positive"
