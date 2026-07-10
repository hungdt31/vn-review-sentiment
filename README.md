---
title: VN Review Sentiment
emoji: 📊
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.32.0
app_file: dashboard/app.py
pinned: false
---

# Phân tích & Phân loại Sentiment Review Tiếng Việt

Pet project: Crawl review sản phẩm (Tiki) → lưu PostgreSQL → tiền xử lý tiếng Việt
(underthesea) → huấn luyện model phân loại cảm xúc (tích cực / tiêu cực / trung tính)
→ dashboard thống kê (Streamlit).

## Cấu trúc thư mục

```
vn-review-sentiment/
├── requirements.txt
├── .env.example
├── sql/
│   └── schema.sql              # Schema PostgreSQL (3 tầng: raw -> processed -> predictions)
├── src/
│   ├── config.py                # Đọc biến môi trường / cấu hình chung
│   ├── db/
│   │   └── db_utils.py          # Kết nối DB, các hàm insert/query dùng chung
│   ├── crawler/
│   │   └── tiki_crawler.py      # Crawl review từ Tiki API công khai
│   ├── preprocessing/
│   │   ├── text_cleaner.py      # Chuẩn hoá + tokenize tiếng Việt
│   │   └── run_preprocessing.py # Script chạy tiền xử lý cho toàn bộ review
│   └── models/
│       ├── train_sentiment.py   # Huấn luyện TF-IDF + Logistic Regression
│       └── predict.py           # Dự đoán & ghi kết quả vào bảng sentiment_predictions
└── dashboard/
    └── app.py                    # Streamlit dashboard
```

## Cài đặt

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` thành `.env` và điền thông tin kết nối PostgreSQL của bạn.

## Khởi tạo database

> **Không có lệnh `psql` trên máy (thường gặp trên Windows)?**
> Bỏ qua các cách dùng `psql` bên dưới, chạy thẳng:
> ```bash
> python -m src.db.init_schema
> ```
> Script này đọc file `sql/schema.sql` và chạy trực tiếp qua `psycopg2`
> (không cần cài PostgreSQL client tools). Nhớ đã điền đúng `.env` trước khi chạy.

### Dùng PostgreSQL local
```bash
psql -U <user> -d <database> -f sql/schema.sql
```

### Dùng Aiven Cloud PostgreSQL

1. Vào **Aiven Console** > service PostgreSQL của bạn > tab **Overview**, lấy
   các thông tin: `Host`, `Port`, `User`, `Password`, `Database name` (thường
   là `defaultdb`).
2. Điền các giá trị đó vào `.env` (xem `.env.example`), nhớ đặt:
   ```
   DB_SSLMODE=require
   ```
   vì Aiven **bắt buộc kết nối qua SSL**, nếu để `disable` sẽ bị từ chối kết nối.
3. Chạy schema trực tiếp bằng connection string Aiven cung cấp
   (Aiven gọi là "Service URI", dạng
   `postgres://avnadmin:<password>@<host>:<port>/defaultdb?sslmode=require`):
   ```bash
   psql "postgres://avnadmin:<password>@<host>:<port>/defaultdb?sslmode=require" -f sql/schema.sql
   ```
   Hoặc dùng từng biến riêng:
   ```bash
   psql -h <host> -p <port> -U avnadmin -d defaultdb "sslmode=require" -f sql/schema.sql
   ```
4. (Tuỳ chọn, bảo mật cao hơn) Nếu muốn xác thực chắc chắn server (chống
   man-in-the-middle) thay vì chỉ mã hoá đường truyền, dùng `sslmode=verify-ca`
   hoặc `verify-full`:
   - Tải file **CA Certificate** trong Aiven Console > Overview > phần
     "CA Certificate" > Download.
   - Lưu file đó vào project (vd `certs/ca.pem`), rồi set trong `.env`:
     ```
     DB_SSLMODE=verify-ca
     DB_SSLROOTCERT=./certs/ca.pem
     ```
   Với pet project học thuật, `sslmode=require` là đủ dùng (đã mã hoá đường
   truyền); `verify-ca`/`verify-full` thường dùng khi lên production.

