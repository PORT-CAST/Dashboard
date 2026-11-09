"""PORTCAST 부산항 의사결정지원 대시보드 기본 틀 (내용 없음).

실행: streamlit run app.py
사진: assets/containership.png를 넣으면 그 사진을 씁니다. 없으면 인터넷 주소의 사진을 불러옵니다.
색상: .streamlit/config.toml과 ui.py의 색 사전
분석 자료: data/ 폴더에 체류시간_찐최종.csv(KPI 1), PORTCAST_선박_기상_특보노출시간_최종.csv(KPI 2)를 넣습니다.
판정 기준: criteria.py의 주의, 위험 값을 바꿉니다.
"""
import numpy as np
import pandas as pd
import streamlit as st

import charts
import kpi
import models
import ui
from terminal_map import 터미널지도
from criteria import 증가량기준, 증가량판정

st.set_page_config(page_title="PORTCAST | 스마트항만 의사결정지원", page_icon="🚢", layout="wide")
ui.스타일적용()

북항 = ["BPTC_G", "BPT_S"]
신항 = ["BNCT", "HPNT", "PNC", "PNIT"]
기간들 = ["전체", "2021", "2022", "2023", "2024"]
팀이름 = "PORTCAST"
프로젝트이름 = "스마트항만 의사결정지원 프로젝트"
프로젝트소개 = ("부산항의 기상·해양 데이터와 풀컨테이너선 운항 데이터를 결합해, 환경 조건에 따른 체류시간과 "
          "터미널별 차이를 비교하고 과거 조건에 기반한 시나리오를 살펴봅니다")
화면들 = {
    "전체 요약": ("space_dashboard", 프로젝트소개),
    "KPI 1": ("air", "기상 관련 체류시간 증가량"),
    "KPI 2": ("warning", "기상특보 발효 시 체류시간 증가량"),
    "기상 상황 점검": ("tune", "기상 시나리오별 예상 체류시간 증가와 안정·주의·위험을 확인합니다"),
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
    _연결 = kpi.자료있음()
    ui.상태표시("분석 자료 연결됨" if all(_연결.values()) else
               "자료 일부 연결" if any(_연결.values()) else "자료 연결 전")

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


KPI1표, KPI2표 = kpi.불러오기()
있음 = {"KPI1": KPI1표 is not None, "KPI2": KPI2표 is not None}
st.session_state.setdefault("표본선택", "조건부 표본")
st.session_state.setdefault("기상변수선택", "최대순간풍속")


def 숫자(값, 자리: int = 1, 끝: str = "") -> str:
    return "-" if 값 is None or pd.isna(값) else f"{값:,.{자리}f}{끝}"


def 자료없음(이름: str) -> None:
    파일 = kpi.KPI1파일.name if 이름 == "KPI1" else kpi.KPI2파일.name
    st.info(f"`data/{파일}` 파일이 없습니다. README의 '분석 자료 넣기'를 보고 data 폴더에 넣어 주세요.",
            icon=":material/folder_open:")


def 표본조절(기상변수도: bool) -> tuple[bool, str | None]:
    with st.container(key="kpictl", horizontal=True, horizontal_alignment="distribute"):
        if 기상변수도:
            st.segmented_control("기상변수", list(kpi.기상구간), key="기상변수선택", required=True,
                                 format_func=lambda 이름: kpi.기상구간[이름]["설명"].replace("체류 중 ", ""))
        if 기상변수도:
            변수 = st.session_state.get("기상변수선택", "최대순간풍속")
            후보 = kpi.비교후보(변수)
            단위 = kpi.기상구간[변수]["단위"]
            st.selectbox("비교 구간", 후보, key=f"비교구간_{변수}", format_func=lambda g: f"{g} {단위}",
                         help="기준 구간과 비교할 구간입니다. 자료가 없는 터미널이 있으면 다른 구간을 골라 보세요.")
        st.segmented_control("비교 표본", ["조건부 표본", "전체 표본"], key="표본선택", required=True,
                             help=f"조건부 표본: {kpi.조건부상세}. 선박 규모·작업량 구성 차이를 줄이기 위한 보조 비교입니다.")
    if st.session_state["표본선택"] == "조건부 표본":
        st.caption(kpi.조건부상세)
    return st.session_state["표본선택"] == "조건부 표본", st.session_state.get("기상변수선택")


def 보정모형(KPI: str = "KPI1"):
    """KPI별 최종 회귀 모형 (자료가 없으면 None). (적합모형, 표본, 독립변수).

    KPI1·기상 상황 점검 = M4_time, KPI2 = 모형 4 + 월·요일·연도추세.
    """
    return models.불러오기(KPI) if 있음["KPI1"] else None


def 범위글(값들: pd.Series) -> str:
    값들 = 값들.dropna()
    if 값들.empty:
        return "-"
    작은, 큰 = 값들.min(), 값들.max()
    return f"{작은:+.1f}h" if abs(큰 - 작은) < 0.05 else f"{작은:+.1f}~{큰:+.1f}h"


def 모형정보칸(키: str) -> None:
    KPI = "KPI2" if 키 == "k2" else "KPI1"
    모형 = 보정모형(KPI)
    if 모형 is None:
        return
    결과, 표, 열들 = 모형
    if KPI == "KPI1":
        항목들 = [
            ("KPI 1 보정값", "같은 터미널에서 해당 기상변수만 기준 구간 대표값 → 비교 구간 대표값으로 바뀔 때의 차이 "
                           "(대표값 = 구간 기록의 중앙값, 기울기 = 기상 계수 + 신항이면 신항더미×기상 계수). "
                           "항만(북항·신항) 상호작용 모형이라 같은 항만의 터미널은 기울기가 같고, 구간 대표값만 다릅니다."),
            ("표준화", "총톤수·총작업량·기상 6개는 2021~2023 학습자료의 평균·표준편차로 표준화해 적합했고, "
                     "화면 값은 원래 단위(m/s·m·km)로 되돌려 계산합니다."),
            ("검증 성능", "2021~2023년 학습 모형의 2024년 8,442건 검증: MAE 3.11h, RMSE 4.28h, R² 0.769. "
                        "화면에 쓰는 전체기간 재적합 모형의 R² 0.735와는 구분합니다."),
            ("달력 효과", "월·요일·연도추세를 함께 넣어 계절·요일·추세 차이를 맞췄습니다. 두 조건을 비교할 때는 같은 날짜로 보고 상쇄됩니다."),
            ("신뢰구간", f"막대 위 가는 선은 95% 신뢰구간입니다 ({결과.공분산설명}, 정규 근사)."),
            ("변수 간 관련성", "기상변수 6개는 서로 관련이 커서 한 변수만 바뀐다는 가정은 현실과 다를 수 있습니다. "
                           "풍속 중앙값처럼 부호가 직관과 반대인 변수는 단독으로 해석하지 마세요."),
            ("해석 범위", "체류 중 최댓값·최솟값을 쓰므로 오래 머문 선박이 강한 기상을 만날 기회가 큰 문제는 남아 있습니다. "
                        "인과 효과가 아니라 다른 조건을 맞춘 연관성입니다."),
        ]
    else:
        항목들 = [
            ("KPI 2 보정값", "총톤수·총작업량·기상 6개·월·요일·연도가 같을 때 특보 노출 − 비노출의 체류시간 차이 "
                           "(BPT_S는 특보 계수, 다른 터미널은 특보 계수 + 터미널×특보 계수). 선박 규모·기상과 관계없이 터미널마다 하나의 값입니다."),
            ("적합 자료", "2021~2023년 학습자료로 적합했습니다. 2024년 자료는 검증(MAE 3.0h, 검증 R² 0.78)에 썼습니다."),
            ("신뢰구간", f"막대 위 가는 선은 95% 신뢰구간입니다 ({결과.공분산설명}, 정규 근사). "
                       "같은 날 입항한 선박끼리 오차가 비슷하고 28일 안쪽으로 이어지는 점을 반영합니다."),
            ("해석 범위", "특보와 기상은 서로 관련되어 있어 특보만 바뀐다는 가정은 현실과 다를 수 있습니다. "
                        "인과 효과가 아니라 다른 조건을 맞춘 연관성입니다."),
        ]
    목록 = "".join(f"<li><b>{제목}</b><span>{내용}</span></li>" for 제목, 내용 in 항목들)
    with st.expander("회귀 보정값은 어떻게 계산했나요?", icon=":material/functions:"):
        st.markdown(f"""<div class="modelinfo">
<p class="mhead"><b>{결과.짧은이름}</b> — {결과.설명}</p>
<p class="mstat">적합 표본 {int(결과.nobs):,}건 · 독립변수 {len(열들)}개 · 적합 R² {결과.rsquared:.3f} (수정 R² {결과.rsquared_adj:.3f}) ·
{결과.적합설명} · 화면의 기간·월·표본 선택과 관계없이 같은 모형</p>
<ul>{목록}</ul></div>""", unsafe_allow_html=True)


def 표보기(표: pd.DataFrame, 열이름: dict, 높이: int = 260) -> None:
    보일표 = 표.rename(columns=열이름)[list(열이름.values())].copy()
    if "표본적음" in 표:
        보일표["비고"] = 표["표본적음"].map({True: "표본 적음", False: ""})
    st.dataframe(보일표, hide_index=True, height=높이, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="%.3f" if "p값" in c else "%.1f")
                                for c in 보일표.columns
                                if any(k in c for k in ("중앙값", "차이", "P90", "보정"))})


