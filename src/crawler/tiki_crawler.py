"""
Crawler thu thập review sản phẩm từ Tiki, dùng API JSON công khai của Tiki
(không cần đăng nhập). Lưu trực tiếp vào PostgreSQL qua db_utils.

Cách hoạt động:
1. Lấy danh sách sản phẩm từ 1 category (qua API search) hoặc từ danh sách
   product_id được truyền vào trực tiếp.
2. Với mỗi sản phẩm, gọi API review theo từng trang (paginate) cho tới khi hết.
3. Insert product + reviews vào DB.

Lưu ý đạo đức khi crawl:
- Có delay giữa các request (CRAWL_DELAY_SECONDS) để tránh spam server.
- Chỉ lấy dữ liệu công khai, không bypass đăng nhập/captcha.
- Nên giới hạn max_products / max_pages khi test để không tải quá nhiều.
"""
import argparse
import re
import time
import logging
from datetime import datetime, date

import requests
from dateutil import parser as date_parser

from src.config import CRAWL_DELAY_SECONDS
from src.db.db_utils import get_connection, upsert_category, upsert_product, insert_review

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

SEARCH_API = "https://tiki.vn/api/personalish/v1/blocks/listings"
REVIEW_API = "https://tiki.vn/api/v2/reviews"


def extract_category_label(category_url: str) -> str:
    """
    Suy ra tên category dễ đọc từ URL, vd:
    'https://tiki.vn/dien-thoai-smartphone/c1795' -> 'Dien thoai smartphone'
    Dùng để lưu vào cột products.category, giúp lọc/gộp trên dashboard
    thay vì để trống hoặc lưu nguyên URL dài.
    """
    try:
        parts = category_url.rstrip("/").split("/")
        slug = parts[-1]
        if re.match(r"^c\d+$", slug) and len(parts) > 1:
            slug = parts[-2]
        slug = re.sub(r"-c\d+$", "", slug)  # bỏ hậu tố '-c1795'
        label = slug.replace("-", " ").strip()
        return label.capitalize() if label else category_url
    except Exception:
        return category_url


def search_products(category_url: str, max_products: int = 50):
    """
    Lấy danh sách product_id từ 1 trang category Tiki.
    category_url dạng: https://tiki.vn/dien-thoai-smartphone/c1795
    Hàm parse category id từ URL rồi gọi API listings.
    """
    try:
        category_id = category_url.rstrip("/").split("c")[-1]
        category_id = "".join(ch for ch in category_id if ch.isdigit())
    except Exception:
        logger.error("Không parse được category_id từ URL: %s", category_url)
        return []

    products = []
    page = 1
    while len(products) < max_products:
        params = {
            "limit": 40,
            "category": category_id,
            "page": page,
        }
        resp = requests.get(SEARCH_API, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning("Search API trả về status %s ở page %s", resp.status_code, page)
            break
        data = resp.json().get("data", [])
        if not data:
            break
        for item in data:
            products.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "url_key": item.get("url_key"),
            })
        page += 1
        time.sleep(CRAWL_DELAY_SECONDS)

    return products[:max_products]


