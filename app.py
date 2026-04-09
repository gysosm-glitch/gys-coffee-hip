import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px

# --- 페이지 설정 ---
st.set_page_config(page_title="카페 입지 추천 시스템", layout="wide")
st.title("☕ 카페 입지 추천 시스템 (K-Means 기반)")

# --- 데이터 로드 (캐싱 적용) ---
@st.cache_data
def load_data():
    try:
        df_rent = pd.read_csv('임대료.csv', encoding='utf-8-sig')
        df_bus = pd.read_csv('버스.csv', encoding='utf-8-sig')
        # 지하철 파일의 인코딩을 utf-8-sig로 수정
        df_subway = pd.read_csv('지하철.csv', encoding='utf-8-sig')
        df_cluster = pd.read_csv('클러스터_결과.csv', encoding='utf-8-sig')
    except Exception as e:
        st.error(f"데이터 로드 중 오류가 발생했습니다: {e}")
        # 파일이 없을 경우 임시 데이터 생성
        dong_list = ['강남구 역삼1동', '마포구 서교동', '중구 명동', '용산구 이태원1동', '종로구 종로1.2.3.4가동']
        df_rent = pd.DataFrame({
            '행정동': dong_list,
            '임대료(천원/㎡)': [100, 80, 150, 90, 120],
            '위도': [37.495, 37.555, 37.561, 37.534, 37.570],
            '경도': [127.033, 126.920, 126.985, 126.994, 126.990]
        })
        df_bus = pd.DataFrame({'행정동': dong_list, '정류장수': [15, 20, 10, 8, 25], '위도': [37.496, 37.556, 37.562, 37.535, 37.571], '경도': [127.034, 126.921, 126.986, 126.995, 126.991]})
        df_subway = pd.DataFrame({'행정동': dong_list, '지하철역수': [3, 2, 2, 1, 4], '위도': [37.494, 37.554, 37.560, 37.533, 37.569], '경도': [127.032, 126.919, 126.984, 126.993, 126.989]})
        df_cluster = pd.DataFrame({
            '행정동': dong_list,
            '수요_점수': [80, 75, 90, 60, 70],
            '구매력_점수': [90, 80, 95, 70, 75],
            '리스크_점수': [50, 60, 40, 30, 55],
            '종합_점수': [85.5, 78.2, 92.1, 55.4, 68.9],
            '클러스터_세분화': [2, 1, 2, 0, 1]
        })

    # '행정동'에서 '구' 정보 추출
    def extract_gu(dong_name):
        parts = str(dong_name).split()
        for p in parts:
            if p.endswith('구'):
                return p
        return parts[0] if parts else '기타'

    for df in [df_rent, df_bus, df_subway, df_cluster]:
        if '행정동' in df.columns:
            df['구'] = df['행정동'].apply(extract_gu)

    return df_rent, df_bus, df_subway, df_cluster

df_rent, df_bus, df_subway, df_cluster = load_data()

# --- 사이드바 UI: 필터 설정 ---
st.sidebar.header("⚙️ 검색 조건 설정")

min_rent = int(df_rent['임대료(천원/㎡)'].min() if not df_rent.empty else 0)
max_rent = int(df_rent['임대료(천원/㎡)'].max() if not df_rent.empty else 200)

rent_range = st.sidebar.slider(
    "임대료 범위 (천원/㎡)",
    min_value=min_rent,
    max_value=max_rent,
    value=(min_rent, max_rent)
)

all_gus = sorted(df_rent['구'].unique().tolist())
selected_gus = st.sidebar.multiselect(
    "구 선택 (다중 선택 가능)",
    options=all_gus,
    default=all_gus
)