def 전체요약화면() -> None:
    좌, 우 = st.columns([1.3, 1], gap="small")
    with 좌:
        if 있음["KPI2"]:
            범위 = kpi.거르기(KPI2표, 기간값, 터미널)
            체류 = kpi.요약값(범위["체류시간"])
            k2 = kpi.KPI2통합(범위)
            ui.지표줄([{"이름": "체류시간 중앙값", "종류": "main", "아이콘": "schedule", "값": 숫자(체류["중앙값"], 1, "h"),
                       "보조": f"P90 {숫자(체류['P90'], 1, '시간')} · 접안~터미널 출항"},
                      {"이름": "분석 기록", "종류": "base", "아이콘": "directions_boat", "값": f"{체류['건수']:,}",
                       "보조": "건 · 총작업량 0 제외, 반복 기항 포함"}])
            ui.지표줄([{"이름": "특보 노출 비율", "아이콘": "warning", "종류": "alert", "값": 숫자(k2["노출비율"], 1, "%"),
                       "보조": f"노출 {k2['노출']['건수']:,}건 / {k2['전체']:,}건"},
                      {"이름": "노출 − 비노출 중앙값", "아이콘": "timer", "값": 숫자(k2["차이"], 1, "h") if pd.isna(k2["차이"]) else f"{k2['차이']:+.1f}h",
                       "보조": "전체 표본 · 지연시간이 아닌 집단 차이"}])
        else:
            자료없음("KPI2")
    with 우:
        지도칸()
    if 있음["KPI2"]:
        with ui.패널("dist", "터미널별 체류시간", f"{기간글} · 막대는 중앙값, 점은 P90(상위 10% 경계). 생산성 순위가 아닙니다"):
            분포 = kpi.터미널분포(kpi.거르기(KPI2표, 기간값))
            st.plotly_chart(charts.터미널분포막대(분포), config=charts.설정, key="c_dist")


월묶음 = {"전체": list(range(1, 13)), "봄": [3, 4, 5], "여름": [6, 7, 8], "가을": [9, 10, 11],
        "겨울": [12, 1, 2], "태풍철": [7, 8, 9]}


