import streamlit as st
from app import init_connection, get_displayable_image_url, get_point, scroll_collection

client = init_connection()

# ── 세션 상태 확인 ────────────────────────────────────────────────
if "selected_product_id" not in st.session_state or "selected_collection" not in st.session_state:
    st.error("선택된 제품이 없습니다. 홈 화면으로 이동해주세요.")
    if st.button("홈으로 가기"):
        st.switch_page("app.py")
    st.stop()

point_id = st.session_state["selected_product_id"]
collection_name = st.session_state["selected_collection"]

# ── 단일 포인트 조회 ──────────────────────────────────────────────
point = get_point(client, collection_name, point_id)

if point:
    product = point.get("payload", {})

    col1, col2 = st.columns([1, 1.5])

    with col1:
        # 여러 이미지 필드 대응
        raw_url = product.get("olive_image_url") or product.get("naver_image_url") or product.get("musinsa_image_url")
        display_url = get_displayable_image_url(raw_url)
        st.image(display_url, use_container_width=True)

    with col2:
        # 배지 처리
        if product.get("badges"):
            badges_html = "".join([
                f"<span style='background:#f0f0f0; padding:4px 8px; border-radius:4px; "
                f"margin-right:5px; font-size:12px;'>{b}</span>"
                for b in product["badges"]
            ])
            st.markdown(badges_html, unsafe_allow_html=True)
            st.write("")

        # 제품명 (DB 필드명: olive_name)
        product_name = product.get("olive_name", "제품명 없음")
        st.title(product_name)
        st.caption(f"카테고리: {product.get('category', 'N/A')}")

        st.divider()
        
        # 가격 정보
        sale_price = product.get("sale_price", "가격 정보 없음")
        original_price = product.get("original_price", "정보 없음")
        discount_rate = product.get("discount_rate")

        # [수정 포인트] discount_rate 타입 에러 방지 로직
        is_discounted = False
        try:
            if discount_rate is not None:
                # 문자열일 경우 숫자로 변환 시도
                if float(discount_rate) > 0:
                    is_discounted = True
        except (ValueError, TypeError):
            is_discounted = False

        delta_str = f"-{discount_rate}% 할인" if is_discounted else None
        
        # metric 출력 (sale_price는 문자열이므로 포맷팅 없이 출력)
        st.metric(label="판매가", value=sale_price, delta=delta_str, delta_color="inverse")

        st.markdown(f"**정상가:** {original_price}")

        st.write("---")
        st.markdown(f"**용량:** {product.get('volume', '표기 없음')}")

        # 용량당 가격
        price_per_ml = product.get("olive_price_per_ml")
        if price_per_ml is not None:
            st.markdown(f"**용량당 가격 (1ml):** 약 {int(price_per_ml):,}원")
        else:
            st.markdown("**용량당 가격 (1ml):** 정보 없음")

        # 평점 및 리뷰 수
        avg_rating = product.get("olive_rating", 0)
        review_count = product.get("olive_review_count", 0)
        st.markdown(f"**평점:** ⭐ {avg_rating} (리뷰 {review_count:,}개)")

    st.divider()
    st.subheader("📊 가성비 분석 지표 (Sentiment)")
    
    q_score = product.get("Q_mass_total", 0)
    e_score = product.get("E_mass_total", 0)
    s_score = product.get("S_mass_total", 0)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("품질 만족도(Q)", f"{q_score:.2f}")
    c2.metric("감성 점수(E)", f"{e_score:.2f}")
    c3.metric("사회적 평가(S)", f"{s_score:.2f}")

    # ── 리뷰 조회 ─────────────────────────────────────────────────
    st.subheader("💬 주요 리뷰")
    review_collection = collection_name.replace("_products", "_reviews")

    review_filter = {
        "must": [
            {
                "key": "olive_id",
                "match": {"value": product.get("olive_id")},
            }
        ]
    }

    try:
        reviews = scroll_collection(
            client,
            collection=review_collection,
            filters=review_filter,
            limit=5,
        )
    except Exception:
        reviews = []

    if reviews:
        for rev_point in reviews:
            rev = rev_point.get("payload", {})
            with st.chat_message("user"):
                st.markdown(
                    f"**익명 사용자** "
                    f"(평점: {rev.get('score', 0)}점)"
                )
                st.write(rev.get("text", "내용 없음"))
    else:
        st.write("등록된 리뷰가 없습니다.")

    if st.button("목록으로 돌아가기"):
        st.switch_page("pages/1_🔎_search.py")

else:
    st.error("제품 정보를 불러올 수 없습니다.")
    if st.button("홈으로 가기"):
        st.switch_page("app.py")