# --- 메인 화면: 필터링 및 결과 표시 ---
if selected_gus:
    filtered_rent = df_rent[
        (df_rent['구'].isin(selected_gus)) &
        (df_rent['임대료(천원/㎡)'] >= rent_range[0]) &
        (df_rent['임대료(천원/㎡)'] <= rent_range[1])
    ]

    if not filtered_rent.empty:
        # 집계 데이터 병합
        bus_agg = df_bus.groupby('행정동').size().reset_index(name='버스정류장수') if '정류장수' not in df_bus.columns else df_bus.groupby('행정동')['정류장수'].sum().reset_index()
        subway_agg = df_subway.groupby('행정동').size().reset_index(name='지하철역수') if '지하철역수' not in df_subway.columns else df_subway.groupby('행정동')['지하철역수'].sum().reset_index()

        result_display = pd.merge(filtered_rent, bus_agg, on='행정동', how='left').fillna(0)
        result_display = pd.merge(result_display, subway_agg, on='행정동', how='left').fillna(0)

        # 클러스터링 데이터 병합 (불필요한 구 컬럼 제외)
        if not df_cluster.empty:
            result_display = pd.merge(result_display, df_cluster.drop(columns=['구'], errors='ignore'), on='행정동', how='left')

        result_display.rename(columns={'정류장수': '버스정류장수'}, inplace=True)

        # --- 지도 시각화 ---
        st.subheader("🗺️ 지역 인프라 및 상권 분석 시각화 지도")
        center_lat = result_display['위도'].mean() if '위도' in result_display.columns else 37.5665
        center_lng = result_display['경도'].mean() if '경도' in result_display.columns else 126.9780

        m = folium.Map(location=[center_lat, center_lng], zoom_start=12)

        # 1. 상권 마커 (빨간색/파란색)
        for idx, row in result_display.iterrows():
            lat = row.get('위도', 37.5665)
            lng = row.get('경도', 126.9780)
            avg_rent = result_display['임대료(천원/㎡)'].mean()
            marker_color = "red" if row.get('임대료(천원/㎡)', 0) > avg_rent else "blue"

            # 군집 점수 안전하게 가져오기
            total_score = row.get('종합_점수', 'N/A')
            cluster_id = row.get('클러스터_세분화', row.get('클러스터', 'N/A'))

            popup_info = f"""<div style='width: 250px'>
            <b>{row['행정동']} (군집: {cluster_id})</b><br>
            ⭐ 종합 점수: {total_score}<br>
            🏢 임대료: {row.get('임대료(천원/㎡)', 0)} 천원/㎡<br>
            🚌 버스: {int(row.get('버스정류장수', 0))}개 | 🚇 지하철: {int(row.get('지하철역수', 0))}개
            </div>"""

            folium.Marker(
                location=[lat, lng],
                popup=folium.Popup(popup_info, max_width=300),
                tooltip=f"{row['행정동']} 상권 (종합 점수: {total_score})",
                icon=folium.Icon(color=marker_color, icon="info-sign")
            ).add_to(m)

        # 2. 버스 정류장 마커 (초록색)
        if '위도' in df_bus.columns and '경도' in df_bus.columns:
            filtered_bus = df_bus[df_bus['구'].isin(selected_gus)]
            for _, row in filtered_bus.iterrows():
                folium.CircleMarker(
                    location=[row['위도'], row['경도']],
                    radius=3, color='green', fill=True,
                    tooltip="버스 정류장"
                ).add_to(m)

        # 3. 지하철역 마커 (보라색)
        if '위도' in df_subway.columns and '경도' in df_subway.columns:
            filtered_subway = df_subway[df_subway['구'].isin(selected_gus)]
            for _, row in filtered_subway.iterrows():
                folium.Marker(
                    location=[row['위도'], row['경도']],
                    icon=folium.Icon(color="purple", icon="train", prefix='fa'),
                    tooltip=f"{row.get('역사명', '지하철역')}"
                ).add_to(m)

        st_folium(m, width="100%", height=500, returned_objects=[])

        # --- 데이터프레임 표출 ---
        st.subheader("📊 상권 분석 및 필터링된 상세 데이터")
        cols_to_show = [c for c in result_display.columns if c not in ['위도', '경도', '구']]
        # 데이터프레임에서 점수를 내림차순으로 정렬하여 보여줌 (종합 점수가 있는 경우)
        if '종합_점수' in result_display.columns:
            result_display = result_display.sort_values(by='종합_점수', ascending=False)

        st.dataframe(result_display[cols_to_show], use_container_width=True)

        # --- Plotly 시각화 추가 ---
        if '수요_점수' in result_display.columns:
            st.subheader("📈 상권 지수 비교 차트 (상위 10개)")
            chart_data = result_display.head(10).melt(
                id_vars=['행정동'],
                value_vars=['수요_점수', '구매력_점수', '리스크_점수'],
                var_name='지수',
                value_name='점수'
            )
            fig = px.bar(
                chart_data,
                x='행정동',
                y='점수',
                color='지수',
                barmode='group',
                title="선택 구역 내 상위 행정동 지수 비교",
                text_auto='.1f'
            )
            fig.update_layout(xaxis_title="행정동", yaxis_title="점수 (100점 만점)")
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning("조건에 맞는 데이터가 없습니다. 임대료 범위나 선택한 구를 조정해보세요.")
else:
    st.info("사이드바에서 분석할 구를 선택해주세요.")