def 월글(월들: list[int]) -> str:
    for 이름, 목록 in 월묶음.items():
        if sorted(목록) == sorted(월들):
            return "전체 월" if 이름 == "전체" else f"{이름}({'·'.join(f'{m}' for m in 목록)}월)"
    return ", ".join(f"{m}월" for m in 월들)


def 기간월조절(키: str) -> list[int] | None:
    """그래프 위 한 줄: 연도(위쪽 기간 필터와 연동) + 월 체크박스. 고른 월 목록(전체면 None)을 돌려준다."""
    def 연도바꿈() -> None:
        st.session_state["기간선택"] = st.session_state[f"{키}_연도"]

    def 묶음적용(목록: list[int]) -> None:
        for m in range(1, 13):
            st.session_state[f"{키}_m{m}"] = m in 목록

    for m in range(1, 13):
        st.session_state.setdefault(f"{키}_m{m}", True)
    st.session_state[f"{키}_연도"] = 기간값          # 위쪽 필터 값으로 맞춘다
    고른 = [m for m in range(1, 13) if st.session_state[f"{키}_m{m}"]]

    with st.container(horizontal=True, vertical_alignment="bottom", gap="small"):
        st.selectbox("연도", 기간들, key=f"{키}_연도", on_change=연도바꿈, width=130)
        with st.popover(f"월: {월글(고른) if 고른 else '선택 없음'}", icon=":material/calendar_month:"):
            with st.container(horizontal=True, gap="small"):
                for 이름, 목록 in 월묶음.items():
                    st.button(이름, key=f"{키}_묶음_{이름}", on_click=묶음적용, args=(목록,), type="tertiary")
            칸들 = st.columns(3)
            for m in range(1, 13):
                칸들[(m - 1) % 3].checkbox(f"{m}월", key=f"{키}_m{m}")
            st.caption("접안 날짜 기준 · 여러 개 선택 가능")
    if not 고른:
        st.warning("월을 하나 이상 선택해 주세요. 지금은 전체 월로 계산합니다.", icon=":material/info:")
        return None
    return None if len(고른) == 12 else 고른


