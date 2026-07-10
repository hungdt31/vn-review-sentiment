"""
Dashboard Streamlit: thống kê kết quả phân loại sentiment review.

Chạy: streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

# Cho phép import module 'src' khi chạy từ thư mục dashboard/
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st
from wordcloud import WordCloud
import matplotlib.pyplot as plt

from src.db.db_utils import get_connection

st.set_page_config(page_title="VN Review Sentiment Dashboard", layout="wide")


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM v_review_full;", conn)
    return df


st.title("📊 Dashboard Phân tích Sentiment Review Tiếng Việt")

df = load_data()

if df.empty:
    st.warning(
        "Chưa có dữ liệu. Hãy chạy crawler -> preprocessing -> train -> predict trước."
    )
    st.stop()

# ---------------- Sidebar filters ----------------
st.sidebar.header("Bộ lọc")

categories = ["Tất cả"] + sorted(df["category"].dropna().unique().tolist())
selected_category = st.sidebar.selectbox("Danh mục sản phẩm", categories)

products = ["Tất cả"] + sorted(df["product_name"].dropna().unique().tolist())
selected_product = st.sidebar.selectbox("Sản phẩm", products)

label_filter = st.sidebar.multiselect(
    "Nhãn cảm xúc (predicted)",
    options=["positive", "neutral", "negative"],
    default=["positive", "neutral", "negative"],
)

filtered = df.copy()
if selected_category != "Tất cả":
    filtered = filtered[filtered["category"] == selected_category]
if selected_product != "Tất cả":
    filtered = filtered[filtered["product_name"] == selected_product]
if label_filter:
    filtered = filtered[filtered["predicted_label"].isin(label_filter)]

# ---------------- Overview metrics ----------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Tổng số review", len(filtered))
col2.metric("Số sản phẩm", filtered["product_id"].nunique())

pos_rate = (filtered["predicted_label"] == "positive").mean() * 100 if len(filtered) else 0
neg_rate = (filtered["predicted_label"] == "negative").mean() * 100 if len(filtered) else 0
col3.metric("Tỉ lệ tích cực", f"{pos_rate:.1f}%")
col4.metric("Tỉ lệ tiêu cực", f"{neg_rate:.1f}%")

st.divider()

# ---------------- Sentiment distribution ----------------
left, right = st.columns(2)

with left:
    st.subheader("Phân bố cảm xúc (predicted)")
    label_counts = filtered["predicted_label"].value_counts().reset_index()
    label_counts.columns = ["label", "count"]
    color_map = {"positive": "#2ecc71", "neutral": "#95a5a6", "negative": "#e74c3c"}
    fig = px.pie(
        label_counts, names="label", values="count",
        color="label", color_discrete_map=color_map, hole=0.4,
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("So sánh nhãn thực tế (rating) vs dự đoán model")
    compare_df = filtered.dropna(subset=["weak_label", "predicted_label"])
    if not compare_df.empty:
        compare_df = compare_df.copy()
        compare_df["match"] = compare_df["weak_label"] == compare_df["predicted_label"]
        match_rate = compare_df["match"].mean() * 100
        st.metric("Độ khớp weak-label vs model", f"{match_rate:.1f}%")
        confusion = pd.crosstab(compare_df["weak_label"], compare_df["predicted_label"])
        st.dataframe(confusion, use_container_width=True)
    else:
        st.info("Chưa đủ dữ liệu để so sánh.")

st.divider()

# ---------------- Trend theo thời gian ----------------
st.subheader("Xu hướng cảm xúc theo thời gian")

# Dùng review_date_effective (đã fallback về ngày crawl nếu Tiki không trả
# được ngày review cụ thể) để biểu đồ không bị trống hoàn toàn.
if filtered["review_date_effective"].notna().any():
    trend_df = filtered.dropna(subset=["review_date_effective", "predicted_label"]).copy()
    trend_df["review_date_effective"] = pd.to_datetime(trend_df["review_date_effective"])
    trend_df["month"] = trend_df["review_date_effective"].dt.to_period("M").astype(str)
    trend_agg = trend_df.groupby(["month", "predicted_label"]).size().reset_index(name="count")
    fig_trend = px.line(
        trend_agg, x="month", y="count", color="predicted_label",
        color_discrete_map=color_map, markers=True,
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    # Cảnh báo nếu phần lớn dùng ngày fallback (ngày crawl) thay vì ngày review thật
    missing_real_date_rate = filtered["review_date"].isna().mean() * 100
    if missing_real_date_rate > 30:
        st.caption(
            f"⚠️ {missing_real_date_rate:.0f}% review không có ngày đăng thực tế từ Tiki — "
            "biểu đồ đang dùng ngày crawl thay thế cho các review đó, nên xu hướng theo "
            "thời gian có thể không phản ánh đúng thời điểm khách hàng thực sự đăng review."
        )
else:
    st.info("Không có dữ liệu ngày tháng để vẽ xu hướng.")

st.divider()

# ---------------- Top sản phẩm ----------------
st.subheader("Top sản phẩm theo số lượng review tiêu cực")
neg_by_product = (
    filtered[filtered["predicted_label"] == "negative"]
    .groupby("product_name").size().reset_index(name="negative_count")
    .sort_values("negative_count", ascending=False).head(10)
)
if not neg_by_product.empty:
    fig_bar = px.bar(neg_by_product, x="negative_count", y="product_name", orientation="h")
    fig_bar.update_layout(yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("Không có review tiêu cực trong dữ liệu đã lọc.")

st.divider()

# ---------------- Word cloud ----------------
st.subheader("Word Cloud từ khóa nổi bật")
wc_col1, wc_col2 = st.columns(2)

def make_wordcloud(text_series: pd.Series, title: str):
    text = " ".join(text_series.dropna().tolist())
    if not text.strip():
        st.info(f"Không đủ dữ liệu cho {title}.")
        return
    wc = WordCloud(width=600, height=400, background_color="white",
                    font_path=None).generate(text)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(title)
    st.pyplot(fig)

with wc_col1:
    make_wordcloud(
        filtered[filtered["predicted_label"] == "positive"]["tokens"], "Từ khóa Tích cực"
    )
with wc_col2:
    make_wordcloud(
        filtered[filtered["predicted_label"] == "negative"]["tokens"], "Từ khóa Tiêu cực"
    )

st.divider()

# ---------------- Bảng chi tiết ----------------
st.subheader("Chi tiết review")
display_cols = [
    "product_name", "rating", "raw_text", "predicted_label", "confidence", "review_date",
]
st.dataframe(
    filtered[display_cols].sort_values("review_date", ascending=False),
    use_container_width=True, height=400,
)
