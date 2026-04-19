import streamlit as st
from app import init_connection, get_displayable_image_url

# 클라이언트를 먼저 받고, DB를 지정해줍니다.
client = init_connection()
db = client["oliveyoung_db"]

if 'selected_product_id' not in st.session_state or 'selected_collection' not in st.session_state:
    st.error("선택된 제품이 없습니다. 홈 화면으로 이동해주세요.")
    if st.button("홈으로 가기"):
        st.switch_page("app.py")
    st.stop()

product_id = st.session_state['selected_product_id']
collection_name = st.session_state['selected_collection']

product = db[collection_name].find_one({"_id": product_id})

if product:
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        # 이미지 띄우기
        raw_url = product.get("image_url")
        display_url = get_displayable_image_url(raw_url)
        st.image(display_url, use_container_width=True)
        
    with col2:
        if product.get("badges"):
            badges_html = "".join([f"<span style='background:#f0f0f0; padding:4px 8px; border-radius:4px; margin-right:5px; font-size:12px;'>{b}</span>" for b in product["badges"]])
            st.markdown(badges_html, unsafe_allow_html=True)
            st.write("")
            
        product_name = product.get("product_name", "제품명 없음")
        st.title(product_name)
        st.caption(f"카테고리: {product.get('category', 'N/A')}")
        
        st.divider()
        sale_price = product.get("sale_price")
        original_price = product.get("original_price")
        discount_rate = product.get("discount_rate")
        
        sale_price_str = f"{sale_price:,}원" if sale_price is not None else "가격 정보 없음"
        delta_str = f"-{discount_rate}% 할인" if discount_rate is not None else None
        
        st.metric(label="판매가", value=sale_price_str, delta=delta_str, delta_color="inverse")
        
        if original_price is not None:
            st.markdown(f"**정상가:** <s>{original_price:,}원</s>", unsafe_allow_html=True)
        else:
            st.markdown("**정상가:** 정보 없음")
        
        st.write("---")
        st.markdown(f"**용량:** {product.get('volume', '표기 없음')}")
        
        price_per_ml = product.get("price_per_ml")
        if price_per_ml is not None:
            st.markdown(f"**용량당 가격 (1ml):** 약 {int(price_per_ml):,}원")
        else:
            st.markdown("**용량당 가격 (1ml):** 정보 없음")
            
        avg_rating = product.get("average_rating", 0)
        review_count = product.get("review_count_total", 0)
        st.markdown(f"**평점:** ⭐ {avg_rating} (리뷰 {review_count:,}개)")
        
    st.divider()
    st.subheader("📊 가성비 분석 지표")
    st.info("이곳에 가격 점수, 성분 품질 점수, 리뷰 감성 분석 결과 등을 차트로 추가할 수 있습니다.")
    
    st.subheader("💬 주요 리뷰")
    review_collection = f"{collection_name}_review"
    reviews = list(db[review_collection].find({"product_id": product.get("product_id")}).limit(3))
    
    if reviews:
        for rev in reviews:
            with st.chat_message("user"):
                st.markdown(f"**{rev.get('nickname', '익명')}** (평점: {rev.get('review_score', 0)}점) - {rev.get('date', '')}")
                st.write(rev.get('review_text', ''))
    else:
        st.write("등록된 리뷰가 없습니다.")

    # 페이지 이동 경로 이모지 반영
    if st.button("목록으로 돌아가기"):
        st.switch_page("pages/1_🔎_search.py")