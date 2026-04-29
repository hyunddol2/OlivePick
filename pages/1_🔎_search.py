import streamlit as st
from app import init_connection, category_map, get_displayable_image_url, scroll_collection

# ── DB 연결 ───────────────────────────────────────────────────────
client = init_connection()

st.title("🔍 카테고리별 상세 검색")

# ── 사이드바: 검색 조건 및 필터 설정 ──────────────────────────────
with st.sidebar:
    st.header("필터 설정")
    selected_cat = st.selectbox("카테고리 선택", list(category_map.keys()))

    st.subheader("상세 필터")
    price_range = st.slider("가격대 (원)", 0, 100000, (0, 50000), step=1000)
    min_review = st.number_input("최소 리뷰 수", min_value=0, value=0, step=50)
    min_rating = st.slider("최소 평점", 0.0, 5.0, 0.0, step=0.1)

# ── 카테고리 → DB 내부 명칭 매핑 ─────────────────────────────────
# Qdrant payload의 'category' 필드 값 목록
category_filter_map = {
    "로션": ["로션", "올인원"],
    "미스트/오일": ["미스트/픽서", "페이스오일", "미스트"],
    "스킨/토너": ["스킨/토너", "토너패드", "토너"],
    "에센스/세럼/앰플": ["에센스/세럼/앰플", "에센스", "세럼", "앰플"],
    "크림": ["크림"],
}

db_categories = category_filter_map.get(selected_cat, [selected_cat])
collection_name = category_map[selected_cat]

# ── Qdrant 필터 구성 ──────────────────────────────────────────────
qdrant_filter = {
    "must": [
        {
            "should": [
                {"key": "category", "match": {"value": cat}}
                for cat in db_categories
            ]
        },
        # DB의 sale_price가 "43,000원" 형태라면 range 필터가 작동하지 않습니다.
        # olive_clean_price(숫자형) 필드를 사용하는 것이 안전합니다.
        {"key": "olive_clean_price", "range": {"gte": price_range[0], "lte": price_range[1]}},
        {"key": "olive_review_count", "range": {"gte": min_review}},
        {"key": "olive_rating", "range": {"gte": min_rating}},
    ]
}

# value_score 내림차순 정렬, 최대 200개 조회
results = scroll_collection(
    client,
    collection=collection_name,
    filters=qdrant_filter,
    limit=200,
    order_by="final_recommend_score", # 정렬 키 변경
)

st.subheader(f"'{selected_cat}' 검색 결과 ({len(results)}건)")

# ── 결과 화면 출력 ────────────────────────────────────────────────
if results:
    cols = st.columns(4)
    for idx, point in enumerate(results):
        product = point.get("payload", {})
        point_id = point.get("id")

        col_idx = idx % 4
        with cols[col_idx]:
            with st.container(border=True):
                raw_url = product.get("olive_image_url")
                display_url = get_displayable_image_url(raw_url)
                st.image(display_url, use_container_width=True)

                product_name = product.get("olive_name", "제품명 없음")
                st.markdown(f"**{product_name[:25]}...**")

                avg_rating = product.get("olive_rating", 0)
                review_count = product.get("olive_review_count", 0)
                st.caption(f"⭐ {avg_rating} ({review_count:,}개)")

                sale_price = product.get("sale_price")
                if sale_price is not None:
                    st.write(f"**{sale_price}**")
                else:
                    st.write("**가격 정보 없음**")    

                if st.button("상세 보기", key=f"search_{point_id}"):
                    st.session_state["selected_product_id"] = point_id
                    st.session_state["selected_collection"] = collection_name
                    st.switch_page("pages/2_📄_detail.py")
else:
    st.warning("조건에 맞는 제품이 없습니다. 필터를 조정해 보세요.")
