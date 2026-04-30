import re
import streamlit as st
from app import init_connection, category_map, get_displayable_image_url, scroll_collection

# ── 1. 화면 좌우 꽉 차게 설정 ────────────────────────────────────────────────
st.set_page_config(layout="wide")

# ── 2. CSS 주입 ───────────────────────────────────────────────────────────────
st.markdown("""
    <style>
    .product-title {
        min-height: 50px;
        max-height: 50px;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        font-size: 14px;
        font-weight: bold;
        line-height: 1.4;
        margin-bottom: 5px;
    }
    .rank-badge {
        min-height: 30px;
        max-height: 30px;
        line-height: 30px;
        font-size: 15px;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .product-price {
        min-height: 25px;
        font-size: 16px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# ── DB 연결 ───────────────────────────────────────────────────────────────────
client = init_connection()

st.title("🔍 카테고리별 상세 검색")

# ── 3. 사이드바: 검색 조건 및 필터 설정 ──────────────────────────────────────
with st.sidebar:
    st.header("필터 설정")
    selected_cat = st.selectbox("카테고리 선택", list(category_map.keys()))

    show_promo_only = st.checkbox("🔥 프로모션 특가 제품만 보기")

    st.subheader("상세 필터")
    price_range = st.slider("가격대 (원)", 0, 100000, (0, 50000), step=1000)
    min_review = st.number_input("최소 리뷰 수", min_value=0, value=0, step=50)
    min_rating = st.slider("최소 평점", 0.0, 5.0, 0.0, step=0.1)

# ── 4. 카테고리 → DB 내부 명칭 매핑 ─────────────────────────────────────────
category_filter_map = {
    "로션": ["로션", "올인원"],
    "미스트/오일": ["미스트/픽서", "페이스오일", "미스트"],
    "스킨/토너": ["스킨/토너", "토너패드", "토너"],
    "에센스/세럼/앰플": ["에센스/세럼/앰플", "에센스", "세럼", "앰플"],
    "크림": ["크림"],
}

db_categories = category_filter_map.get(selected_cat, [selected_cat])
collection_name = category_map[selected_cat]

# ── 5. [개선] st.cache_data로 카테고리 전체 데이터 캐싱 ──────────────────────
# 동일 카테고리를 반복 조회 시 Qdrant 호출을 건너뛰고 캐시에서 즉시 반환
# TTL=600초(10분) 후 자동으로 갱신 — Hot Storage 계층 역할
@st.cache_data(ttl=600, show_spinner=False)
def get_all_products(collection: str) -> list:
    return scroll_collection(client, collection=collection, limit=200)

# ── 6. 캐시된 데이터에 Python 레벨 필터 적용 ─────────────────────────────────
# Qdrant 호출은 캐시에서 처리, 필터 연산은 메모리에서 수행
all_products = get_all_products(collection_name)

sort_key = "promo_recommend_score" if show_promo_only else "final_recommend_score"

results = []
for point in all_products:
    product = point.get("payload", {})

    # 카테고리 필터
    if product.get("category") not in db_categories:
        continue
    # 가격 필터
    price = product.get("olive_clean_price", 0) or 0
    if not (price_range[0] <= price <= price_range[1]):
        continue
    # 리뷰 수 필터
    if (product.get("olive_review_count") or 0) < min_review:
        continue
    # 평점 필터
    if (product.get("olive_rating") or 0.0) < min_rating:
        continue
    # 프로모션 필터
    if show_promo_only and not product.get("olive_is_promo", False):
        continue

    results.append(point)

# 가성비 점수 기준 정렬
results.sort(
    key=lambda x: x.get("payload", {}).get(sort_key, 0),
    reverse=True
)

st.subheader(f"'{selected_cat}' 검색 결과 ({len(results)}건)")

# ── 7. 결과 화면 출력 ─────────────────────────────────────────────────────────
if results:
    if show_promo_only:
        st.info("💡 **promotion 제품을 보여드립니다!** 가성비 점수도 promotion 적용됐을 때를 기준으로 산출하여 보여드립니다.")

    cols = st.columns(4)
    for idx, point in enumerate(results):
        product = point.get("payload", {})
        point_id = point.get("id")
        is_promo = product.get("olive_is_promo", False)

        col_idx = idx % 4
        with cols[col_idx]:
            with st.container(border=True):
                # 1. 순위 표시
                rank = idx + 1
                st.markdown('<div class="rank-badge">', unsafe_allow_html=True)
                if rank <= 3:
                    st.markdown(f"🏆 <span style='color:#FF4B4B;'>TOP {rank}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f" <span style='color:#666; font-size:12px;'>{rank}위</span>", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # 2. 이미지 표시
                raw_url = product.get("olive_image_url")
                display_url = get_displayable_image_url(raw_url)
                st.image(display_url, use_container_width=True)

                # 3. 제품명 표시
                product_name = product.get("olive_name", "제품명 없음")
                st.markdown(f"""
                    <div style="font-size: 15px; font-weight: bold; height: 45px;
                                overflow: hidden; text-overflow: ellipsis;
                                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
                                line-height: 1.4; margin-bottom: 12px; color: #222;">
                        {product_name}
                    </div>
                """, unsafe_allow_html=True)

                # 4. 가성비 점수 노출
                if show_promo_only and is_promo:
                    rec_score = product.get("promo_recommend_score", 0)
                    label = "🔥 가성비 점수 (특가)"
                else:
                    rec_score = product.get("final_recommend_score", 0)
                    label = "📊 가성비 점수"

                st.markdown(f"""
                    <div style="margin-bottom: 8px;">
                        <span style="font-size: 13px; font-weight: bold; color: #666;">{label}</span><br>
                        <span style="background: linear-gradient(to top, #fff59d 45%, transparent 45%);
                                     font-size: 19px; font-weight: 900; color: #000; padding: 0 2px;">
                            {rec_score * 100:.1f}점
                        </span>
                    </div>
                """, unsafe_allow_html=True)

                # 5. 평점 및 리뷰 수 표시
                rating = product.get("olive_rating", 0.0)
                reviews = product.get("olive_review_count", 0)
                st.markdown(f"""
                    <div style="font-size: 13px; color: #777; margin-bottom: 4px;">
                        <span style="color: #FFB300;">★</span> {rating}
                        <span style="margin-left: 5px; color: #DDD;">|</span>
                        <span style="margin-left: 5px;">리뷰 {reviews:,}</span>
                    </div>
                """, unsafe_allow_html=True)

                # 6. 가격 정보
                sale_price = product.get("sale_price", "가격 정보 없음")
                st.markdown(f"""
                    <div style="margin-top: 0px; margin-bottom: 12px;">
                        <b style="color: #000; font-size: 17px;">{sale_price}</b>
                    </div>
                """, unsafe_allow_html=True)

                # 7. 상세 보기 버튼
                if st.button("상세 보기", key=f"search_{point_id}", use_container_width=True):
                    st.session_state["selected_product_id"] = point_id
                    st.session_state["selected_collection"] = collection_name
                    st.switch_page("pages/2_📄_detail.py")
else:
    st.warning("조건에 맞는 제품이 없습니다. 필터를 조정해 보세요.")