**Lưu ý về free tier**: gói miễn phí/hobbyist của Aiven thường giới hạn dung
lượng lưu trữ (~1-5GB) và có thể tự tạm dừng (auto-suspend) sau một thời gian
không hoạt động — kiểm tra lại trong Aiven Console nếu crawler báo lỗi kết nối
đột ngột. Cũng nên giới hạn `--max-products` khi crawl để không vượt quota.

## Chạy pipeline theo thứ tự

```bash
# 1. Crawl dữ liệu review từ Tiki 
# (Danh sách các URL và cài đặt được cấu hình trong file run_crawler.py)
python run_crawler.py

# 2. Tiền xử lý (làm sạch + tokenize + weak label từ rating)
python -m src.preprocessing.run_preprocessing

# 3. Huấn luyện model
python -m src.models.train_sentiment

# 4. Dự đoán lại toàn bộ (hoặc review mới) và lưu kết quả
python -m src.models.predict

# 5. Chạy dashboard
streamlit run dashboard/app.py
```

> **Đã tạo DB từ trước và muốn cập nhật lên bản mới nhất?** Chạy lại
> `python -m src.db.init_schema` (hoặc `psql -f sql/schema.sql`) — an toàn để
> chạy lại nhiều lần vì dùng `CREATE TABLE IF NOT EXISTS` / `CREATE OR REPLACE
> VIEW`, sẽ không xoá dữ liệu cũ, chỉ cập nhật view `v_review_full` (thêm cột
> `review_date_effective` dùng để fix biểu đồ xu hướng bị trống).

## Ghi chú quan trọng

- **Nhãn (label)**: dùng "weak label" suy ra từ số sao rating (1-2★ = negative,
  3★ = neutral, 4-5★ = positive). Đây không phải nhãn hoàn hảo — nên lấy mẫu
  100-200 review để kiểm tra thủ công độ lệch, đó là một phần thú vị để phân
  tích/trình bày trong báo cáo.
- **Nhiều danh mục**: `--category-urls` nhận danh sách URL phân cách bởi dấu
  phẩy, mỗi category được crawl độc lập và gắn nhãn `category` (suy ra từ slug
  URL, vd `dien-thoai-smartphone` -> `Dien thoai smartphone`) để lọc trên
  dashboard. `--max-products-per-category` áp dụng cho MỖI category, không
  phải tổng số toàn bộ.
- **Ngày review bị thiếu / biểu đồ xu hướng trống**: Tiki đôi khi trả
  `created_at` ở định dạng không parse được bằng cách cũ. Crawler giờ dùng
  `dateutil.parser` để bao quát nhiều định dạng hơn; ngoài ra view
  `v_review_full` có cột `review_date_effective` tự động dùng ngày crawl làm
  fallback khi không có ngày review thật, để dashboard luôn có dữ liệu vẽ biểu
  đồ. Dashboard hiển thị cảnh báo nếu tỉ lệ dùng ngày fallback quá cao (>30%).
- **Shopee**: Shopee chống bot khá chặt (cần token động, rotate header, dễ bị
  chặn IP). Project này dùng **Tiki** làm nguồn chính vì có API JSON công khai,
  ổn định hơn cho một pet project học thuật. Bạn có thể mở rộng thêm crawler
  Shopee sau bằng Selenium nếu muốn.
- Luôn tôn trọng `robots.txt` và giới hạn tốc độ request (đã có `time.sleep`
  trong crawler) để tránh gây tải cho server và vi phạm điều khoản dịch vụ.
- Model baseline dùng TF-IDF + Logistic Regression để có pipeline chạy nhanh,
  end-to-end. Bạn có thể nâng cấp bằng PhoBERT embedding sau khi baseline chạy ổn.
- **Word Cloud tiếng Việt**: font mặc định của thư viện `wordcloud` có thể không
  hiển thị đúng dấu tiếng Việt. Nếu gặp lỗi hiển thị, tải 1 font hỗ trợ Unicode
  tiếng Việt (vd. Roboto, Noto Sans) và truyền đường dẫn vào tham số
  `font_path` trong hàm `make_wordcloud()` ở `dashboard/app.py`.
