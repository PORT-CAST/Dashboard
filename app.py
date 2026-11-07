"""PORTCAST 부산항 의사결정지원 대시보드 기본 틀 (내용 없음).

실행: streamlit run app.py
사진: assets/containership.png를 넣으면 그 사진을 씁니다. 없으면 인터넷 주소의 사진을 불러옵니다.
색상: .streamlit/config.toml과 ui.py의 색 사전
내용 넣기: 각 화면 함수의 ui.빈자리(...)를 그래프나 표 코드로 바꿉니다.
판정 기준: criteria.py의 주의, 위험 값을 바꿉니다.
"""
import streamlit as st

import ui
from terminal_map import 터미널지도
from criteria import 기상변수, 종합판정

st.set_page_config(page_title="PORTCAST | 스마트항만 의사결정지원", page_icon="🚢", layout="wide")
ui.스타일적용()

북항 = ["BPTC_G", "BPT_S"]
신항 = ["BNCT", "HPNT", "PNC", "PNIT"]
기간들 = ["전체", "2021", "2022", "2023", "2024"]
팀이름 = "PORTCAST"
프로젝트이름 = "스마트항만 의사결정지원 프로젝트"
프로젝트소개 = ("부산항의 기상·해양 데이터와 풀컨테이너선 운항 데이터를 결합해, 환경 조건에 따른 체류시간과 "
          "터미널별 운영 변화를 분석하고 운영 위험을 예측합니다")
화면들 = {
    "전체 요약": ("space_dashboard", 프로젝트소개),
    "KPI 1": ("air", "기상 관련 체류시간 증가량"),
    "KPI 2": ("warning", "기상특보 발효 시 체류시간 증가량"),
    "기상 상황 점검": ("tune", "기상값을 조정해 안정, 주의, 위험을 확인합니다"),
}


def 항만선택(고른쪽: str, 다른쪽: str) -> None:
    """북항과 신항 중 한쪽 터미널만 선택되도록 다른 쪽을 비운다."""
    if st.session_state.get(고른쪽):
        st.session_state[다른쪽] = None


def 지도선택() -> None:
    """지도에서 누른 터미널을 위쪽 선택 막대와 맞춘다. 같은 칸을 다시 누르면 해제한다."""
    고른값 = st.session_state["터미널지도"].get("pick")
    if not 고른값:
        return
    현재 = st.session_state.get("북항선택") or st.session_state.get("신항선택")
    st.session_state["북항선택"] = None
    st.session_state["신항선택"] = None
    if 고른값 != 현재:
        st.session_state["북항선택" if 고른값 in 북항 else "신항선택"] = 고른값


with st.sidebar:
    ui.브랜드(팀이름, 프로젝트이름)
    st.markdown('<div class="navlabel">메뉴</div>', unsafe_allow_html=True)
    st.session_state.setdefault("화면", "전체 요약")
    with st.container(key="nav"):
        for 이름, (모양, _) in 화면들.items():
            st.button(이름, icon=f":material/{모양}:", width="stretch", key=f"메뉴_{이름}",
                      type="primary" if st.session_state["화면"] == 이름 else "secondary",
                      on_click=st.session_state.__setitem__, args=("화면", 이름))
    ui.상태표시("자료 연결 전")

제목 = st.session_state["화면"]
설명 = 화면들[제목][1]
머리자리 = st.container()

기간표시 = 제목 != "기상 상황 점검"
with st.container(key="filter", horizontal=True,
                  horizontal_alignment="distribute" if 기간표시 else "right"):
    if 기간표시:
        st.segmented_control("기간", 기간들, default="전체", key="기간선택")
    with st.container(horizontal=True, width="content", gap="medium"):
        st.segmented_control("북항", 북항, key="북항선택", on_change=항만선택, args=("북항선택", "신항선택"))
        st.segmented_control("신항", 신항, key="신항선택", on_change=항만선택, args=("신항선택", "북항선택"))

터미널 = st.session_state.get("북항선택") or st.session_state.get("신항선택")
기간값 = st.session_state.get("기간선택") or "전체"
with 머리자리:
    기간글 = "2021-2024년" if 기간값 == "전체" else f"{기간값}년"
    ui.머리글(f"🚢 {팀이름}" if 제목 == "전체 요약" else 제목, 설명, 터미널 or "전체 터미널", None if 제목 == "기상 상황 점검" else 기간글)


def 지도칸() -> None:
    with ui.패널("map", "터미널 위치", f"보고 있는 터미널: {터미널 or '전체'}"):
        터미널지도(data={"sel": 터미널}, key="터미널지도", on_pick_change=지도선택)
        ui.지도설명()