def KPI1화면() -> dict | None:
    if not 있음["KPI1"]:
        자료없음("KPI1")
        return
    조건부, 변수 = 표본조절(True)
    정보 = kpi.기상구간[변수]
    기준구간, 비교구간 = kpi.기준비교(변수, st.session_state.get(f"비교구간_{변수}"))
    기준이름, 비교이름 = f"{기준구간} {정보['단위']}", f"{비교구간} {정보['단위']}"
    범위 = kpi.거르기(KPI1표, 기간값, 터미널, 조건부)
    통합 = kpi.KPI1통합(범위, 변수, 비교구간)
    표본글 = kpi.조건부설명 if 조건부 else "전체 표본"
    모형 = 보정모형()
    전체범위 = kpi.거르기(KPI1표, 기간값, None, 조건부)
    차이 = kpi.KPI1차이표(전체범위, 변수, 비교구간)
    보정 = models.KPI1보정표(모형[0], 차이, 전체범위, 변수, 비교구간) if 모형 else None
    if 보정 is None:
        보정타일 = {"이름": "회귀 보정 증가량", "아이콘": "functions", "값": "-",
                  "보조": "이 변수는 모형에서 제외됨 (VIF)" if 모형 else "모형 없음"}
    elif 터미널:
        행 = 보정.set_index("터미널").loc[터미널]
        보정타일 = {"이름": f"회귀 보정 증가량 · {터미널}", "아이콘": "functions",
                  "값": "-" if pd.isna(행["효과"]) else f"{행['효과']:+.1f}h",
                  "보조": "-" if pd.isna(행["효과"]) else f"95% CI {행['하한']:+.1f}~{행['상한']:+.1f}h · 다른 조건 동일 가정"}
    else:
        보정타일 = {"이름": "회귀 보정 증가량 (터미널별)", "아이콘": "functions", "값": 범위글(보정["효과"]),
                  "보조": "GT·작업량·특보·다른 기상이 같을 때 · 아래 그래프 참고"}

    좌, 우 = st.columns([1.3, 1], gap="small")
    with 좌:
        ui.지표줄([{"이름": f"KPI 1 · {비교이름} − {기준이름}", "종류": "main", "아이콘": "schedule",
                   "값": "-" if pd.isna(통합["차이"]) else f"{통합['차이']:+.1f}h",
                   "보조": f"단순 중앙값 차이 · {터미널 or '전체 터미널 통합'} · {표본글}"
                          + (" · ⚠ 표본 적음, 해석 주의" if min(통합["기준"]["건수"], 통합["비교"]["건수"]) < kpi.적은표본 else "")},
                  보정타일])
        ui.지표줄([{"이름": f"기준 구간 ({기준이름})", "아이콘": "air", "값": 숫자(통합["기준"]["중앙값"], 1, "h"),
                   "보조": f"{통합['기준']['건수']:,}건 · 체류시간 중앙값"},
                  {"이름": f"비교 구간 ({비교이름})", "종류": "base", "아이콘": "storm", "값": 숫자(통합["비교"]["중앙값"], 1, "h"),
                   "보조": f"{통합['비교']['건수']:,}건" + (" · 표본 적음" if 통합["비교"]["건수"] < kpi.적은표본 else "")}])
    with 우:
        지도칸()

    좌, 우 = st.columns([2, 1], gap="small")
    with 좌:
        with ui.패널("k1a", f"터미널별 KPI 1 ({비교이름} − {기준이름})",
                    f"{정보['설명']} · {표본글} · 빗금은 10건 미만 표본"):
            월들 = 기간월조절("k1")
            월범위 = kpi.거르기(KPI1표, 기간값, None, 조건부, 월들)
            if 월범위.empty:
                st.info("선택한 기간·월·표본 조건에 해당하는 기록이 없습니다.")
            월차이 = kpi.KPI1차이표(월범위, 변수, 비교구간) if 월들 else 차이
            사유 = kpi.빈구간사유(월범위, kpi.거르기(KPI1표, 기간값, 월들=월들), 변수, 월차이, 비교구간)
            if 월들:
                st.caption(f"{기간글} · {월글(월들)} 접안 기록 {len(월범위):,}건으로 계산 · 월 선택은 이 그래프에만 적용됩니다")
            보기 = st.toggle("회귀 보정값 함께 보기", value=True, key="k1_보정보기", disabled=모형 is None)
            월보정 = models.KPI1보정표(모형[0], 월차이, 월범위, 변수, 비교구간) if (모형 and 보기) else None
            if 월보정 is not None:
                st.plotly_chart(charts.보정비교막대([
                    {"이름": "단순 중앙값 차이", "표": 월차이, "값열": "차이", "색": charts.전체색, "적음열": "표본적음",
                     "건수글": [f"기준 {a:,}건 · 비교 {b:,}건" for a, b in zip(월차이["기준건수"], 월차이["비교건수"])]},
                    {"이름": "회귀 보정 (95% 신뢰구간)", "표": 월보정, "값열": "효과", "하한열": "하한", "상한열": "상한",
                     "색": charts.보정색,
                     "건수글": [f"대표값 {a:.1f} → {b:.1f} {정보['단위']}" for a, b in zip(월보정["기준대표값"], 월보정["비교대표값"])]},
                ]), config=charts.설정, key="c_k1a")
                if 변수 == "풍속":
                    st.caption("⚠ 풍속 중앙값은 돌풍 최댓값과 함께 모형에 들어가 보정값이 음수로 나옵니다(다중공선성). 단독으로 해석하지 마세요.")
            else:
                if 보기 and 모형 and models.KPI1연결.get(변수) is None:
                    st.caption("이 기상변수(유의파고 최댓값)는 VIF가 높아 회귀 모형에서 제외되어 보정값이 없습니다. 모형에는 유의파고 중앙값이 들어 있습니다.")
                st.plotly_chart(charts.차이막대(월차이, 기준이름, 비교이름, 사유=사유), config=charts.설정, key="c_k1a")
            if 사유:
                st.caption(f"막대가 없는 터미널 — {kpi.빈구간설명(사유)}. 비교 구간이나 비교 표본을 바꿔 보세요.")
    with 우:
        구간 = kpi.KPI1구간표(범위.assign(터미널=범위["터미널"]), 변수)
        구간합 = (범위.assign(구간=kpi.구간나누기(범위, 변수)).dropna(subset=["구간"])
               .groupby("구간", observed=False)["체류시간"]
               .agg(건수="size", 중앙값="median", P90=lambda s: s.quantile(0.9)).reset_index())
        with ui.패널("k1b", "기상 구간별 체류시간", f"{터미널 or '전체 터미널 통합'} · 구간별 중앙값과 건수"):
            st.plotly_chart(charts.구간막대(구간합, 정보["단위"], 낮을수록나쁨=정보.get("비교") == 정보["이름"][0]),
                            config=charts.설정, key="c_k1b")
    좌, 우 = st.columns([1, 2], gap="small")
    with 좌:
        with ui.패널("k1c", "두 구간 중앙값 비교", "터미널별 기준 구간과 비교 구간"):
            st.plotly_chart(charts.두집단막대(차이, 기준이름, 비교이름, 높이=260), config=charts.설정, key="c_k1c")
    with 우:
        with ui.패널("k1d", "구간별 상세", f"{표본글} · 구간 결측 {통합['결측']:,}건 제외 · 시간 단위"):
            상세 = kpi.KPI1구간표(전체범위 if not 터미널 else 범위, 변수)
            상세["표본적음"] = 상세["건수"] < kpi.적은표본
            표보기(상세, {"터미널": "터미널", "구간": f"구간({정보['단위']})", "건수": "건수", "중앙값": "중앙값", "P90": "P90"})
    st.caption("※ 증가량은 비교 구간과 기준 구간의 체류시간 중앙값 차이이며, 기상 때문에 생긴 지연시간이 아닙니다. 회귀 보정은 다른 조건이 같을 때의 평균 체류시간 차이입니다. "
               "오래 머문 선박일수록 체류 중 강한 기상을 만날 기회가 커지는 점도 함께 고려해야 합니다.")
    모형정보칸("k1")
    return {"월들": 월들, "월차이": 월차이, "월보정": 월보정}


