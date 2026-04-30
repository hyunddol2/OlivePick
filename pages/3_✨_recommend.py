import numpy as np
import streamlit as st
from app import init_connection, category_map, get_displayable_image_url, scroll_collection

# ── 1. 페이지 설정 및 CSS 주입 ────────────────────────────────────────────────
st.set_page_config(page_title="맞춤 추천", page_icon="✨", layout="wide")

st.markdown("""
    <style>
    .product-title {
        font-size: 18px;
        font-weight: bold;
        line-height: 1.4;
        margin-bottom: 10px;
        color: #222;
    }
    .highlight-score {
        background: linear-gradient(to top, #fff59d 45%, transparent 45%);
        font-size: 22px;
        font-weight: 900;
        color: #000;
        padding: 0 2px;
    }
    .price-text {
        font-size: 18px;
        font-weight: bold;
        color: #000;
    }
    </style>
""", unsafe_allow_html=True)

client = init_connection()

# ── app.py의 category_map과 동일한 키 사용 (일관성 확보) ──────────────────────
cat_to_collection = {
    "크림": "cream_products",
    "에센스/세럼/앰플": "essence_products",
    "로션": "lotion_products",
    "미스트/오일": "mist_products",
    "스킨/토너": "skintoner_products",
}

# DB 내부 카테고리명 매핑 (search.py와 동일하게 유지)
category_filter_map = {
    "로션": ["로션", "올인원"],
    "미스트/오일": ["미스트/픽서", "페이스오일", "미스트"],
    "스킨/토너": ["스킨/토너", "토너패드", "토너"],
    "에센스/세럼/앰플": ["에센스/세럼/앰플", "에센스", "세럼", "앰플"],
    "크림": ["크림"],
}

st.title("✨ 나를 위한 맞춤 가성비 추천")
st.subheader("당신이 생각하는 가치별 중요도를 선택해 주세요")

# ── 2. 사이드바: 사용자 입력 및 필터 ─────────────────────────────────────────
with st.sidebar:
    st.header("🔍 선호도 설정")
    cat_kor = st.selectbox("카테고리 선택", list(cat_to_collection.keys()))
    collection_name = cat_to_collection[cat_kor]
    db_categories = category_filter_map.get(cat_kor, [cat_kor])

    show_promo_only = st.checkbox("🔥 프로모션 특가 제품만 보기")

    st.divider()

    slider_labels = {
        1: "1: 상관없음",
        2: "2: 고려하지 않음",
        3: "3: 보통",
        4: "4: 중요",
        5: "5: 매우 중요"
    }

    s_q = st.select_slider("Q: 성분과 기능의 확실한 효과",        options=[1,2,3,4,5], value=3, format_func=lambda x: slider_labels[x])
    s_e = st.select_slider("E: 많은 사람이 선택한 인기 아이템",   options=[1,2,3,4,5], value=3, format_func=lambda x: slider_labels[x])
    s_s = st.select_slider("S: 디자인이나 향 등의 감성적 만족",   options=[1,2,3,4,5], value=3, format_func=lambda x: slider_labels[x])
    s_p = st.select_slider("P: 저렴한 가격",                      options=[1,2,3,4,5], value=3, format_func=lambda x: slider_labels[x])

    total_s = s_q + s_e + s_s + s_p
    w_q, w_e, w_s, w_p = s_q/total_s, s_e/total_s, s_s/total_s, s_p/total_s

# ── 3. [개선①] st.cache_data — 카테고리별 데이터 캐싱 ────────────────────────
# 동일 카테고리 반복 요청 시 Qdrant 호출 없이 캐시에서 즉시 반환 (TTL: 10분)
# Redis Hot Storage의 간소화 버전 — 계층적 데이터 접근 구조 구현
@st.cache_data(ttl=600, show_spinner=False)
def get_category_products(collection: str, db_cats: tuple) -> list:
    """
    [데이터 엔지니어링 포인트]
    - Metadata Filtering: 컬렉션(1차) + 카테고리 필드(2차) 이중 필터로 검색 범위 축소
    - Pre-filtering: 쿼리 시점에 불필요한 데이터를 DB 레벨에서 제거
    - Cache: 동일 카테고리 재조회 시 DB 호출 0회 (메모리에서 즉시 반환)
    """
    # [개선②] Metadata Filtering — recommend.py에서도 카테고리 필터 적용
    # 기존: filters=None 으로 컬렉션 전체 조회
    # 개선: category 필드 기준 Pre-filtering으로 검색 대상 대폭 축소
    qdrant_filter = {
        "must": [
            {
                "should": [
                    {"key": "category", "match": {"value": cat}}
                    for cat in db_cats
                ]
            }
        ]
    }
    return scroll_collection(client, collection=collection, filters=qdrant_filter, limit=200)


