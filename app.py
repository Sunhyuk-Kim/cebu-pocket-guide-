# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# app.py — 세부 여행 위치 기반 추천 MVP (단일 파일)
# 실행: streamlit run app.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import streamlit as st
import requests
import math
import os
from dotenv import load_dotenv

load_dotenv()

# ─── 설정 ───────────────────────────────────────────────

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

HOTELS = {
    "워터프론트 세부시티 호텔": (10.3119, 123.8916),
    "뫼벤픽 막탄 리조트": (10.2655, 123.9633),
}

CATEGORIES = {
    "💆 마사지/스파": "spa|massage",
    "🍽️ 맛집": "restaurant",
    "☕ 카페": "cafe",
    "🏄 액티비티": "tourist_attraction",
    "🪩 클럽": "night_club",
    "🍺 바/펍": "bar",
    "🎤 KTV/노래방": "karaoke",
}

# 카테고리별 1인 평균 비용 (PHP 범위)
COST_TABLE = {
    "💆 마사지/스파": (300, 800, "1시간 기준, 타이/오일 마사지"),
    "🍽️ 맛집": (200, 1500, "로컬 식당~레스토랑 1인"),
    "☕ 카페": (100, 300, "커피+디저트 1인"),
    "🏄 액티비티": (800, 5000, "스노클링~아일랜드호핑"),
    "🪩 클럽": (500, 2000, "입장료+음료 2~3잔"),
    "🍺 바/펍": (200, 800, "맥주/칵테일 2~3잔"),
    "🎤 KTV/노래방": (300, 1500, "1~2시간 룸+음료"),
}


# ─── 유틸 ───────────────────────────────────────────────

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 사이 거리(km)"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─── Google Places 검색 ────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def search_places(lat: float, lng: float, keyword: str, radius: int) -> list:
    """Google Places Nearby Search API 호출 (캐시 1시간)"""
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "keyword": keyword,
        "language": "ko",
        "key": GOOGLE_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            error_msg = data.get("error_message", data.get("status", "알 수 없는 오류"))
            st.error(f"🚨 Google API 오류: {error_msg}")
            return []

        results = []
        for p in data.get("results", []):
            loc = p.get("geometry", {}).get("location", {})
            p_lat = loc.get("lat", 0)
            p_lng = loc.get("lng", 0)

            # 영업중 여부
            opening = p.get("opening_hours")
            if opening is not None:
                is_open = opening.get("open_now")
            else:
                is_open = None

            results.append({
                "name": p.get("name", "이름 없음"),
                "rating": p.get("rating", 0),
                "reviews": p.get("user_ratings_total", 0),
                "lat": p_lat,
                "lng": p_lng,
                "address": p.get("vicinity", ""),
                "is_open": is_open,
                "place_id": p.get("place_id", ""),
                "dist_km": haversine(lat, lng, p_lat, p_lng),
            })

        return results

    except requests.exceptions.Timeout:
        st.error("🚨 API 요청 시간 초과 — 잠시 후 다시 시도해 주세요.")
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"🚨 네트워크 오류: {e}")
        return []
    except Exception as e:
        st.error(f"🚨 예상치 못한 오류: {e}")
        return []


# ─── 페이지 설정 ────────────────────────────────────────

st.set_page_config(page_title="세부 여행 추천", page_icon="🏝️", layout="wide")
st.title("🏝️ 세부 여행 — 위치 기반 장소 추천")

if not GOOGLE_API_KEY:
    st.error("⚠️ `.env` 파일에 `GOOGLE_API_KEY`를 설정해 주세요.")
    st.code("GOOGLE_API_KEY=AIzaSy__your_key_here__", language="bash")
    st.stop()