def KPI2화면() -> None:
    if not 있음["KPI2"]:
        자료없음("KPI2")
        return
    조건부, _ = 표본조절(False)
    표본글 = kpi.조건부설명 if 조건부 else "전체 표본"
    범위 = kpi.거르기(KPI2표, 기간값, 터미널, 조건부)
    통합 = kpi.KPI2통합(범위)
    모형 = 보정모형("KPI2")
    보정 = models.특보효과(모형[0]) if 모형 else None
    if 보정 is None:
        보정타일 = {"이름": "회귀 보정 증가량", "아이콘": "functions", "값": "-", "보조": "KPI 1 자료가 있어야 모형을 적합합니다"}
    elif 터미널:
        행 = 보정.set_index("터미널").loc[터미널]
        보정타일 = {"이름": f"회귀 보정 증가량 · {터미널}", "아이콘": "functions", "값": f"{행['효과']:+.1f}h",
                  "보조": f"95% CI {행['하한']:+.1f}~{행['상한']:+.1f}h · p={행['p값']:.3f}"}
    else:
        보정타일 = {"이름": "회귀 보정 증가량 (터미널별)", "아이콘": "functions", "값": 범위글(보정["효과"]),
                  "보조": "GT·작업량·기상이 같을 때 · 아래 그래프 참고"}

    좌, 우 = st.columns([1.3, 1], gap="small")
    with 좌:
        ui.지표줄([{"이름": "KPI 2 · 노출 − 비노출 중앙값", "종류": "main", "아이콘": "schedule",
                   "값": "-" if pd.isna(통합["차이"]) else f"{통합['차이']:+.1f}h",
                   "보조": f"단순 중앙값 차이 · {터미널 or '전체 터미널 통합'} · {표본글}"
                          + (" · ⚠ 표본 적음, 해석 주의" if min(통합["비노출"]["건수"], 통합["노출"]["건수"]) < kpi.적은표본 else "")},
                  보정타일])
        ui.지표줄([{"이름": "특보 노출 비율", "종류": "alert", "아이콘": "warning", "값": 숫자(통합["노출비율"], 1, "%"),
                   "보조": f"노출 {통합['노출']['건수']:,}건 / {통합['전체']:,}건"},
                  {"이름": "비노출 중앙값", "종류": "base", "아이콘": "directions_boat", "값": 숫자(통합["비노출"]["중앙값"], 1, "h"),
                   "보조": f"{통합['비노출']['건수']:,}건 · P90 {숫자(통합['비노출']['P90'], 1, 'h')}"},
                  {"이름": "노출 중앙값", "아이콘": "timer", "값": 숫자(통합["노출"]["중앙값"], 1, "h"),
                   "보조": f"{통합['노출']['건수']:,}건 · P90 {숫자(통합['노출']['P90'], 1, 'h')}"
                          + (" · 표본 적음" if 통합["노출"]["건수"] < kpi.적은표본 else "")}])
    with 우:
        지도칸()

    전체차이 = kpi.KPI2차이표(kpi.거르기(KPI2표, 기간값))
    조건부차이 = kpi.KPI2차이표(kpi.거르기(KPI2표, 기간값, None, True))
    좌, 우 = st.columns([2, 1], gap="small")
    with 좌:
        with ui.패널("k2a", "단순 차이와 회귀 보정의 KPI 2",
                    f"전체 표본 · 조건부 표본({kpi.조건부설명}) 중앙값 차이와, GT·작업량·기상을 맞춘 회귀 보정값 · 빗금은 10건 미만"):
            if 보정 is not None:
                st.plotly_chart(charts.보정비교막대([
                    {"이름": "전체 표본 중앙값 차이", "표": 전체차이, "값열": "차이", "색": charts.전체색, "적음열": "표본적음",
                     "건수글": [f"비노출 {a:,}건 · 노출 {b:,}건" for a, b in zip(전체차이["비노출건수"], 전체차이["노출건수"])]},
                    {"이름": "조건부 표본 중앙값 차이", "표": 조건부차이, "값열": "차이", "색": charts.조건부색, "적음열": "표본적음",
                     "건수글": [f"비노출 {a:,}건 · 노출 {b:,}건" for a, b in zip(조건부차이["비노출건수"], 조건부차이["노출건수"])]},
                    {"이름": "회귀 보정 (95% 신뢰구간)", "표": 보정, "값열": "효과", "하한열": "하한", "상한열": "상한",
                     "색": charts.보정색, "건수글": [f"p = {p:.3f}" for p in 보정["p값"]]},
                ], y제목="노출 − 비노출 (시간)"), config=charts.설정, key="c_k2a")
            else:
                st.plotly_chart(charts.표본비교막대(전체차이, 조건부차이), config=charts.설정, key="c_k2a")
    with 우:
        구성 = kpi.KPI2구성(범위)
        with ui.패널("k2b", "노출·비노출 집단 구성", f"{터미널 or '전체 터미널'} · {표본글} · 구성이 다르면 단순 차이에 섞입니다"):
            st.dataframe(구성.rename(columns={"GT중앙값": "GT", "작업량중앙값": "작업량", "체류중앙값": "체류(h)"}),
                         hide_index=True, width="stretch", height=110,
                         column_config={"GT": st.column_config.NumberColumn(format="localized"),
                                        "작업량": st.column_config.NumberColumn(format="%.0f"),
                                        "체류(h)": st.column_config.NumberColumn(format="%.1f")})
            st.caption("GT·작업량·체류시간은 각 집단의 중앙값입니다.")
            st.plotly_chart(charts.두집단막대(kpi.KPI2차이표(kpi.거르기(KPI2표, 기간값, None, 조건부)), "비노출", "노출", 높이=230),
                            config=charts.설정, key="c_k2b")
    with ui.패널("k2c", f"터미널별 KPI 2 ({표본글})", "시간 단위 · 차이 = 노출 − 비노출 중앙값 · 보정 = 회귀 보정 증가량(KPI 2 모형 · 2021~2023 학습)"):
        표 = kpi.KPI2차이표(kpi.거르기(KPI2표, 기간값, None, 조건부))
        열 = {"터미널": "터미널", "비노출건수": "비노출 건수", "노출건수": "노출 건수", "비노출중앙값": "비노출 중앙값",
             "노출중앙값": "노출 중앙값", "차이": "차이"}
        if 보정 is not None:
            표 = 표.merge(보정.rename(columns={"효과": "보정", "하한": "보정하한", "상한": "보정상한"}), on="터미널", how="left")
            열.update({"보정": "보정", "보정하한": "보정 CI 하한", "보정상한": "보정 CI 상한", "p값": "보정 p값"})
        표보기(표, 열, 높이=260)
    st.caption("※ 특보 발효 구간과 체류 구간이 양의 시간만큼 겹치면 노출입니다. 차이는 노출 집단과 비노출 집단의 중앙값 차이이며, "
               "특보 때문에 생긴 지연시간으로 해석하지 않습니다.")
    모형정보칸("k2")


# ---------------- 기상 상황 점검: 조작판(슬라이더) + 결과판 ----------------
def _키(v: str) -> str:
    return f"점검_{v}"


