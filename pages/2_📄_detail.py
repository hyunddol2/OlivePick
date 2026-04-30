import re
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

    # ── 프로모션 여부에 따른 데이터 분기 로직 ──────────────────────
    is_promo = product.get("olive_is_promo", False)

    if is_promo:
        q_val = product.get("promo_Q_pos_product", 0)
        e_val = product.get("promo_E_pos_product", 0)
        s_val = product.get("promo_S_pos_product", 0)
        f_score = product.get("promo_recommend_score", 0)
    else:
        q_val = product.get("Q_pos_product", 0)
        e_val = product.get("E_pos_product", 0)
        s_val = product.get("S_pos_product", 0)
        f_score = product.get("final_recommend_score", 0)

    col1, col2 = st.columns([1, 1.5])

    with col1:
        raw_url = product.get("olive_image_url") or product.get("naver_image_url") or product.get("musinsa_image_url")
        display_url = get_displayable_image_url(raw_url)
        st.image(display_url, use_container_width=True)

    with col2:
        if product.get("badges"):
            badges_html = "".join([
                f"<span style='background:#f0f0f0; padding:4px 8px; border-radius:4px; "
                f"margin-right:5px; font-size:12px;'>{b}</span>"
                for b in product["badges"]
            ])
            st.markdown(badges_html, unsafe_allow_html=True)
            st.write("")

        product_name = product.get("olive_name", "제품명 없음")
        st.title(product_name)
        st.caption(f"카테고리: {product.get('category', 'N/A')}")

        st.divider()
        
        sale_price = product.get("sale_price", "가격 정보 없음")
        original_price = product.get("original_price", "정보 없음")
        discount_rate = product.get("discount_rate")

        is_discounted = False
        try:
            if discount_rate is not None:
                if float(discount_rate) > 0:
                    is_discounted = True
        except (ValueError, TypeError):
            is_discounted = False

        delta_str = f"-{discount_rate}% 할인" if is_discounted else None
        
        st.metric(label="판매가", value=sale_price, delta=delta_str, delta_color="inverse")
        st.markdown(f"**정상가:** {original_price}")

        st.write("---")
        st.markdown(f"**용량:** {product.get('volume', '표기 없음')}")

        price_per_ml = product.get("olive_price_per_ml")
        if price_per_ml is not None:
            st.markdown(f"**용량당 가격 (1ml):** 약 {int(price_per_ml):,}원")
        else:
            st.markdown("**용량당 가격 (1ml):** 정보 없음")

        avg_rating = product.get("olive_rating", 0)
        review_count = product.get("olive_review_count", 0)
        st.markdown(f"**평점:** ⭐ {avg_rating} (리뷰 {review_count:,}개)")

    st.divider()
    
    st.subheader("🎯 최종 추천 분석")
    if is_promo:
        st.success("✅ 이 제품은 '프로모션 혜택'이 적용된 가성비 지표를 보여줍니다.")

    keywords = product.get("product_keyword", [])

    k1, k2 = st.columns([1, 2])
    with k1:
        display_f_score = f_score * 100
        st.metric("최종 가성비 점수", f"{display_f_score:.1f} / 100")
    with k2:
        if keywords:
            kw_html = "".join([
                f"<span style='background:#E1F5FE; color:#01579B; padding:5px 12px; border-radius:20px; "
                f"margin-right:8px; font-size:14px; font-weight:bold;'>#{kw}</span>"
                for kw in keywords
            ])
            st.markdown(kw_html, unsafe_allow_html=True)
        else:
            st.write("분석된 키워드가 없습니다.")

    st.write("") 

    st.subheader("📊 상세 가성비 지표 (Q·E·S)")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("**🛡️ 품질 지수 (Q)**")
        st.progress(float(min(q_val, 1.0)))
        st.write(f"점수: **{q_val * 100:.1f}점**")
        with st.expander("Q 지수란?"):
            st.caption("품질 지수로 '성분과 기능의 확실한 효과'를 의미합니다.")

    with c2:
        st.markdown("**🤝 사회적 가치 지수 (E)**")
        st.progress(float(min(e_val, 1.0)))
        st.write(f"점수: **{e_val * 100:.1f}점**")
        with st.expander("E 지수란?"):
            st.caption("사회적 가치 지수로 '많은 사람이 선택한 인기 아이템'을 의미합니다.")

    with c3:
        st.markdown("**✨ 감성 지수 (S)**")
        st.progress(float(min(s_val, 1.0)))
        st.write(f"점수: **{s_val * 100:.1f}점**")
        with st.expander("S 지수란?"):
            st.caption("감성 지수로 '디자인이나 향 등의 감성적 만족'을 의미합니다.")

    st.divider()

    st.subheader("💬 주요 리뷰")
    reviews = [] 
    review_collection = collection_name.replace("_products", "_reviews")

    review_filter = {
        "must": [
            {"key": "olive_id", "match": {"value": product.get("olive_id")}}
        ]
    }

    try:
        reviews = scroll_collection(client, collection=review_collection, filters=review_filter, limit=5)
    except Exception:
        reviews = []

    if reviews:
        for rev_point in reviews:
            rev = rev_point.get("payload", {})
            raw_text = rev.get("text", "")
            clean_text = re.sub(r'옵션 및 피부타입:.*?리뷰 내용:', '', raw_text).strip()
            clean_text = clean_text.replace("옵션 및 피부타입: |", "").replace("옵션 및 피부타입:|", "").replace("리뷰 내용:", "").strip()

            st.markdown(f"""
                <div style="background-color: #f9f9f9; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
                    {clean_text}
                </div>
            """, unsafe_allow_html=True)
    else:
        st.write("등록된 리뷰가 없습니다.")

    if st.button("목록으로 돌아가기"):
        st.switch_page("pages/1_🔎_search.py")

else:
    st.error("제품 정보를 불러올 수 없습니다.")
    if st.button("홈으로 가기"):
        st.switch_page("app.py")