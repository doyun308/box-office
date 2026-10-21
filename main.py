
import html
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

# -------------------------
# 1. 앱 기본 설정
# -------------------------
st.set_page_config(
    page_title="KOBIS 일별 박스오피스",
    page_icon="🎬",
    layout="wide",
)

# 앱을 실행하는 서버의 시간대와 관계없이 한국 날짜를 사용합니다.
korea_today = datetime.now(ZoneInfo("Asia/Seoul")).date()
yesterday = korea_today - timedelta(days=1)

# -------------------------
# 2. 화면 디자인
# -------------------------
st.markdown(
    """
    <style>
    .stApp { background-color: #f5f9ff; }
    .block-container { max-width: 1150px; padding-top: 2rem; }
    h1, h2, h3 { color: #16375c; }
    [data-testid="stMetric"] {
        background: white;
        border: 1px solid #dce9fa;
        border-radius: 15px;
        padding: 18px;
        box-shadow: 0 3px 12px rgba(32, 72, 117, 0.06);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎬 KOBIS 일별 박스오피스 대시보드")
st.caption("영화진흥위원회(KOBIS) 공식 일별 박스오피스 API를 사용합니다.")

# -------------------------
# 3. KOBIS 인증키 읽기
# -------------------------
# Streamlit Cloud의 Settings > Secrets에 KOBIS_KEY를 저장해야 합니다.
try:
    api_key = st.secrets["KOBIS_KEY"]
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("인증키가 비어 있습니다.")
except (KeyError, FileNotFoundError, ValueError, st.errors.StreamlitSecretNotFoundError):
    st.error("🔐 인증키(KOBIS_KEY)를 읽을 수 없습니다.")
    st.info(
        'Streamlit Cloud 앱의 Settings → Secrets에 '
        '`KOBIS_KEY = "발급받은_인증키"` 형식으로 입력한 뒤 저장하세요. '
        '키 이름의 대소문자와 따옴표도 확인하세요.'
    )
    st.stop()

# -------------------------
# 4. 공식 API에서 데이터 받아오기
# -------------------------
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)

@st.cache_data(ttl=600, show_spinner=False)
def fetch_boxoffice(target_date: str, key: str) -> list:
    """날짜(YYYYMMDD)에 해당하는 영화 목록을 받아옵니다.

    API가 정상 응답하지 않으면 화면에 표시할 오류를 발생시킵니다.
    10분 캐시로 반복적인 API 호출을 줄입니다.
    """
    try:
        response = requests.get(
            API_URL,
            params={"key": key, "targetDt": target_date},
            timeout=12,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise RuntimeError("API 서버의 응답 시간이 초과되었습니다.") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError("API 서버 연결 또는 HTTP 요청에 실패했습니다.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("API 응답을 JSON 형식으로 읽을 수 없습니다.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("API 응답 구조가 올바르지 않습니다.")

    # 중요! KOBIS는 인증키 오류도 HTTP 200으로 보낼 수 있습니다.
    if "faultInfo" in payload:
        fault = payload.get("faultInfo") or {}
        detail = (
            fault.get("message", "인증키 또는 요청값을 확인하세요.")
            if isinstance(fault, dict)
            else "인증키 또는 요청값을 확인하세요."
        )
        raise RuntimeError(f"KOBIS API 오류: {detail}")

    result = payload.get("boxOfficeResult")
    if not isinstance(result, dict):
        raise RuntimeError("boxOfficeResult 항목이 없는 응답입니다.")

    movies = result.get("dailyBoxOfficeList")
    if not isinstance(movies, list):
        raise RuntimeError("dailyBoxOfficeList 항목을 찾을 수 없습니다.")
    return movies

# -------------------------
# 5. 날짜 선택 (한국 날짜 기준 어제까지만)
# -------------------------
left, right = st.columns([3, 1])
with left:
    selected_date = st.date_input(
        "📅 조회할 날짜를 선택하세요",
        value=yesterday,
        min_value=date(2004, 1, 1),
        max_value=yesterday,
        format="YYYY/MM/DD",
    )
with right:
    st.write("")
    st.write("")
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        fetch_boxoffice.clear()
        st.rerun()

st.caption(
    f"한국 시간 기준 오늘: {korea_today:%Y-%m-%d} · "
    f"조회 가능: {yesterday:%Y-%m-%d}까지"
)

if selected_date > yesterday:
    st.warning("오늘 데이터는 아직 집계 전이므로 어제까지의 날짜만 선택해 주세요.")
    st.stop()

with st.spinner("KOBIS 박스오피스 데이터를 불러오는 중입니다..."):
    try:
        raw_movies = fetch_boxoffice(
            selected_date.strftime("%Y%m%d"),
            api_key
        )
    except RuntimeError as exc:
        st.error(f"⚠️ 박스오피스를 불러오지 못했습니다. {exc}")
        st.info(
            "확인할 사항: ① Streamlit Secrets의 KOBIS_KEY가 올바른지 "
            "② KOBIS 인증키가 활성화되어 있는지 "
            "③ 인터넷 연결과 KOBIS 서버 상태가 정상인지 "
            "④ 조회 날짜가 지원되는 날짜인지 확인하세요. "
            "문제가 일시적이라면 잠시 후 '데이터 새로고침'을 눌러 다시 시도하세요."
        )
        st.stop()

if not raw_movies:
    st.warning("📭 그날은 아직 집계 전입니다.")
    st.info(
        "조회한 날짜를 확인하거나 다른 날짜를 선택해 보세요. "
        "집계가 완료되지 않았을 수도 있습니다."
    )
    st.stop()

# -------------------------
# 6. API의 문자열 숫자를 정수로 변환
# -------------------------
def to_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0

rows = []
for movie in raw_movies:
    if not isinstance(movie, dict):
        continue

    rank = to_int(movie.get("rank"))
    change = to_int(movie.get("rankInten"))
    audience_total = to_int(movie.get("audiAcc"))

    # 전날 대비 순위가 상승하면 빨간 ↑, 하락하면 파란 ↓입니다.
    if change > 0:
        trend = f"🔴 ↑ {change}"
    elif change < 0:
        trend = f"🔵 ↓ {abs(change)}"
    else:
        trend = "➖ 0"

    name = str(movie.get("movieNm") or "제목 없음")
    if audience_total > 1_000_000:
        name += " 🏆"

    rows.append({
        "순위": rank,
        "순위 변동": trend,
        "영화명": name,
        "개봉일": str(movie.get("openDt") or "미정"),
        "관객수": to_int(movie.get("audiCnt")),
        "누적관객": audience_total,
        "스크린수": to_int(movie.get("scrnCnt")),
        "상영횟수": to_int(movie.get("showCnt")),
    })

if not rows:
    st.warning("📭 그날은 아직 집계 전입니다.")
    st.stop()

df = pd.DataFrame(rows).sort_values("순위").reset_index(drop=True)
number_of_films = len(df)
daily_audience = int(df["관객수"].sum())

st.divider()
st.subheader(
    f"🏅 {selected_date:%Y년 %m월 %d일} 박스오피스 1위"
)

# -------------------------
# 7. 1위 영화 지표 카드 3개
# -------------------------
first = df.iloc[0]
st.markdown(f"### {html.escape(str(first['영화명']))}")

a, b, c = st.columns(3)
a.metric("🎟️ 일일 관객수", f"{first['관객수']:,}명")
b.metric("👥 누적 관객수", f"{first['누적관객']:,}명")
c.metric("🎥 스크린수", f"{first['스크린수']:,}개")

# -------------------------
# 8. 전체 순위와 간단한 검색 기능
# -------------------------
st.subheader("📋 일별 박스오피스 순위표")
st.caption(
    "🔴 ↑ 순위 상승 · 🔵 ↓ 순위 하락 · "
    "➖ 변화 없음 · 🏆 누적 관객 100만 명 초과"
)

search_term = st.text_input(
    "🔎 영화명 검색",
    placeholder="찾을 영화의 이름을 입력하세요"
)

visible = df[
    df["영화명"].str.contains(
        search_term,
        case=False,
        regex=False,
        na=False
    )
]

if visible.empty:
    st.info("검색된 영화가 없습니다. 다른 검색어를 입력해 보세요.")
else:
    st.dataframe(
        visible[
            ["순위", "순위 변동", "영화명", "개봉일",
             "관객수", "누적관객", "스크린수"]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "순위": st.column_config.NumberColumn(
                format="%d위", width="small"
            ),
            "순위 변동": st.column_config.TextColumn(
                width="small"
            ),
            "영화명": st.column_config.TextColumn(
                width="large"
            ),
            "관객수": st.column_config.NumberColumn(
                format="localized"
            ),
            "누적관객": st.column_config.NumberColumn(
                format="localized"
            ),
            "스크린수": st.column_config.NumberColumn(
                format="localized"
            ),
        },
    )

# -------------------------
# 9. 상위 5편 관객수 막대그래프
# -------------------------
st.subheader("📊 관객수 TOP 5")

top5 = df.sort_values(
    "관객수",
    ascending=False
).head(5).copy()

# 같은 이름의 영화가 있을 경우에도 그래프에서 구별되도록 순위를 함께 표시합니다.
top5["영화"] = (
    top5["순위"].astype(str)
    + "위 · "
    + top5["영화명"]
)

st.bar_chart(
    top5.set_index("영화")[["관객수"]],
    horizontal=True,
    color="#328fe6"
)

# -------------------------
# 10. 추가 기능: 관객 점유율 분석
# -------------------------
st.subheader("📈 관객 데이터 분석")

x, y, z = st.columns(3)
x.metric("TOP 10 합계 관객수", f"{daily_audience:,}명")
y.metric("집계된 영화 수", f"{number_of_films}편")

share = (
    first["관객수"] / daily_audience * 100
    if daily_audience
    else 0
)
z.metric("1위 관객 점유율", f"{share:.1f}%")

st.caption(
    "※ 점유율과 합계는 API에 제공된 순위권 영화만을 기준으로 계산하며, "
    "전체 극장 관객수와 다를 수 있습니다."
)

# -------------------------
# 11. 추가 기능: CSV 다운로드
# -------------------------
st.download_button(
    "📥 이 날짜의 박스오피스 CSV 다운로드",
    data=df.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"KOBIS_boxoffice_{selected_date:%Y%m%d}.csv",
    mime="text/csv",
    use_container_width=True,
)

st.caption(
    "자료 출처: 영화진흥위원회 영화관입장권 통합전산망(KOBIS) "
    "· 일별 박스오피스 API"
)