def 프리셋적용(터미널이름: str, 시나리오: str) -> None:
    """시나리오 버튼: 그 터미널의 조건별 기상 중앙값으로 슬라이더를 한 번에 맞춘다."""
    _, 표, _ = 보정모형()
    값 = models.시나리오프로필(표).set_index(["터미널", "시나리오"]).loc[(터미널이름, 시나리오)]
    for v in models.기상변수:
        st.session_state[_키(v)] = round(models.화면값(v, float(값[v])), 1)
    st.session_state["점검_시작점"] = 시나리오


def 점검터미널바꿈() -> None:
    고른값 = st.session_state["점검_터미널"]
    st.session_state["북항선택"] = 고른값 if 고른값 in 북항 else None
    st.session_state["신항선택"] = 고른값 if 고른값 in 신항 else None


def 조작판(대상: str) -> tuple[dict, bool]:
    """왼쪽 조작판. 슬라이더 값(모형 단위)과 특보 여부를 돌려준다."""
    결과, 표, _ = 보정모형()
    # 다른 화면에 다녀오면 Streamlit이 화면에 없던 위젯(슬라이더·스위치) 값을 지운다.
    # 마지막 설정을 보관해 두었다가 되살리고, 보관한 값이 없으면 평온 시작점으로 맞춘다.
    필요 = [_키(v) for v in models.기상변수]
    if any(k not in st.session_state for k in 필요):
        보관 = st.session_state.get("점검_보관")
        if 보관 and all(k in 보관 for k in 필요):
            for k, 값 in 보관.items():
                st.session_state[k] = 값
        else:
            프리셋적용(대상, models.기준시나리오)
    with st.container(key="console"):
        st.markdown('<p class="console-h">기상 조건 조절</p>'
                    '<p class="console-s">돌풍·최대파고·시정을 정하면 나머지 기상값은 과거 기록으로 예측합니다</p>',
                    unsafe_allow_html=True)
        st.session_state["점검_터미널"] = 대상
        st.selectbox("터미널", kpi.터미널순서, key="점검_터미널", on_change=점검터미널바꿈)
        st.caption("시작점 (터미널별 조건 기록의 변수별 중앙값)")
        with st.container(horizontal=True, gap="small"):
            for 이름, 정의 in models.시나리오정의.items():
                st.button(이름, key=f"점검_프리셋_{이름}", on_click=프리셋적용, args=(대상, 이름),
                          icon=f":material/{정의['아이콘']}:", type="primary" if st.session_state.get("점검_시작점") == 이름 else "secondary")
        세부 = st.toggle("세부 조정 (중앙값도 직접 바꾸기)", key="점검_세부")
        값들 = {}
        for 묶음, 아이콘, 주, 종, 관계 in models.짝변수:
            st.markdown(f'<div class="console-g">{ui.아이콘(아이콘)}{묶음}</div>', unsafe_allow_html=True)
            주이름, 주단위, _ = models.기상이름[주]
            최소, 최대, 간격 = models.주변수범위[주]
            st.session_state[_키(주)] = float(min(max(st.session_state[_키(주)], 최소), 최대))
            주화면 = st.slider(f"{주이름} ({주단위})", 최소, 최대, step=간격, key=_키(주), format="%.1f")
            값들[주] = models.모형값(주, 주화면)
            종이름, 종단위, _ = models.기상이름[종]
            예측 = models.조건예측(표, 주, 종, 값들[주], 관계)
            if 세부:
                # 과거 기록에서 이 값일 때 나타난 범위 안에서만 직접 조절
                원하한, 원상한 = models.조건범위(표, 주, 종, 값들[주], 관계)
                원하한, 원상한 = models.화면값(종, 원하한), models.화면값(종, 원상한)
                # 표시 눈금을 허용 범위 안쪽으로 맞춘다. 범위를 넓혀 물리 관계를 깨지 않는다.
                아래 = np.ceil(원하한 * 10 - 1e-9) / 10
                위 = np.floor(원상한 * 10 + 1e-9) / 10
                if 위 > 아래:
                    st.session_state[_키(종)] = float(min(max(st.session_state.get(_키(종), models.화면값(종, 예측)), 아래), 위))
                    종화면 = st.slider(f"{종이름} ({종단위})", float(아래), float(위), step=0.1, key=_키(종), format="%.1f")
                else:
                    종화면 = float(min(max(models.화면값(종, 예측), 원하한), 원상한))
                    st.session_state[_키(종)] = 종화면
                    st.markdown(f'<div class="console-p"><span>{종이름}</span><b>{종화면:.2f} {종단위}</b><i>고정값</i></div>', unsafe_allow_html=True)
                값들[종] = models.모형값(종, 종화면)
                st.caption(f"보완 {models.화면값(종, 예측):.1f}{종단위} · 허용 범위 {원하한:.2f}~{원상한:.2f}{종단위}")
            else:
                값들[종] = 예측
                st.session_state[_키(종)] = round(models.화면값(종, 예측), 1)
                st.markdown(f'<div class="console-p"><span>{종이름}</span><b>{models.화면값(종, 예측):.1f} {종단위}</b>'
                            f'<i>예측값</i></div>', unsafe_allow_html=True)
        st.markdown('<div class="console-g">' + ui.아이콘("warning") + '기상특보</div>', unsafe_allow_html=True)
        특보 = st.toggle("풍랑·태풍 특보 발효 중", key="점검_특보")
    st.session_state["점검_보관"] = {k: st.session_state[k] for k in
                                 [_키(v) for v in models.기상변수] + ["점검_세부", "점검_특보"] if k in st.session_state}
    return 값들, 특보


