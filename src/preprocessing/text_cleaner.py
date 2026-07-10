"""
Tiền xử lý văn bản tiếng Việt: chuẩn hoá, loại nhiễu, tokenize bằng underthesea.
"""
import re
from underthesea import word_tokenize, text_normalize

# Danh sách stopword tiếng Việt rút gọn, đủ dùng cho baseline.
# Có thể mở rộng thêm tuỳ theo dữ liệu thực tế.
VIETNAMESE_STOPWORDS = {
    "và", "là", "của", "có", "cho", "được", "này", "đó", "các", "một",
    "những", "để", "khi", "với", "về", "thì", "đã", "sẽ", "ở", "nhưng",
    "cũng", "rất", "nên", "vì", "nếu", "mà", "lại", "nữa", "còn", "trong",
    "ra", "vào", "lên", "xuống", "tôi", "bạn", "mình", "họ", "nó", "ạ",
    "nha", "nhé", "à", "ừ", "ơi",
}

URL_PATTERN = re.compile(r"http\S+|www\.\S+")
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)
# Giữ chữ cái (bao gồm ký tự tiếng Việt có dấu), số và khoảng trắng
NON_WORD_PATTERN = re.compile(r"[^\w\sÀ-ỹà-ỹÀ-Ỹ]")
MULTI_SPACE_PATTERN = re.compile(r"\s+")


def clean_text(raw_text: str) -> str:
    """Chuẩn hoá văn bản thô: bỏ URL, emoji, ký tự đặc biệt, khoảng trắng thừa."""
    if not raw_text:
        return ""

    text = text_normalize(raw_text)          # chuẩn hoá unicode tiếng Việt (underthesea)
    text = URL_PATTERN.sub(" ", text)
    text = EMOJI_PATTERN.sub(" ", text)
    text = NON_WORD_PATTERN.sub(" ", text)
    text = MULTI_SPACE_PATTERN.sub(" ", text)
    return text.strip().lower()


def tokenize(clean: str, remove_stopwords: bool = True) -> str:
    """
    Tách từ tiếng Việt bằng underthesea (word_tokenize).
    Trả về chuỗi token phân cách bằng khoảng trắng (dễ lưu DB / đưa vào TF-IDF).
    """
    if not clean:
        return ""

    tokens = word_tokenize(clean, format="text").split()
    if remove_stopwords:
        tokens = [t for t in tokens if t not in VIETNAMESE_STOPWORDS]

    return " ".join(tokens)


def preprocess(raw_text: str, remove_stopwords: bool = True):
    """Pipeline đầy đủ: raw_text -> (clean_text, tokens, token_count)."""
    clean = clean_text(raw_text)
    tokens_str = tokenize(clean, remove_stopwords=remove_stopwords)
    token_count = len(tokens_str.split()) if tokens_str else 0
    return clean, tokens_str, token_count
