-- ============================================================
-- Schema: Phân tích & Phân loại Sentiment Review Tiếng Việt
-- Thiết kế 3 tầng: raw (products/reviews) -> processed -> predictions
-- ============================================================

-- Drop view và bảng cũ để khởi tạo mới hoàn toàn (không giữ dữ liệu cũ)
DROP VIEW IF EXISTS v_review_full;
DROP TABLE IF EXISTS model_runs;
DROP TABLE IF EXISTS sentiment_predictions;
DROP TABLE IF EXISTS reviews_processed;
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;

CREATE TABLE categories (
    category_id     SERIAL PRIMARY KEY,
    name            VARCHAR(150) NOT NULL UNIQUE,
    url             TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE products (
    product_id      SERIAL PRIMARY KEY,
    source          VARCHAR(20)  NOT NULL,          -- 'tiki' | 'shopee'
    external_id     VARCHAR(100) NOT NULL,
    name            TEXT,
    category_id     INT REFERENCES categories(category_id) ON DELETE SET NULL,
    url             TEXT,
    crawled_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (source, external_id)
);

CREATE TABLE reviews (
    review_id       SERIAL PRIMARY KEY,
    product_id      INT REFERENCES products(product_id) ON DELETE CASCADE,
    external_review_id VARCHAR(100),
    rating          SMALLINT CHECK (rating BETWEEN 1 AND 5),
    raw_text        TEXT NOT NULL,
    review_title    TEXT,
    review_date     DATE,
    author_name     VARCHAR(150),
    crawled_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (product_id, external_review_id)
);

CREATE TABLE reviews_processed (
    review_id       INT PRIMARY KEY REFERENCES reviews(review_id) ON DELETE CASCADE,
    clean_text      TEXT,
    tokens          TEXT,              -- chuỗi token đã tách từ, phân cách bằng khoảng trắng
    token_count     INT,
    weak_label      VARCHAR(20),       -- nhãn suy ra từ rating: positive|negative|neutral
    processed_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sentiment_predictions (
    review_id       INT PRIMARY KEY REFERENCES reviews(review_id) ON DELETE CASCADE,
    predicted_label VARCHAR(20),       -- positive|negative|neutral
    confidence      FLOAT,
    model_version   VARCHAR(50),
    predicted_at    TIMESTAMP DEFAULT NOW()
);

-- Bảng lưu vết mỗi lần train model (để so sánh các phiên bản)
CREATE TABLE model_runs (
    run_id          SERIAL PRIMARY KEY,
    model_version   VARCHAR(50) UNIQUE,
    algorithm       VARCHAR(100),
    train_size      INT,
    test_size       INT,
    accuracy        FLOAT,
    macro_f1        FLOAT,
    notes           TEXT,
    trained_at      TIMESTAMP DEFAULT NOW()
);

-- Index hỗ trợ truy vấn dashboard
CREATE INDEX idx_reviews_product_id ON reviews(product_id);
CREATE INDEX idx_reviews_date ON reviews(review_date);
CREATE INDEX idx_predictions_label ON sentiment_predictions(predicted_label);

-- View tiện lợi để dashboard query nhanh (join sẵn 3 bảng)
CREATE OR REPLACE VIEW v_review_full AS
SELECT
    r.review_id,
    p.product_id,
    p.name        AS product_name,
    c.name        AS category,
    p.source,
    r.rating,
    r.raw_text,
    r.review_date,
    -- Fallback: nếu Tiki không trả được ngày review cụ thể (review_date NULL),
    -- dùng ngày crawl thay thế để biểu đồ "xu hướng theo thời gian" trên
    -- dashboard không bị trống hoàn toàn. Dashboard nên ưu tiên dùng cột này.
    COALESCE(r.review_date, r.crawled_at::date) AS review_date_effective,
    rp.clean_text,
    rp.tokens,
    rp.weak_label,
    sp.predicted_label,
    sp.confidence,
    sp.model_version
FROM reviews r
JOIN products p ON r.product_id = p.product_id
LEFT JOIN categories c ON p.category_id = c.category_id
LEFT JOIN reviews_processed rp ON r.review_id = rp.review_id
LEFT JOIN sentiment_predictions sp ON r.review_id = sp.review_id;