def 기상점검화면() -> dict | None:
    if 보정모형() is None:
        자료없음("KPI1")
        return
    결과, 표, _ = 보정모형()
    프로필 = models.시나리오프로필(표)
    대상 = 터미널 or st.session_state.get("점검_터미널", models.기준터미널)

    좌, 우 = st.columns([1, 1.65], gap="medium")
    with 좌:
        값들, 특보 = 조작판(대상)
    문제 = models.입력점검(값들)
    if 문제:
        st.error(" · ".join(문제))
        return None
    평온값 = models.평온기준(표, 프로필, 대상)
    효과 = models.조절효과(결과, 프로필, 대상, 값들, 특보, 평온값)
    평온예상 = models.예상체류값(결과, 표, 대상, 평온값, False)
    단계 = 증가량판정(효과["효과"])
    조건 = (st.session_state.get("점검_시작점", "직접 조절") + " 기준 조절") + (" + 특보" if 특보 else "")

    with 우:
        효과표시 = {k: (0.0 if abs(효과[k]) < 0.05 else 효과[k]) for k in ("효과", "하한", "상한")}
        ui.상태카드(단계, f"평온 대비 {효과표시['효과']:+.1f}시간 (95% CI {효과표시['하한']:+.1f}~{효과표시['상한']:+.1f}) · "
                       f"경계 {증가량기준['주의']:g}h / {증가량기준['위험']:g}h (임시)", 제목=f"{대상} · 체류시간 증가량 분류 (임시)")
        st.caption("과거 체류기간 기상값을 비교한 결과입니다. 운항 안전도나 현재·예보 기상의 위험 등급을 뜻하지 않습니다.")
        ui.계산식(평온예상, 효과["효과"], 효과["하한"], 효과["상한"], 평온예상 + 효과["효과"], 조건)

        기여 = []
        for v in models.기상변수:
            이름, 단위, _ = models.기상이름[v]
            기여.append({"이름": 이름, "기여": 효과["기여"][v],
                       "설명": f"평온 {models.화면값(v, 평온값[v]):.1f} → {models.화면값(v, 값들[v]):.1f} {단위}"})
        if 특보:
            기여.append({"이름": "기상특보", "기여": 효과["기여"]["특보유무"], "설명": "특보 없음 → 발효"})
        with ui.패널("chk_b", "무엇이 체류시간을 바꿨나요?", f"{대상} · 변수별 기여(시간) · 막대 합 = 기상 조건에 따른 변화"):
            st.plotly_chart(charts.기여도막대(pd.DataFrame(기여), 높이=270), config=charts.설정, key="c_contrib")
            st.caption("짝 변수(돌풍·풍속, 최대파고·유의파고, 시정 최솟값·중앙값)는 서로 반대 방향으로 나올 수 있습니다. "
                       "한 변수씩보다 묶음의 합으로 보세요.")

        행들 = []
        for t in kpi.터미널순서:
            평 = models.평온기준(표, 프로필, t)
            e = models.조절효과(결과, 프로필, t, 값들, 특보, 평)
            행들.append({"터미널": t, "효과": e["효과"], "하한": e["하한"], "상한": e["상한"], "단계": 증가량판정(e["효과"]),
                       "건수": f"평온 예상 {models.예상체류값(결과, 표, t, 평, False):.1f}h"})
        with ui.패널("chk_c", "같은 기상이면 터미널마다 얼마나 다를까요?",
                    f"왼쪽에서 설정한 기상값을 6개 터미널에 똑같이 적용 · 각 터미널의 평온 대비 · 점선은 주의·위험 경계(임시)"):
            st.plotly_chart(charts.시나리오막대(pd.DataFrame(행들), 증가량기준["주의"], 증가량기준["위험"], 대상, 높이=280),
                            config=charts.설정, key="c_chk_all")


    st.caption(f"※ 단계 경계(임시): 평온 대비 증가량 {증가량기준['주의']:g}시간 미만 안정, {증가량기준['주의']:g}~{증가량기준['위험']:g}시간 주의, "
               f"{증가량기준['위험']:g}시간 이상 위험 (criteria.py의 증가량기준). 보통 선박 = 그 터미널의 총톤수·총작업량 중앙값.")
    점검설명칸()
    return {"대상": 대상, "값들": 값들, "특보": 특보, "터미널별 결과": 행들}


def 점검설명칸() -> None:
    결과, 표, 열들 = 보정모형()
    항목들 = [
        ("계산 방법", f"같은 선박(총톤수·총작업량 동일)이 같은 날짜에 평온 대신 설정한 기상을 겪는다고 보고, KPI 1 모형({결과.이름})의 "
                    "기상 계수(+신항이면 신항더미×기상 계수)로 체류시간 차이를 계산합니다. 같은 항만의 터미널은 기울기가 같고 평온 기준값만 다릅니다."),
        ("기상값 예측", "돌풍 최댓값·순간최대파고 최댓값·시정 최솟값만 정하면, 짝 변수(풍속 중앙값·유의파고 중앙값·시정 중앙값)는 "
                       "과거 기록에서 그 값과 가장 가까운 400건의 중앙값으로 예측합니다. '세부 조정'을 켜면 그 기록들의 1~99% 범위 안에서 직접 바꿀 수 있습니다."),
        ("시작점", "평온·강풍·높은 파도·저시정·폭풍급 버튼은 그 터미널의 조건에 맞는 기록에서 변수별 중앙값으로 슬라이더를 맞춥니다. 하나의 실제 항차를 재현하는 것은 아닙니다."),
        ("기상특보", "켜면 같은 KPI 1 모형의 특보 계수(북항 +0.67h, 신항 +0.74h)를 더합니다. "
                     "터미널별 특보 효과는 KPI 2 화면(KPI 2 모형)에서 확인하세요."),
        ("예상 체류시간", "보통 선박(그 터미널의 총톤수·총작업량 중앙값)에 월·요일·연도추세는 그 터미널 기록의 평균을 넣은 모형 예측값입니다."),
        ("해석 범위", "기상값은 '체류 기간 전체'의 중앙값·최댓값·최솟값입니다. 지금·예보 기상으로 예측하는 모형이 아니며, "
                    "인과 효과가 아니라 다른 조건을 맞춘 연관성입니다."),
    ]
    목록 = "".join(f"<li><b>{제목}</b><span>{내용}</span></li>" for 제목, 내용 in 항목들)
    with st.expander("기상 상황 점검은 어떻게 계산했나요?", icon=":material/functions:"):
        st.markdown(f"""<div class="modelinfo">
<p class="mhead"><b>{결과.짧은이름}</b> — {결과.설명}</p>
<p class="mstat">표본 {int(결과.nobs):,}건 · R² {결과.rsquared:.3f} · {결과.적합설명} · 신뢰구간: {결과.공분산설명}</p>
<ul>{목록}</ul></div>""", unsafe_allow_html=True)


