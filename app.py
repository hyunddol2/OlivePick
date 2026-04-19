import streamlit as st
from pymongo import MongoClient
import certifi
import re

# 페이지 기본 설정
st.set_page_config(page_title="스킨 제품 가성비 추천", page_icon="🌿", layout="wide")

# 구글 드라이브 링크 변환 및 기본 이미지 처리 함수 (방어 로직 강화 버전)
def get_displayable_image_url(url):
    # 1. 값이 없거나, 비어있거나, "0", "null" 같은 이상한 텍스트인 경우 걸러냄
    url_str = str(url).strip()
    if not url or url_str in ["", "0", "null", "None", "nan"]:
        return "no_image.png" 
    
    # 2. 구글 드라이브 링크인 경우 썸네일 직접 링크로 변환
    if "drive.google.com" in url_str:
        match = re.search(r'(?:id=|/file/d/)([a-zA-Z0-9_-]+)', url_str)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/thumbnail?id={file_id}&sz=w400"
            
    # 3. 만약 'http'로 시작하지 않는 이상한 주소가 남아있다면 그것도 걸러냄
    if not url_str.startswith("http"):
        return "no_image.png"
        
    return url_str

# DB 연결
@st.cache_resource
def init_connection():
    uri = st.secrets["mongo_uri"] 
    return MongoClient(uri, tlsCAFile=certifi.where())

client = init_connection()
db = client["oliveyoung_db"]

category_map = {
    "스킨/토너": "skincare",
    "에센스/세럼/앰플": "essence",
    "크림": "cream",
    "로션": "lotion",
    "미스트/오일": "mist"
}

st.title("🌿 스킨 제품 가성비 추천 시스템")
st.subheader("가격과 리뷰 데이터를 바탕으로 최적의 제품을 추천해드립니다!")
st.divider()

st.header("🏆 카테고리별 가성비 TOP 5")

for kor_cat, eng_col in category_map.items():
    st.markdown(f"### {kor_cat}")
    
    top5_products = list(db[eng_col].find().sort("value_score", -1).limit(5))
    
    if not top5_products:
        st.info("데이터를 불러오는 중이거나 데이터가 없습니다.")
        continue

    cols = st.columns(5)
    for idx, product in enumerate(top5_products):
        with cols[idx]:
            # 이미지 띄우기
            raw_url = product.get("image_url")
            display_url = get_displayable_image_url(raw_url)
            st.image(display_url, use_container_width=True) 
            
            product_name = product.get("product_name", "제품명 없음")
            st.write(f"**{product_name[:20]}...**")
            
            sale_price = product.get("sale_price")
            if sale_price is not None:
                st.write(f"💰 {sale_price:,}원")
            else:
                st.write("💰 가격 정보 없음")
            
            # 페이지 이동 경로 이모지 반영
            if st.button("자세히 보기", key=f"home_{eng_col}_{product['_id']}"):
                st.session_state['selected_product_id'] = product['_id']
                st.session_state['selected_collection'] = eng_col
                st.switch_page("pages/2_📄_detail.py")
    st.write("---")