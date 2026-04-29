import streamlit as st
from app import init_connection, get_displayable_image_url, scroll_collection

# 페이지 설정
st.set_page_config(page_title="맞춤 추천", page_icon="✨")
client = init_connection()

st.title("✨ 나만을 위한 맞춤 가성비 추천")
st.write("당신이 가장 중요하게 생각하는 가치를 선택해 주세요.")

# ── 사이드바: 사용자 입력 ────────────────────────────────────────
with st.sidebar:
    st.header("🔍 선호도 설정")
    cat_kor = st.selectbox("카테고리 선택", ["크림", "에센스", "로션", "미스트", "스킨/토너"])
    
    cat_map = {
        "크림": "cream_products",
        "에센스": "essence_products",
        "로션": "lotion_products",
        "미스트": "mist_products",
        "스킨/토너": "skintoner_products"
    }
    collection_name = cat_map[cat_kor]

    st.divider()
    
    slider_labels = {
        1: "1: 상관없음",
        2: "2: 고려하지 않음",
        3: "3: 보통",
        4: "4: 중요",
        5: "5: 매우 중요"
    }

    s_q = st.select_slider("Q: 성분과 기능의 확실한 효과", options=[1, 2, 3, 4, 5], value=3, format_func=lambda x: slider_labels[x])
    s_e = st.select_slider("E: 많은 사람이 선택한 인기 아이템", options=[1, 2, 3, 4, 5], value=3, format_func=lambda x: slider_labels[x])
    s_s = st.select_slider("S: 디자인이나 향 등의 감성적 만족", options=[1, 2, 3, 4, 5], value=3, format_func=lambda x: slider_labels[x])
    s_p = st.select_slider("P: 저렴한 가격", options=[1, 2, 3, 4, 5], value=3, format_func=lambda x: slider_labels[x])

    total_s = s_q + s_e + s_s + s_p
    w_q, w_e, w_s, w_p = s_q/total_s, s_e/total_s, s_s/total_s, s_p/total_s

# ── 추천 알고리즘 함수 ──────────────────────────────────────────
def calculate_user_score(product, w_q, w_e, w_s, w_p):
    is_promo = product.get("olive_is_promo", False)
    c_q, c_e, c_s, c_p = 0.4471, 0.0510, 0.0287, 0.4732
    
    if is_promo:
        q_val = product.get("promo_Q_pos_product", 0)
        e_val = product.get("promo_E_pos_product", 0)
        s_val = product.get("promo_S_pos_product", 0)
    else:
        q_val = product.get("Q_pos_product", 0)
        e_val = product.get("E_pos_product", 0)
        s_val = product.get("S_pos_product", 0)
    
    p_val = product.get("P_score", 0)
    return (w_q * c_q * q_val) + (w_e * c_e * e_val) + (w_s * c_s * s_val) + (w_p * c_p * p_val)

# ── 추천 실행 버튼 ─────────────────────────────────────────────
if st.button("내 취향 분석 및 추천받기", type="primary", use_container_width=True):
    with st.spinner("최적의 밸런스를 찾는 중..."):
        all_points = scroll_collection(client, collection=collection_name, limit=100)
        scored_products = []
        for p in all_points:
            payload = p.get("payload", {})
            payload["final_user_score"] = calculate_user_score(payload, w_q, w_e, w_s, w_p)
            payload["point_id"] = p.get("id")
            scored_products.append(payload)
            
        st.session_state["top3_results"] = sorted(scored_products, key=lambda x: x["final_user_score"], reverse=True)[:3]
        st.session_state["last_collection"] = collection_name

# ── 결과 출력 ──────────────────────────────────────────────────
if "top3_results" in st.session_state:
    st.divider()
    for i, item in enumerate(st.session_state["top3_results"]):
        with st.container(border=True):
            col1, col2 = st.columns([1, 2.5])
            with col1:
                img_url = get_displayable_image_url(item.get("olive_image_url"))
                st.image(img_url, use_container_width=True)
            with col2:
                if item.get("olive_is_promo"):
                    st.markdown("🎯 **Promotion 진행 중**")
                st.subheader(f"{i+1}위. {item.get('olive_name', '제품명 없음')}")
                st.write(f"💰 판매가: {item.get('sale_price', '정보없음')}")
                st.info(f"개인 맞춤 가성비 지수: **{item['final_user_score']:.4f}**")
                
                # 버튼 클릭 시 세션에 저장하고 페이지 이동을 직접 수행
                if st.button("제품 상세 정보 보기", key=f"rec_btn_{item['point_id']}"):
                    st.session_state["selected_product_id"] = item['point_id']
                    st.session_state["selected_collection"] = st.session_state["last_collection"]
                    st.switch_page("pages/2_📄_detail.py")