def _기록(표: pd.DataFrame) -> list[dict]:
    return 표.round(1).astype(object).where(표.notna(), None).to_dict(orient="records")


def AI요약자료(화면자료: dict | None = None) -> list | dict:
    """현재 화면의 집계 결과 (AI 요약 입력). 자료가 없으면 빈 목록 → 버튼 비활성."""
    조건부 = st.session_state.get("표본선택", "조건부 표본") == "조건부 표본"
    if 제목 == "전체 요약" and 있음["KPI2"]:
        범위 = kpi.거르기(KPI2표, 기간값, 터미널)
        k2 = kpi.KPI2통합(범위)
        return {"체류시간": kpi.요약값(범위["체류시간"]), "특보노출비율(%)": round(k2["노출비율"], 1),
                "노출-비노출 중앙값 차이(h)": round(k2["차이"], 1),
                "터미널별 분포": _기록(kpi.터미널분포(kpi.거르기(KPI2표, 기간값)))}
    if 제목 == "KPI 1" and 있음["KPI1"]:
        변수 = st.session_state.get("기상변수선택", "최대순간풍속")
        정보 = kpi.기상구간[변수]
        기준구간, 비교구간 = kpi.기준비교(변수, st.session_state.get(f"비교구간_{변수}"))
        return {"기상변수": 정보["설명"], "기준구간": f"{기준구간} {정보['단위']}",
                "비교구간": f"{비교구간} {정보['단위']}", "표본": kpi.조건부설명 if 조건부 else "전체 표본",
                "월 선택 비교 그래프": {
                    "월": 월글(화면자료["월들"] or list(range(1, 13))),
                    "단순 차이": _기록(화면자료["월차이"]),
                    "회귀 보정": _기록(화면자료["월보정"]) if 화면자료["월보정"] is not None else [],
                    "적용 범위": "터미널별 비교 그래프에만 월 선택 적용. 나머지 지표는 선택 연도의 전체 월.",
                } if 화면자료 else {},
                "터미널별 단순 차이": _기록(kpi.KPI1차이표(kpi.거르기(KPI1표, 기간값, None, 조건부), 변수, 비교구간)),
                "터미널별 회귀 보정 효과(시간, 95% CI)": (
                    _기록(models.KPI1보정표(보정모형()[0], kpi.KPI1차이표(kpi.거르기(KPI1표, 기간값, None, 조건부), 변수, 비교구간),
                                         kpi.거르기(KPI1표, 기간값, None, 조건부), 변수, 비교구간))
                    if 보정모형() and models.KPI1연결.get(변수) else "모형에서 제외된 변수"),
                "보정 모형": f"M4_time — {보정모형()[0].설명}" if 보정모형() else "모형 없음"}
    if 제목 == "KPI 2" and 있음["KPI2"]:
        return {"전체 표본 터미널별": _기록(kpi.KPI2차이표(kpi.거르기(KPI2표, 기간값))),
                f"조건부 표본({kpi.조건부설명}) 터미널별": _기록(kpi.KPI2차이표(kpi.거르기(KPI2표, 기간값, None, True))),
                "터미널별 회귀 보정 효과(시간, 95% CI, p값)": _기록(models.특보효과(보정모형("KPI2")[0])) if 보정모형("KPI2") else "모형 없음",
                "보정 모형": f"모형 4 + 월·요일·연도추세 — {보정모형('KPI2')[0].설명}" if 보정모형("KPI2") else "모형 없음"}
    if 제목 == "기상 상황 점검" and 화면자료:
        return {"설정 기상값": {models.기상이름[v][0]: float(models.화면값(v, 값))
                             for v, 값 in 화면자료["값들"].items()},
                "기상특보": 화면자료["특보"], "단계 기준(임시)": 증가량기준,
                "터미널별 결과": 화면자료["터미널별 결과"],
                "주의": "체류 기간 기상 대표값 기반 연관성, 지금·예보 기상 예측 아님"}
    return []


# 자리는 기존 위치에 두되, 모든 화면 계산이 끝난 뒤 같은 결과로 요약을 만든다.
요약자리 = st.container()
화면자료 = {"전체 요약": 전체요약화면, "KPI 1": KPI1화면, "KPI 2": KPI2화면, "기상 상황 점검": 기상점검화면}[제목]()
with 요약자리:
    ui.AI요약칸({
        "화면": 제목,
        "기간": "전체 적합기간 (2021~2024)" if 제목 == "기상 상황 점검" else 기간값,
        "터미널": 화면자료["대상"] if 제목 == "기상 상황 점검" and 화면자료 else 터미널 or "전체 터미널",
        "정의": "체류시간=터미널 출항-접안(시간). 단순 차이는 집단 중앙값 차이, 회귀 보정은 조건부 평균 차이이며 인과적 지연시간이 아님. 10건 미만은 표본 적음.",
        "조건부 표본 기준": kpi.조건부상세,
        "분석결과": AI요약자료(화면자료),
    })