# ─── 사이드바 ───────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ 검색 설정")

    hotel = st.selectbox("🏨 숙소 선택", list(HOTELS.keys()))
    base_lat, base_lng = HOTELS[hotel]

    category = st.selectbox("🏷️ 카테고리", list(CATEGORIES.keys()))
    keyword = CATEGORIES[category]

    radius_km = st.radio("📏 검색 반경", [1, 3, 5], index=1, horizontal=True)
    radius_m = radius_km * 1000

    st.divider()
    st.header("💱 환율 설정")
    exchange_rate = st.number_input(
        "1페소(₱) = 원(₩)",
        min_value=1.0, max_value=100.0,
        value=24.0, step=0.5,
        help="현재 PHP→KRW 환율을 직접 입력하세요",
    )

    st.divider()
    # 비용 안내
    cost_min, cost_max, cost_note = COST_TABLE[category]
    st.subheader(f"💰 {category} 예상 비용")
    st.markdown(f"""
    | 항목 | 금액 |
    |------|------|
    | **페소** | ₱{cost_min:,} ~ ₱{cost_max:,} |
    | **원화** | ₩{int(cost_min * exchange_rate):,} ~ ₩{int(cost_max * exchange_rate):,} |
    | **기준** | {cost_note} |
    """)


# ─── 메인: 검색 & 결과 ─────────────────────────────────

st.caption(f"📍 기준: **{hotel}** ({base_lat:.4f}, {base_lng:.4f}) · "
           f"반경 **{radius_km}km** · 평점 **4.0+** 필터")

with st.spinner("🔍 주변 장소를 검색하고 있습니다..."):
    raw = search_places(base_lat, base_lng, keyword, radius_m)

if not raw:
    st.warning("😢 검색 결과가 없습니다. 반경을 넓히거나 카테고리를 변경해 보세요.")
    st.stop()

# 필터: 평점 4.0 이상 + 거리순 정렬 → Top 10
filtered = [p for p in raw if p["rating"] >= 4.0]
filtered.sort(key=lambda x: x["dist_km"])
top10 = filtered[:10]

if not top10:
    st.warning("😢 평점 4.0 이상인 장소가 없습니다. 반경을 넓혀 보세요.")
    st.stop()

st.success(f"✅ 평점 4.0 이상 **{len(top10)}곳** 발견 (전체 {len(raw)}곳 중)")

# ─── 결과 카드 렌더링 ──────────────────────────────────

for i, place in enumerate(top10, 1):
    maps_url = f"https://www.google.com/maps/place/?q=place_id:{place['place_id']}"

    # 영업 상태
    if place["is_open"] is True:
        status = "🟢 영업중"
    elif place["is_open"] is False:
        status = "🔴 영업 종료"
    else:
        status = "⚪ 정보 없음"

    with st.container(border=True):
        cols = st.columns([0.5, 3, 1.2, 1.2, 1.2, 1.5])

        with cols[0]:
            st.markdown(f"### {i}")

        with cols[1]:
            st.markdown(f"**{place['name']}**")
            st.caption(place["address"])

        with cols[2]:
            st.metric("평점", f"⭐ {place['rating']}")

        with cols[3]:
            st.metric("리뷰", f"{place['reviews']:,}개")

        with cols[4]:
            st.metric("거리", f"{place['dist_km']:.1f}km")

        with cols[5]:
            st.markdown(f"**{status}**")
            st.link_button("🗺️ 구글맵", maps_url, use_container_width=True)


# ─── 하단: 비용 요약 ───────────────────────────────────

st.divider()
st.subheader(f"💰 {category} 예상 비용 요약")

cost_min, cost_max, cost_note = COST_TABLE[category]

c1, c2, c3 = st.columns(3)
c1.metric("최소 (₱)", f"₱{cost_min:,}", f"₩{int(cost_min * exchange_rate):,}")
c2.metric("최대 (₱)", f"₱{cost_max:,}", f"₩{int(cost_max * exchange_rate):,}")
c3.metric("환율 기준", f"₱1 = ₩{exchange_rate:.1f}", cost_note)

# Grab 교통비 참고
if top10:
    avg_dist = sum(p["dist_km"] for p in top10) / len(top10)
    grab_est = max(60, 40 + avg_dist * 15)
    st.info(
        f"🚕 **Grab 참고**: 평균 거리 {avg_dist:.1f}km 기준 "
        f"약 ₱{grab_est:,.0f} (≈₩{int(grab_est * exchange_rate):,})"
    )


# ─── 푸터 ──────────────────────────────────────────────

st.divider()
st.caption("💡 데이터: Google Places API · 비용은 2025년 현지 평균 기준 참고값입니다 · "
           "환율은 사이드바에서 직접 조정하세요")