def crawl_reviews_for_product(product_id: int, max_pages: int = 10):
    """Lấy toàn bộ review (tối đa max_pages trang) cho 1 product_id."""
    all_reviews = []
    page = 1
    while page <= max_pages:
        params = {
            "product_id": product_id,
            "page": page,
            "limit": 20,
        }
        resp = requests.get(REVIEW_API, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(
                "Review API trả về status %s cho product_id=%s trang %s",
                resp.status_code, product_id, page,
            )
            break
        payload = resp.json()
        reviews = payload.get("data", [])
        if not reviews:
            break
        all_reviews.extend(reviews)

        paging = payload.get("paging", {})
        total_pages = paging.get("last_page", page)
        if page >= total_pages:
            break
        page += 1
        time.sleep(CRAWL_DELAY_SECONDS)

    return all_reviews


def parse_review_date(raw_date_value):
    """
    Parse ngày review từ nhiều định dạng khác nhau mà Tiki có thể trả về:
    - ISO string: '2023-08-01T10:23:11Z' hoặc '2023-08-01 10:23:11'
    - Unix timestamp (int/str số): 1690876800
    Trả về None nếu không parse được (dùng dateutil để bao quát nhiều format
    thay vì chỉ fromisoformat, tránh trường hợp review_date bị NULL hàng loạt
    khiến biểu đồ xu hướng theo thời gian bị trống).
    """
    if not raw_date_value:
        return None

    # Trường hợp timestamp dạng số (int hoặc string toàn số)
    if isinstance(raw_date_value, (int, float)):
        try:
            return datetime.fromtimestamp(raw_date_value).date()
        except Exception:
            return None

    raw_str = str(raw_date_value).strip()
    if raw_str.isdigit():
        try:
            return datetime.fromtimestamp(int(raw_str)).date()
        except Exception:
            return None

    # Trường hợp chuỗi ngày dạng text, dùng dateutil để bao quát nhiều format
    try:
        return date_parser.parse(raw_str, fuzzy=True).date()
    except Exception:
        return None


def run(category_urls: list = None, product_ids: list = None,
        max_products_per_category: int = 50, max_pages_per_product: int = 10):
    """
    category_urls: danh sách nhiều URL category, vd:
        ["https://tiki.vn/dien-thoai-smartphone/c1795",
         "https://tiki.vn/laptop/c8095"]
        -> crawl lần lượt từng category, mỗi category tối đa
           max_products_per_category sản phẩm.
    """
    products_meta = []

    if product_ids:
        products_meta = [
            {"id": pid, "name": None, "url_key": None, "category_url": None}
            for pid in product_ids
        ]
    elif category_urls:
        for cat_url in category_urls:
            logger.info("Đang tìm sản phẩm trong category: %s", cat_url)
            found = search_products(cat_url, max_products=max_products_per_category)
            for item in found:
                item["category_url"] = cat_url
            products_meta.extend(found)
            logger.info("  -> Tìm thấy %d sản phẩm trong category này.", len(found))
    else:
        raise ValueError("Cần truyền category_urls hoặc product_ids")

    logger.info("Tổng số sản phẩm sẽ crawl review: %d", len(products_meta))

    total_reviews_saved = 0
    with get_connection() as conn:
        for meta in products_meta:
            pid = meta["id"]
            if pid is None:
                continue
            name = meta.get("name") or f"tiki_product_{pid}"
            cat_url = meta.get("category_url")
            category_label = extract_category_label(cat_url) if cat_url else None
            url = f"https://tiki.vn/{meta['url_key']}-p{pid}.html" if meta.get("url_key") else None

            category_id = None
            if cat_url and category_label:
                category_id = upsert_category(conn, name=category_label, url=cat_url)

            product_db_id = upsert_product(
                conn, source="tiki", external_id=str(pid),
                name=name, category_id=category_id, url=url,
            )

            reviews = crawl_reviews_for_product(pid, max_pages=max_pages_per_product)
            logger.info("Product %s (%s) [%s]: lấy được %d review",
                        pid, name, category_label, len(reviews))

            for rv in reviews:
                content = (rv.get("content") or "").strip()
                if not content:
                    continue  # bỏ qua review rỗng (chỉ có sao, không có text)
                insert_review(
                    conn,
                    product_id=product_db_id,
                    external_review_id=str(rv.get("id")),
                    rating=rv.get("rating"),
                    raw_text=content,
                    review_title=rv.get("title"),
                    review_date=parse_review_date(rv.get("created_at")),
                    author_name=(rv.get("created_by") or {}).get("name"),
                )
                total_reviews_saved += 1

            conn.commit()

    logger.info("Hoàn tất crawl. Tổng số review đã lưu: %d", total_reviews_saved)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl review sản phẩm từ Tiki")
    parser.add_argument(
        "--category-urls", type=str, default=None,
        help=(
            "Danh sách URL category Tiki, phân cách bởi dấu phẩy. Vd: "
            '"https://tiki.vn/dien-thoai-smartphone/c1795,https://tiki.vn/laptop/c8095"'
        ),
    )
    parser.add_argument("--product-ids", type=str, default=None,
                         help="Danh sách product_id, phân cách bởi dấu phẩy (thay cho --category-urls)")
    parser.add_argument("--max-products-per-category", type=int, default=50,
                         help="Số sản phẩm tối đa lấy cho MỖI category")
    parser.add_argument("--max-pages", type=int, default=10,
                         help="Số trang review tối đa lấy cho mỗi sản phẩm")
    args = parser.parse_args()

    pids = None
    if args.product_ids:
        pids = [int(x.strip()) for x in args.product_ids.split(",") if x.strip()]

    cat_urls = None
    if args.category_urls:
        cat_urls = [u.strip() for u in args.category_urls.split(",") if u.strip()]

    run(
        category_urls=cat_urls,
        product_ids=pids,
        max_products_per_category=args.max_products_per_category,
        max_pages_per_product=args.max_pages,
    )