def 전체요약화면() -> None:
    좌, 우 = st.columns([1.3, 1], gap="small")
    with 좌:
        ui.지표줄([{"이름": "지표 1", "종류": "main", "아이콘": "schedule"},
                 {"이름": "지표 2", "종류": "base", "아이콘": "directions_boat"}])
        ui.지표줄([{"이름": "지표 3", "아이콘": "air"},
                 {"이름": "지표 4", "종류": "alert", "아이콘": "warning"}])
    with 우:
        지도칸()


# AI 요약칸은 모든 화면에서 여기 한 번만 그린다 (화면 함수 안에서 또 부르면 key 중복 오류)
ui.AI요약칸({
    "화면": 제목,
    "기간": 기간값,
    "터미널": 터미널 or "전체 터미널",
    "분석결과": [],  # 실제 집계 결과로 교체: 집계_df.to_dict(orient="records")
})


def KPI1화면() -> None:
    좌, 우 = st.columns([1.3, 1], gap="small")
    with 좌:
        ui.지표줄([{"이름": "지표 1", "종류": "main", "아이콘": "schedule"}])
        ui.지표줄([{"이름": "지표 2", "아이콘": "air"},
                 {"이름": "지표 3", "종류": "base", "아이콘": "waves"}])
    with 우:
        지도칸()
    좌, 우 = st.columns([2, 1], gap="small")
    with 좌:
        with ui.패널("k1a", "그래프 1"):
            ui.빈자리(320)
    with 우:
        with ui.패널("k1b", "그래프 2"):
            ui.빈자리(320)
    좌, 우 = st.columns([1, 2], gap="small")
    with 좌:
        with ui.패널("k1c", "그래프 3"):
            ui.빈자리(260)
    with 우:
        with ui.패널("k1d", "표 1"):
            ui.빈자리(260, "표")


def KPI2화면() -> None:
    좌, 우 = st.columns([1.3, 1], gap="small")
    with 좌:
        ui.지표줄([{"이름": "지표 1", "종류": "main", "아이콘": "schedule"},
                 {"이름": "지표 2", "종류": "alert", "아이콘": "warning"}])
        ui.지표줄([{"이름": "지표 3", "종류": "base", "아이콘": "directions_boat"},
                 {"이름": "지표 4", "아이콘": "timer"}])
    with 우:
        지도칸()
    좌, 우 = st.columns([2, 1], gap="small")
    with 좌:
        with ui.패널("k2a", "그래프 1"):
            ui.빈자리(320)
    with 우:
        with ui.패널("k2b", "그래프 2"):
            ui.빈자리(320)
    with ui.패널("k2c", "표 1"):
        ui.빈자리(220, "표")


def 기본값으로() -> None:
    for 이름, 기준 in 기상변수.items():
        st.session_state[f"슬라이더_{이름}"] = 기준["기본"]


def 기상점검화면() -> None:
    좌, 우 = st.columns([1, 1.15], gap="small")
    with 좌:
        with ui.패널("cond", "기상 조건", "슬라이더로 값을 바꿔 보세요"):
            값들 = {}
            for 이름, 기준 in 기상변수.items():
                st.session_state.setdefault(f"슬라이더_{이름}", 기준["기본"])
                값들[이름] = st.slider(
                    f":material/{기준['아이콘']}: {이름} ({기준['단위']})",
                    기준["최소"], 기준["최대"], step=기준["간격"], format="%.1f", key=f"슬라이더_{이름}")
            st.button("기본값으로", icon=":material/restart_alt:", on_click=기본값으로, key="기상초기화")
    단계, 단계들 = 종합판정(값들)
    with 우:
        해당 = [이름 for 이름, 값 in 단계들.items() if 값 == 단계]
        이유 = "모든 기상값이 주의 기준보다 양호합니다." if 단계 == "안정" else f"{단계} 기준 해당: {', '.join(해당)}"
        ui.상태카드(단계, 이유)
        with ui.패널("vars", "변수별 상태", "가장 나쁜 변수의 단계가 현재 상황이 됩니다"):
            ui.임시기준안내()
            ui.변수별상태(값들, 단계들, 기상변수)
    좌, 우 = st.columns([1, 1.15], gap="small")
    with 좌:
        지도칸()
    with 우:
        with ui.패널("expect", "예상 체류시간 변화", "터미널을 고르면 이 조건의 예상값을 보여 줄 자리입니다"):
            ui.빈자리(200)


{"전체 요약": 전체요약화면, "KPI 1": KPI1화면, "KPI 2": KPI2화면, "기상 상황 점검": 기상점검화면}[제목]()
