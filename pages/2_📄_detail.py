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


# ── [추가] 유사 제품 추천 함수 ────────────────────────────────────
def get_similar_products(client, collection: str, pid, limit: int = 4) -> list:
    """
    [데이터 엔지니어링 포인트] 벡터 유사도 기반 추천
    - Qdrant /recommend API: point_id만 넘기면 해당 벡터를 DB에서 직접 참조
    - 벡터를 꺼내서 직접 계산할 필요 없이 DB 레벨에서 코사인 유사도 계산
    - size=768 BERT 계열 임베딩 벡터 활용 (메타데이터 필터링과 결합 가능)
    """
    r = client.post(
        f"/collections/{collection}/points/recommend",
        json={
            "positive": [pid],
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        }
    )
    r.raise_for_status()
    return r.json().get("result", [])


if point:
    product = point.get("payload", {})

    # ── [수정] promo 필드 존재 여부 확인 후 분기 ─────────────────
    # olive_is_promo가 True여도 promo_ 필드가 없는 제품이 있음
    # → promo_recommend_score 존재 여부로 실제 분기 결정
    is_promo = product.get("olive_is_promo", False)
    has_promo_score = bool(product.get("promo_recommend_score"))

    if is_promo and has_promo_score:
        q_val = product.get("promo_Q_pos_product", 0)
        e_val = product.get("promo_E_pos_product", 0)
        s_val = product.get("promo_S_pos_product", 0)
        f_score = product.get("promo_recommend_score", 0)
    else:
        # promo 필드 없으면 일반 필드로 fallback
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
    if is_promo and has_promo_score:
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

    st.divider()

    # ── 유사 제품 추천 섹션 ───────────────────────────────────────
    st.subheader("🔎 비슷한 제품")
    st.caption("현재 제품과 벡터 유사도가 높은 제품을 추천합니다.")

    try:
        similar_products = get_similar_products(client, collection_name, point_id, limit=4)

        if similar_products:
            cols = st.columns(4)
            for idx, sim_point in enumerate(similar_products):
                sim_product = sim_point.get("payload", {})
                sim_id = sim_point.get("id")

                with cols[idx]:
                    with st.container(border=True):
                        sim_url = get_displayable_image_url(sim_product.get("olive_image_url"))
                        st.image(sim_url, use_container_width=True)

                        st.markdown(f"""
                            <div style="font-size: 13px; font-weight: bold; height: 40px;
                                        overflow: hidden; text-overflow: ellipsis;
                                        display: -webkit-box; -webkit-line-clamp: 2;
                                        -webkit-box-orient: vertical; line-height: 1.4;
                                        margin-bottom: 8px; color: #222;">
                                {sim_product.get("olive_name", "제품명 없음")}
                            </div>
                        """, unsafe_allow_html=True)

                        sim_score = sim_product.get("final_recommend_score", 0)
                        st.markdown(f"""
                            <div style="margin-bottom: 6px;">
                                <span style="font-size: 12px; color: #666;">📊 가성비 점수</span><br>
                                <span style="background: linear-gradient(to top, #fff59d 45%, transparent 45%);
                                             font-size: 16px; font-weight: 900; color: #000;">
                                    {sim_score * 100:.1f}점
                                </span>
                            </div>
                        """, unsafe_allow_html=True)

                        st.markdown(f"""
                            <div style="margin-bottom: 10px;">
                                <b style="color: #000; font-size: 15px;">
                                    {sim_product.get("sale_price", "가격 정보 없음")}
                                </b>
                            </div>
                        """, unsafe_allow_html=True)

                        if st.button("보기", key=f"sim_{sim_id}", use_container_width=True):
                            st.session_state["selected_product_id"] = sim_id
                            st.session_state["selected_collection"] = collection_name
                            st.switch_page("pages/2_📄_detail.py")
        else:
            st.info("유사한 제품을 찾을 수 없습니다.")

    except Exception:
        st.info("유사 제품 추천을 불러오는 중 오류가 발생했습니다.")

    st.write("")

    if st.button("목록으로 돌아가기"):
        st.switch_page("pages/1_🔎_search.py")

else:
    st.error("제품 정보를 불러올 수 없습니다.")
    if st.button("홈으로 가기"):
        st.switch_page("app.py")
