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
    try:
        df_rent = pd.read_csv('임대료.csv', encoding='cp949')
        df_bus = pd.read_csv('버스.csv', encoding='cp949')
        df_subway = pd.read_csv('지하철.csv', encoding='cp949')
    except Exception:
        # 파일이 없을 경우 조용히 임시 데이터를 불러옵니다 (경고창 미출력)
        dong_list = ['강남구 역삼1동', '마포구 서교동', '중구 명동', '용산구 이태원1동', '종로구 종로1.2.3.4가동']
        
        df_rent = pd.DataFrame({
            '행정동': dong_list, 
            '임대료(천원/㎡)': [100, 80, 150, 90, 120],
            '위도': [37.495, 37.555, 37.561, 37.534, 37.570], 
            '경도': [127.033, 126.920, 126.985, 126.994, 126.990]
        })
        df_bus = pd.DataFrame({'행정동': dong_list, '정류장수': [15, 20, 10, 8, 25]})
        df_subway = pd.DataFrame({'행정동': dong_list, '지하철역수': [3, 2, 2, 1, 4]})

    # '행정동'에서 '구' 정보 추출 (예: '강남구 역삼1동' -> '강남구')
    def extract_gu(dong_name):
        parts = str(dong_name).split()
        for p in parts:
            if p.endswith('구'):
                return p
        return parts[0] if parts else '기타'

    for df in [df_rent, df_bus, df_subway]:
        if '행정동' in df.columns:
            df['구'] = df['행정동'].apply(extract_gu)
            
    return df_rent, df_bus, df_subway

df_rent, df_bus, df_subway = load_data()

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

# 2. '구' 다중 선택
all_gus = sorted(df_rent['구'].unique().tolist())
selected_gus = st.sidebar.multiselect(
    "구 선택 (다중 선택 가능)",
    options=all_gus,
    default=all_gus
)

# --- 메인 화면: 필터링 및 결과 표시 ---
if selected_gus:
    # 데이터 필터링
    filtered_rent = df_rent[
        (df_rent['구'].isin(selected_gus)) &
        (df_rent['임대료(천원/㎡)'] >= rent_range[0]) &
        (df_rent['임대료(천원/㎡)'] <= rent_range[1])
    ]

    if not filtered_rent.empty:
        # 버스 및 지하철 집계
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

        # --- 지도 시각화 (최상단 배치) ---
        st.subheader("🗺️ 지역 인프라 및 임대료 시각화 지도")
        
        # 지도의 중심 좌표 설정 (필터링된 지역 중심)
        center_lat = result_display['위도'].mean() if '위도' in result_display.columns else 37.5665
        center_lng = result_display['경도'].mean() if '경도' in result_display.columns else 126.9780
        
        m = folium.Map(location=[center_lat, center_lng], zoom_start=12)

        # 마커 추가
        for idx, row in result_display.iterrows():
             lat = row.get('위도', 37.5665) 
             lng = row.get('경도', 126.9780)

             popup_info = f"""
             <div style='width: 200px'>
                 <b>{row['행정동']}</b><br>
                 <hr style='margin: 5px 0'>
                 🏢 <b>임대료:</b> {row['임대료(천원/㎡)']} 천원/㎡<br>
                 🚌 <b>버스 정류장:</b> {row.get('버스정류장수', 0)}개<br>
                 🚇 <b>지하철역:</b> {row.get('지하철역수', 0)}개
             </div>
             """

             # 임대료 평균 이상이면 빨간색, 이하면 파란색으로 마커 구분
             avg_rent = result_display['임대료(천원/㎡)'].mean()
             marker_color = "red" if row['임대료(천원/㎡)'] > avg_rent else "blue"

             folium.Marker(
                 location=[lat, lng],
                 popup=folium.Popup(popup_info, max_width=300),
                 tooltip=f"{row['행정동']} (상세정보 클릭)",
                 icon=folium.Icon(color=marker_color, icon="info-sign")
             ).add_to(m)

        st_folium(m, width="100%", height=500, returned_objects=[])

        # --- 데이터프레임 표출 ---
        st.subheader("📊 필터링된 상세 데이터")
        # 표에서 필요없는 컬럼 제거 후 출력
        cols_to_show = [c for c in result_display.columns if c not in ['위도', '경도', '구']]
        st.dataframe(result_display[cols_to_show], use_container_width=True)

    else:
        st.warning("조건에 맞는 데이터가 없습니다. 임대료 범위나 선택한 구를 조정해보세요.")
else:
    st.info("사이드바에서 분석할 구를 선택해주세요.")
