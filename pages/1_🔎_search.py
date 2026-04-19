import streamlit as st
from app import init_connection, category_map, get_displayable_image_url

# 1. DB 연결 설정
client = init_connection()
db = client["oliveyoung_db"]

st.title("🔍 카테고리별 상세 검색")

# 2. 사이드바: 검색 조건 및 필터 설정
with st.sidebar:
    st.header("필터 설정")
    selected_cat = st.selectbox("카테고리 선택", list(category_map.keys()))
    
    st.subheader("상세 필터")
    # 슬라이더 및 입력창을 통해 필터값 수집
    price_range = st.slider("가격대 (원)", 0, 100000, (0, 50000), step=1000)
    min_review = st.number_input("최소 리뷰 수", min_value=0, value=0, step=50) # 기본값을 0으로 낮춰 접근성 향상
    min_rating = st.slider("최소 평점", 0.0, 5.0, 0.0, step=0.1) # 기본값을 0으로 낮춤

# 3. 카테고리별 DB 내부 명칭 매핑 (중요!)
# 사용자가 선택한 카테고리명과 실제 DB의 'category' 필드 값이 다를 경우를 대비합니다.
category_filter_map = {
    "로션": ["로션", "올인원"],
    "미스트/오일": ["미스트/픽서", "페이스오일", "미스트"],
    "스킨/토너": ["스킨/토너", "토너패드", "토너"],
    "에센스/세럼/앰플": ["에센스/세럼/앰플", "에센스", "세럼", "앰플"],
    "크림": ["크림"]
}

# 현재 선택된 카테고리에 해당하는 DB 명칭 리스트 가져오기
db_categories = category_filter_map.get(selected_cat, [selected_cat])

# 사용자가 선택한 컬렉션 (essence, lotion 등)
collection_name = category_map[selected_cat]

# 4. MongoDB 쿼리 작성 ($in 연산자 활용)
query = {
    "category": {"$in": db_categories}, 
    "sale_price": {"$gte": price_range[0], "$lte": price_range[1]},
    "review_count_total": {"$gte": min_review},
    "average_rating": {"$gte": min_rating}
}

# 가성비 점수(value_score) 기준 내림차순 정렬
results = list(db[collection_name].find(query).sort("value_score", -1))

st.subheader(f"'{selected_cat}' 검색 결과 ({len(results)}건)")

# 5. 결과 화면 출력
if results:
    # 4열 그리드 레이아웃
    cols = st.columns(4)
    for idx, product in enumerate(results):
        col_idx = idx % 4
        with cols[col_idx]:
            # 카드 형태의 컨테이너
            with st.container(border=True):
                # 이미지 띄우기 (방어 로직이 포함된 함수 사용)
                raw_url = product.get("image_url")
                display_url = get_displayable_image_url(raw_url)
                st.image(display_url, use_container_width=True)
                
                # 제품명 (글자수 제한)
                product_name = product.get("product_name", "제품명 없음")
                st.markdown(f"**{product_name[:25]}...**")
                
                # 평점 및 리뷰수
                avg_rating = product.get("average_rating", 0)
                review_count = product.get("review_count_total", 0)
                st.caption(f"⭐ {avg_rating} ({review_count:,}개)")
                
                # 판매가 출력
                sale_price = product.get("sale_price")
                if sale_price is not None:
                    st.write(f"**{sale_price:,}원**")
                else:
                    st.write("**가격 정보 없음**")
                
                # 상세 보기 버튼 (세션에 ID 저장 후 페이지 이동)
                if st.button("상세 보기", key=f"search_{product['_id']}"):
                    st.session_state['selected_product_id'] = product['_id']
                    st.session_state['selected_collection'] = collection_name
                    # 이모지가 포함된 실제 파일명으로 이동
                    st.switch_page("pages/2_📄_detail.py")
else:
    st.warning("조건에 맞는 제품이 없습니다. 필터를 조정해 보세요.")