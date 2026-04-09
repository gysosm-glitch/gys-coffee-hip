import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium

# --- 페이지 설정 ---
st.set_page_config(page_title="카페 입지 추천 시스템", layout="wide")
st.title("☕ 카페 입지 추천 시스템 (K-Means 기반)")

# --- 데이터 로드 (캐싱 적용) ---
@st.cache_data
def load_data():
    # 파일이 app.py와 같은 폴더에 있다고 가정하고 상대 경로로 수정
    df_rent = pd.read_csv('임대료.csv', encoding='cp949')
    df_bus = pd.read_csv('버스.csv', encoding='cp949')
    df_subway = pd.read_csv('지하철.csv', encoding='cp949')
    return df_rent, df_bus, df_subway

try:
    df_rent, df_bus, df_subway = load_data()
    st.success("데이터 로딩 성공!")
except Exception as e:
    st.warning(f"실제 데이터를 찾을 수 없어 임시 데이터를 사용합니다. (사유: {e})")
    # 가상 데이터 로직 (테스트용)
    dong_list = ['강남구 역삼1동', '마포구 서교동', '중구 명동', '용산구 이태원1동', '종로구 종로1.2.3.4가동']
    
    # 지도 흔들림을 막기 위해 고정된 위도/경도(서울 주요 좌표)를 임시 데이터에 추가!
    df_rent = pd.DataFrame({
        '행정동': dong_list, 
        '임대료(천원/㎡)': [100, 80, 150, 90, 120],
        '위도': [37.495, 37.555, 37.561, 37.534, 37.570], 
        '경도': [127.033, 126.920, 126.985, 126.994, 126.990]
    })
    df_bus = pd.DataFrame({'행정동': dong_list, '정류장수': [15, 20, 10, 8, 25]})
    df_subway = pd.DataFrame({'행정동': dong_list, '지하철역수': [3, 2, 2, 1, 4]})

# --- 사이드바 UI: 필터 설정 ---
st.sidebar.header("⚙️ 검색 조건 설정")

# 1. 임대료 상~하한선 슬라이더
min_rent = int(df_rent['임대료(천원/㎡)'].min() if not df_rent.empty else 0)
max_rent = int(df_rent['임대료(천원/㎡)'].max() if not df_rent.empty else 200)

rent_range = st.sidebar.slider(
    "임대료 범위 (천원/㎡)",
    min_value=min_rent,
    max_value=max_rent,
    value=(min_rent, max_rent)
)

# 2. 행정동 다중 선택
all_dongs = sorted(df_rent['행정동'].unique().tolist())
selected_dongs = st.sidebar.multiselect(
    "행정동 선택 (다중 선택 가능)",
    options=all_dongs,
    default=all_dongs[:3] if len(all_dongs) >= 3 else all_dongs
)

# --- 메인 화면: 필터링 및 결과 표시 ---
st.subheader("📊 분석 결과")

if selected_dongs:
    # 데이터 필터링
    filtered_rent = df_rent[
        (df_rent['행정동'].isin(selected_dongs)) &
        (df_rent['임대료(천원/㎡)'] >= rent_range[0]) &
        (df_rent['임대료(천원/㎡)'] <= rent_range[1])
    ]

    if not filtered_rent.empty:
        # 예시 로직: 행정동별 건수 집계
        if '정류장수' in df_bus.columns:
            bus_count = df_bus.groupby('행정동')['정류장수'].sum().reset_index()
        else:
             bus_count = df_bus.groupby('행정동').size().reset_index(name='버스정류장수')

        if '지하철역수' in df_subway.columns:
            subway_count = df_subway.groupby('행정동')['지하철역수'].sum().reset_index()
        else:
             subway_count = df_subway.groupby('행정동').size().reset_index(name='지하철역수')

        result_display = pd.merge(filtered_rent, bus_count, on='행정동', how='left').fillna(0)
        result_display = pd.merge(result_display, subway_count, on='행정동', how='left').fillna(0)

        result_display.rename(columns={'정류장수': '버스정류장수'}, inplace=True)

        for col in ['버스정류장수', '지하철역수']:
            if col in result_display.columns:
                 result_display[col] = result_display[col].astype(int)

        # 위도, 경도는 표에서 숨기기 위해 제외하고 출력
        cols_to_show = [c for c in result_display.columns if c not in ['위도', '경도']]
        st.dataframe(result_display[cols_to_show], use_container_width=True)

        # --- 지도 시각화 ---
        st.subheader("🗺️ 선택 지역 교통 인프라 지도")

        m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)

        # 고정된 위경도 데이터를 사용하여 마커 생성 (랜덤 난수 제거)
        for idx, row in result_display.iterrows():
             # 데이터프레임에 있는 실제 위도/경도 사용
             lat = row.get('위도', 37.5665) 
             lng = row.get('경도', 126.9780)

             popup_info = f"""
             <b>{row['행정동']}</b><br>
             임대료: {row['임대료(천원/㎡)']} 천원/㎡<br>
             버스 정류장: {row.get('버스정류장수', 0)}개<br>
             지하철역: {row.get('지하철역수', 0)}개
             """

             folium.Marker(
                 location=[lat, lng],
                 popup=folium.Popup(popup_info, max_width=300),
                 icon=folium.Icon(color="blue", icon="info-sign")
             ).add_to(m)

        st_folium(m, width=800, height=500, returned_objects=[])

    else:
        st.warning("조건에 맞는 데이터가 없습니다. 임대료 범위를 조정해보세요.")
else:
    st.info("사이드바에서 분석할 행정동을 선택해주세요.")
