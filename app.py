import streamlit as st
import httpx
import re

# 페이지 기본 설정
st.set_page_config(page_title="스킨 제품 가성비 추천", page_icon="🌿", layout="wide")

# ── Qdrant 연결 설정 ──────────────────────────────────────────────
BASE_URL = "https://estranged-simple-unknowing.ngrok-free.dev"
HEADERS = {"ngrok-skip-browser-warning": "true"}

# 구글 드라이브 링크 변환 및 기본 이미지 처리 함수
def get_displayable_image_url(url):
    url_str = str(url).strip()
    if not url or url_str in ["", "0", "null", "None", "nan"]:
        return "no_image.png"

    if "drive.google.com" in url_str:
        match = re.search(r'(?:id=|/file/d/)([a-zA-Z0-9_-]+)', url_str)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/thumbnail?id={file_id}&sz=w400"

    if not url_str.startswith("http"):
        return "no_image.png"

    return url_str


# ── Qdrant 클라이언트 (httpx 기반) ───────────────────────────────
@st.cache_resource
def init_connection():
    """
    Qdrant REST API를 감싸는 간단한 클라이언트 객체를 반환합니다.
    실제 qdrant-client 라이브러리 대신 httpx를 사용하는 팀 환경에 맞춥니다.
    """
    client = httpx.Client(
        base_url=BASE_URL,
        headers=HEADERS,
        follow_redirects=True,
        timeout=30,
    )
    return client


def scroll_collection(client: httpx.Client, collection: str, filters: dict = None,
                       limit: int = 20, offset: int = None, order_by: str = None):
    """
    Qdrant /collections/{name}/points/scroll 엔드포인트를 호출합니다.

    Parameters
    ----------
    filters  : Qdrant filter dict (must 조건 등)
    limit    : 반환할 최대 포인트 수
    offset   : 페이지네이션용 point id (이전 scroll 결과의 next_page_offset)
    order_by : 정렬 기준 필드명 (value_score 등), 내림차순 고정
    """
    body = {
        "limit": limit,
        "with_payload": True,
        "with_vector": False,
    }
    if filters:
        body["filter"] = filters
    if offset:
        body["offset"] = offset
    if order_by:
        body["order_by"] = {"key": order_by, "direction": "desc"}

    r = client.post(f"/collections/{collection}/points/scroll", json=body)
    r.raise_for_status()
    data = r.json()
    # result: {"points": [...], "next_page_offset": ...}
    return data.get("result", {}).get("points", [])

def get_point(client: httpx.Client, collection: str, point_id):
    """
    단일 포인트를 ID로 조회합니다. 
    404 에러 방지를 위해 points/scroll 또는 POST 조회를 사용하는 것이 안전합니다.
    """
    # ID가 숫자든 문자열이든 처리할 수 있도록 리스트로 감싸서 POST 요청
    body = {
        "ids": [point_id],
        "with_payload": True,
        "with_vector": False
    }
    r = client.post(f"/collections/{collection}/points", json=body)
    r.raise_for_status()
    data = r.json()
    
    # result 리스트의 첫 번째 항목 반환
    results = data.get("result", [])
    return results[0] if results else None


# ── 카테고리 매핑 ─────────────────────────────────────────────────
# key: 화면 표시명 / value: Qdrant 컬렉션 이름
category_map = {
    "스킨/토너": "skintoner_products",
    "에센스/세럼/앰플": "essence_products",
    "크림": "cream_products",
    "로션": "lotion_products",
    "미스트/오일": "mist_products",
}

# ── 메인 화면 ─────────────────────────────────────────────────────
client = init_connection()

st.title("🌿 스킨 제품 가성비 추천 시스템")
st.subheader("가격과 리뷰 데이터를 바탕으로 최적의 제품을 추천해드립니다!")
st.divider()

st.header("🏆 카테고리별 가성비 TOP 5")

for kor_cat, eng_col in category_map.items():
    st.markdown(f"### {kor_cat}")

    # value_score 내림차순으로 상위 5개 조회
    top5_products = scroll_collection(
        client,
        collection=eng_col,
        limit=5,
        order_by="final_recommend_score", # value_score -> final_recommend_score
    )

    if not top5_products:
        st.info("데이터를 불러오는 중이거나 데이터가 없습니다.")
        continue

    cols = st.columns(5)
    for idx, point in enumerate(top5_products):
        # 1. 포인트에서 데이터(payload)와 ID 추출
        product = point.get("payload", {})
        point_id = point.get("id")  # 버튼 클릭 시 제품을 식별하기 위해 필수입니다.

        with cols[idx]:
            # 2. 이미지 표시 (DB 필드명: olive_image_url)
            raw_url = product.get("olive_image_url")
            display_url = get_displayable_image_url(raw_url)
            st.image(display_url, use_container_width=True)

            # 3. 제품명 표시 (DB 필드명: olive_name)
            product_name = product.get("olive_name", "제품명 없음")
            st.write(f"**{product_name[:15]}...**")

            # 4. 가격 표시 처리
            # DB의 sale_price가 "43,000원" 형태의 문자열이므로, 
            # 숫자로 변환하지 않고 그대로 출력하는 것이 가장 안전합니다.
            sale_price = product.get("sale_price")
            if sale_price:
                st.write(f"💰 {sale_price}")
            else:
                st.write("💰 가격 정보 없음")

            # 5. 상세 페이지 이동 버튼
            # key 값에 point_id를 포함시켜야 각 버튼이 서로 충돌하지 않습니다.
            if st.button("자세히 보기", key=f"home_{eng_col}_{point_id}"):
                st.session_state["selected_product_id"] = point_id
                st.session_state["selected_collection"] = eng_col
                st.switch_page("pages/2_📄_detail.py")

    st.write("---") # 카테고리 섹션 간 구분선