# ── 4. [개선②] NumPy 배치 연산 ───────────────────────────────────────────────
# 고정 계수 (모델 학습으로 결정된 값)
C = np.array([0.4471, 0.0510, 0.0287, 0.4732])


def calculate_scores_batch(payloads: list, w_q: float, w_e: float, w_s: float, w_p: float) -> np.ndarray:
    """
    [데이터 엔지니어링 포인트] Batch Vectorization
    - 기존: Python for loop으로 제품 1개씩 개별 계산 → O(n) 순차 연산
    - 개선: 전체 제품을 행렬 M ∈ R^(n×4) 로 구성 후 행렬 곱 1회로 처리
    - 수식: scores = M @ (C * W)  (SIMD 가속, 마이크로초 단위 완료)
    - 제품 수가 늘어날수록 for loop 대비 성능 격차가 기하급수적으로 증가
    """
    W = np.array([w_q, w_e, w_s, w_p])
    CW = C * W  # element-wise: 고정 계수 × 사용자 가중치

    # 제품 수(n) × 4 행렬 구성
    M = np.array([
        [
            p.get("Q_pos_product", 0) if not p.get("olive_is_promo") else p.get("promo_Q_pos_product", 0),
            p.get("E_pos_product", 0) if not p.get("olive_is_promo") else p.get("promo_E_pos_product", 0),
            p.get("S_pos_product", 0) if not p.get("olive_is_promo") else p.get("promo_S_pos_product", 0),
            min(p.get("P_score", 0) + (0.5 if p.get("olive_is_promo") else 0), 1.0),
        ]
        for p in payloads
    ], dtype=np.float32)  # float32: 메모리 절감 + 연산 속도 향상

    return M @ CW  # 행렬 곱 1회로 n개 점수 동시 계산 → shape: (n,)


# ── 5. 추천 실행 버튼 ─────────────────────────────────────────────────────────
if st.button("내 취향 분석 및 추천받기", type="primary", use_container_width=True):
    with st.spinner("최적의 밸런스를 찾는 중..."):

        # 캐시된 데이터 로드 (Metadata Filtering 적용됨)
        all_points = get_category_products(collection_name, tuple(db_categories))

        # 프로모션 필터 (메모리 레벨)
        if show_promo_only:
            all_points = [p for p in all_points if p.get("payload", {}).get("olive_is_promo", False)]

        payloads = [p.get("payload", {}) for p in all_points]

        if not payloads:
            st.warning("조건에 맞는 제품이 없습니다. 필터를 조정해 보세요.")
            st.stop()

        # NumPy 배치 연산으로 전체 점수 한 번에 계산
        scores = calculate_scores_batch(payloads, w_q, w_e, w_s, w_p)

        # np.argsort로 정렬도 벡터 연산 처리
        top3_idx = np.argsort(scores)[::-1][:3]

        top3 = []
        for i in top3_idx:
            item = payloads[i].copy()
            item["final_user_score"] = float(scores[i])
            item["point_id"] = all_points[i].get("id")
            top3.append(item)

        st.session_state["top3_results"] = top3
        st.session_state["last_collection"] = collection_name

# ── 6. 결과 출력 ──────────────────────────────────────────────────────────────
if "top3_results" in st.session_state:
    st.divider()
    for i, item in enumerate(st.session_state["top3_results"]):
        with st.container(border=True):
            col1, col2 = st.columns([1, 2.5])
            with col1:
                img_url = get_displayable_image_url(item.get("olive_image_url"))
                st.image(img_url, use_container_width=True)

            with col2:
                # 프로모션 배지
                if item.get("olive_is_promo"):
                    st.markdown("🎯 <span style='color:#FF4B4B; font-weight:bold;'>Promotion 진행 중</span>", unsafe_allow_html=True)

                # 순위 및 제품명
                st.markdown(f'<div class="product-title">{i+1}위. {item.get("olive_name", "제품명 없음")}</div>', unsafe_allow_html=True)

                # 평점 및 리뷰 수
                rating = item.get("olive_rating", 0.0)
                reviews = item.get("olive_review_count", 0)
                st.markdown(f"""
                    <div style="font-size: 14px; color: #777; margin-bottom: 10px;">
                        <span style="color: #FFB300;">★</span> {rating}
                        <span style="margin-left: 5px; color: #DDD;">|</span>
                        <span style="margin-left: 5px;">리뷰 {reviews:,}</span>
                    </div>
                """, unsafe_allow_html=True)

                # 판매가
                st.markdown(f'<div class="price-text">💰 판매가: {item.get("sale_price", "정보없음")}</div>', unsafe_allow_html=True)

                st.write("")

                if st.button("제품 상세 정보 보기", key=f"rec_btn_{item['point_id']}", use_container_width=True):
                    st.session_state["selected_product_id"] = item["point_id"]
                    st.session_state["selected_collection"] = st.session_state["last_collection"]
                    st.switch_page("pages/2_📄_detail.py")
