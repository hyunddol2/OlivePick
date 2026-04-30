import streamlit as st
import httpx

# 페이지 기본 설정
st.set_page_config(page_title="스킨 제품 가성비 추천", page_icon="🌿", layout="wide")

# ── Qdrant 연결 설정 ──────────────────────────────────────────────────────────
BASE_URL = "https://estranged-simple-unknowing.ngrok-free.dev"
HEADERS = {"ngrok-skip-browser-warning": "true"}


# 구글 드라이브 링크 변환 및 기본 이미지 처리 함수
def get_displayable_image_url(url):
    if not url:
        return "https://via.placeholder.com/150?text=No+Image"

    url_str = str(url).strip()

    if "drive.google.com" in url_str:
        file_id = ""
        if "id=" in url_str:
            file_id = url_str.split("id=")[-1].split("&")[0]
        elif "/d/" in url_str:
            file_id = url_str.split("/d/")[1].split("/")[0]

        if file_id:
            return f"https://drive.google.com/thumbnail?id={file_id}&sz=w600"

    return url_str


@st.cache_resource
def init_connection():
    client = httpx.Client(
        base_url=BASE_URL,
        headers=HEADERS,
        follow_redirects=True,
        timeout=30,
    )
    return client


def get_point(client: httpx.Client, collection: str, point_id):
    r = client.get(f"/collections/{collection}/points/{point_id}")
    r.raise_for_status()
    data = r.json()
    return data.get("result")


def scroll_collection(client: httpx.Client, collection: str, filters: dict = None,
                      limit: int = 20, offset: int = None, order_by: str = None):
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
    return data.get("result", {}).get("points", [])


# ── 카테고리 매핑 (공통 사용) ──────────────────────────────────────────────────
category_map = {
    "스킨/토너": "skintoner_products",
    "에센스/세럼/앰플": "essence_products",
    "크림": "cream_products",
    "로션": "lotion_products",
    "미스트/오일": "mist_products",
}

# ── 메인 화면 ──────────────────────────────────────────────────────────────────
client = init_connection()

st.title("🌿 스킨 제품 가성비 추천 시스템")
st.subheader("가격과 리뷰 데이터를 바탕으로 최적의 제품을 추천해드립니다!")
st.divider()

st.header("🏆 카테고리별 가성비 TOP 5")

for kor_cat, eng_col in category_map.items():
    st.markdown(f"### {kor_cat}")

    top5_products = scroll_collection(
        client,
        collection=eng_col,
        limit=5,
        order_by="final_recommend_score",
    )

    if not top5_products:
        st.info("데이터를 불러오는 중이거나 데이터가 없습니다.")
        continue

    cols = st.columns(5)
    for idx, point in enumerate(top5_products):
        product = point.get("payload", {})
        point_id = point.get("id")

        with cols[idx]:
            with st.container(border=True):
                # 1. 이미지 표시
                raw_url = product.get("olive_image_url")
                display_url = get_displayable_image_url(raw_url)
                st.image(display_url, use_container_width=True)

                # 2. 제품명 표시
                product_name = product.get("olive_name", "제품명 없음")
                st.markdown(f"""
                    <div style="font-size: 15px; font-weight: bold; height: 45px;
                                overflow: hidden; text-overflow: ellipsis;
                                display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
                                line-height: 1.4; margin-bottom: 12px; color: #222;">
                        {product_name}
                    </div>
                """, unsafe_allow_html=True)

                # 3. 가성비 점수 표시
                rec_score = product.get("final_recommend_score", 0)
                st.markdown(f"""
                    <div style="margin-bottom: 8px;">
                        <span style="font-size: 13px; font-weight: bold; color: #666;">📊 가성비 점수</span><br>
                        <span style="background: linear-gradient(to top, #fff59d 45%, transparent 45%);
                                     font-size: 19px; font-weight: 900; color: #000; padding: 0 2px;">
                            {rec_score * 100:.1f}점
                        </span>
                    </div>
                """, unsafe_allow_html=True)

                # 4. 가격 표시
                sale_price = product.get("sale_price", "가격 정보 없음")
                st.markdown(f"""
                    <div style="margin-top: 5px; margin-bottom: 12px;">
                        <b style="color: #000; font-size: 17px;">{sale_price}</b>
                    </div>
                """, unsafe_allow_html=True)

                # 5. 상세 페이지 이동 버튼
                if st.button("자세히 보기", key=f"home_{eng_col}_{point_id}", use_container_width=True):
                    st.session_state["selected_product_id"] = point_id
                    st.session_state["selected_collection"] = eng_col
                    st.switch_page("pages/2_📄_detail.py")

    st.write("---")
