"""KPI 1·2 계산 (체류시간_최종.ipynb 후반 항만별 분석 · 터미널_특보.ipynb 기준).

입력 자료 (data 폴더, Streamlit Cloud 배포를 위해 저장소에 포함)
- KPI 1: 체류시간_찐최종.csv                         선박별 체류 중 기상 대표값 (33,994행)
- KPI 2: PORTCAST_선박_기상_특보노출시간_최종.csv     특보 노출 결합 결과 (33,819행)

정의
- 체류시간 = 터미널 출항시각 - 접안시각 (시각 차이로 다시 계산)
- 분석 대상 = 총작업량 > 0
- 증가량 = 비교 집단 중앙값 - 기준 집단 중앙값 (지연시간이 아니라 집단 간 차이)
- 조건부 표본 = 항만별 GT·작업량 범위 (기초 EDA 후반 분석)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

자료폴더 = Path(__file__).parent / "data"
KPI1파일 = 자료폴더 / "체류시간_찐최종.csv"
KPI2파일 = 자료폴더 / "PORTCAST_선박_기상_특보노출시간_최종.csv"

터미널순서 = ["BNCT", "HPNT", "PNC", "PNIT", "BPTC_G", "BPT_S"]
적은표본 = 10          # 이 건수보다 적은 집단은 '표본 적음'으로 표시
조건부기준 = {
    "북항": {"터미널": ("BPTC_G", "BPT_S"), "GT": (5_000, 10_000), "작업량": (400, 600)},
    "신항": {"터미널": ("BNCT", "HPNT", "PNC", "PNIT"), "GT": (100_000, 150_000), "작업량": (2_000, 2_500)},
}
조건부설명 = "항만별 GT·작업량 제한"
조건부상세 = " / ".join(
    f"{항만}: {기준['GT'][0]:,} ≤ GT < {기준['GT'][1]:,}, "
    f"{기준['작업량'][0]:,} ≤ 총작업량 ≤ {기준['작업량'][1]:,}"
    for 항만, 기준 in 조건부기준.items()
)

# KPI 1 기상변수와 구간 (체류시간_최종.ipynb 후반 항만별 분석의 구간). 기본: 첫 구간 = 기준, 마지막 구간 = 비교.
# 시정처럼 낮을수록 나쁜 변수는 "기준"/"비교"를 직접 지정한다. "배율"은 원본 단위를 화면 단위로 바꾼다.
기상구간 = {
    "최대순간풍속": {"열": "돌풍", "원본열": "체류시간_최대순간풍속_최댓값_mps", "설명": "체류 중 최대순간풍속 최댓값",
               "단위": "m/s", "경계": [0, 5, 8, np.inf], "이름": ["5 미만", "5~8", "8 이상"]},
    "풍속": {"열": "풍속", "원본열": "체류시간_풍속_중앙값_mps", "설명": "체류 중 풍속 중앙값",
           "단위": "m/s", "경계": [0, 2, 4, np.inf], "이름": ["2 미만", "2~4", "4 이상"]},
    "유의파고": {"열": "파고", "원본열": "체류시간_유의파고_최댓값_m", "설명": "체류 중 유의파고 최댓값",
             "단위": "m", "경계": [0, 0.5, 1, 2, np.inf], "이름": ["0.5 미만", "0.5~1", "1~2", "2 이상"]},
    # 원본 단위 10m → km. EDA의 500·1,000·3,000 경계를 5·10·30km로 표시한다.
    "시정": {"열": "시정", "원본열": "체류시간_시정_최솟값_10m", "설명": "체류 중 시정 최솟값",
           "단위": "km", "배율": 0.01, "경계": [0, 5, 10, 30, np.inf], "이름": ["5 미만", "5~10", "10~30", "30 이상"],
           "기준": "30 이상", "비교": "5 미만"},
}


def 기준비교(변수: str, 비교: str | None = None) -> tuple[str, str]:
    """(기준 구간, 비교 구간). 비교를 주면 그 구간을 비교 구간으로 쓴다."""
    정보 = 기상구간[변수]
    기준 = 정보.get("기준", 정보["이름"][0])
    if 비교 not in 정보["이름"] or 비교 == 기준:
        비교 = 정보.get("비교", 정보["이름"][-1])
    return 기준, 비교


def 비교후보(변수: str) -> list[str]:
    """비교 구간으로 고를 수 있는 구간 (기준 구간 제외, 나쁜 조건부터)."""
    정보 = 기상구간[변수]
    기준, 기본비교 = 기준비교(변수)
    후보 = [g for g in 정보["이름"] if g != 기준]
    return 후보[::-1] if 기본비교 == 후보[-1] else 후보


def _숫자(열: pd.Series) -> pd.Series:
    return pd.to_numeric(열.astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")


def _공통정리(원본: pd.DataFrame) -> pd.DataFrame:
    표 = pd.DataFrame({
        "선박명": 원본["선박명"].astype(str).str.strip(),
        "터미널": 원본["터미널"].astype(str).str.strip(),
        "접안": pd.to_datetime(원본["접안일시"], errors="coerce"),
        "출항": pd.to_datetime(원본["출항일시"], errors="coerce"),
        "GT": _숫자(원본["총톤수"]),
        "작업량": _숫자(원본["총작업량"]),
    })
    표["체류시간"] = (표["출항"] - 표["접안"]).dt.total_seconds() / 3600
    표["연도"] = 표["접안"].dt.year.astype("Int64").astype(str)
    표["월"] = 표["접안"].dt.month.astype("Int64")
    return 표


def 자료있음() -> dict[str, bool]:
    return {"KPI1": KPI1파일.exists(), "KPI2": KPI2파일.exists()}


@st.cache_data(show_spinner="KPI 1 자료를 읽는 중...")
def KPI1자료(수정시각: float | None = None) -> pd.DataFrame:
    원본 = pd.read_csv(KPI1파일, encoding="utf-8-sig", low_memory=False)
    표 = _공통정리(원본)
    for 정보 in 기상구간.values():
        표[정보["열"]] = _숫자(원본[정보["원본열"]]) * 정보.get("배율", 1)
    return 표.loc[표["작업량"] > 0].reset_index(drop=True)


@st.cache_data(show_spinner="KPI 2 자료를 읽는 중...")
def KPI2자료(수정시각: float | None = None) -> pd.DataFrame:
    원본 = pd.read_csv(KPI2파일, encoding="utf-8-sig", low_memory=False)
    표 = _공통정리(원본)
    표["노출"] = pd.to_numeric(원본["특보노출여부"], errors="coerce").fillna(0).astype(int)
    표["노출시간"] = pd.to_numeric(원본["전체특보노출시간(h)"], errors="coerce")
    return 표.loc[표["작업량"] > 0].reset_index(drop=True)


def 불러오기() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    k1 = KPI1자료(KPI1파일.stat().st_mtime) if KPI1파일.exists() else None
    k2 = KPI2자료(KPI2파일.stat().st_mtime) if KPI2파일.exists() else None
    return k1, k2


def 거르기(표: pd.DataFrame, 기간: str = "전체", 터미널: str | None = None, 조건부: bool = False,
          월들: list[int] | None = None) -> pd.DataFrame:
    """기간(연도), 터미널, 조건부 표본, 월(접안 기준, 여러 개 가능)로 거른다. 월들이 비어 있으면 전체 월."""
    선택 = pd.Series(True, index=표.index)
    if 기간 != "전체":
        선택 &= 표["연도"] == str(기간)
    if 월들:
        선택 &= 표["월"].isin(월들)
    if 터미널:
        선택 &= 표["터미널"] == 터미널
    if 조건부:
        조건 = pd.Series(False, index=표.index)
        for 기준 in 조건부기준.values():
            조건 |= (표["터미널"].isin(기준["터미널"])
                   & 표["GT"].ge(기준["GT"][0]) & 표["GT"].lt(기준["GT"][1])
                   & 표["작업량"].between(*기준["작업량"]))
        선택 &= 조건
    return 표.loc[선택]


def 요약값(값: pd.Series) -> dict:
    값 = 값.dropna()
    return {"건수": int(len(값)),
            "중앙값": float(값.median()) if len(값) else np.nan,
            "P90": float(값.quantile(0.9)) if len(값) else np.nan}


def 터미널분포(표: pd.DataFrame) -> pd.DataFrame:
    결과 = 표.groupby("터미널")["체류시간"].agg(건수="size", 중앙값="median", P90=lambda s: s.quantile(0.9))
    return 결과.reindex([t for t in 터미널순서 if t in 결과.index]).reset_index()


# ---------------- KPI 1 ----------------
def 구간나누기(표: pd.DataFrame, 변수: str) -> pd.Series:
    정보 = 기상구간[변수]
    return pd.cut(표[정보["열"]], 정보["경계"], labels=정보["이름"], right=False)


def KPI1구간표(표: pd.DataFrame, 변수: str) -> pd.DataFrame:
    """터미널 × 기상구간별 건수·중앙값·P90 (긴 표)."""
    정보 = 기상구간[변수]
    임시 = 표.assign(구간=구간나누기(표, 변수)).dropna(subset=["구간"])
    결과 = (임시.groupby(["터미널", "구간"], observed=False)["체류시간"]
            .agg(건수="size", 중앙값="median", P90=lambda s: s.quantile(0.9)).reset_index())
    결과["구간"] = pd.Categorical(결과["구간"], 정보["이름"], ordered=True)
    결과["터미널"] = pd.Categorical(결과["터미널"], 터미널순서, ordered=True)
    return 결과.sort_values(["터미널", "구간"]).reset_index(drop=True)


def KPI1차이표(표: pd.DataFrame, 변수: str, 비교: str | None = None) -> pd.DataFrame:
    """터미널별 (비교 구간 중앙값 - 기준 구간 중앙값)."""
    기준이름, 비교이름 = 기준비교(변수, 비교)
    긴표 = KPI1구간표(표, 변수)
    행들 = []
    for 터미널, 묶음 in 긴표.groupby("터미널", observed=True):
        기준 = 묶음.loc[묶음["구간"] == 기준이름].iloc[0]
        비교 = 묶음.loc[묶음["구간"] == 비교이름].iloc[0]
        행들.append({"터미널": str(터미널), "기준건수": int(기준["건수"]), "기준중앙값": 기준["중앙값"],
                   "비교건수": int(비교["건수"]), "비교중앙값": 비교["중앙값"],
                   "차이": 비교["중앙값"] - 기준["중앙값"]})
    결과 = pd.DataFrame(행들, columns=["터미널", "기준건수", "기준중앙값", "비교건수", "비교중앙값", "차이"])
    결과["표본적음"] = (결과["기준건수"] < 적은표본) | (결과["비교건수"] < 적은표본)
    return 결과


def 빈구간사유(범위: pd.DataFrame, 전체범위: pd.DataFrame, 변수: str, 차이표: pd.DataFrame,
             비교: str | None = None) -> dict[str, dict]:
    """차이를 계산할 수 없는 터미널마다 이유를 만든다.

    범위: 지금 보고 있는 표본 (조건부 포함), 전체범위: 같은 기간의 전체 표본.
    반환: {터미널: {"짧게": 그래프용, "길게": 설명용}}
    """
    정보 = 기상구간[변수]
    단위 = 정보["단위"]
    낮을수록나쁨 = 정보.get("비교") == 정보["이름"][0]
    결과 = {}
    for 행 in 차이표.itertuples():
        if not pd.isna(행.차이):
            continue
        빈구간 = 기준비교(변수, 비교)[1] if 행.비교건수 == 0 else 기준비교(변수, 비교)[0]
        이쪽 = 범위.loc[범위["터미널"] == 행.터미널]
        전체쪽 = 전체범위.loc[전체범위["터미널"] == 행.터미널]
        전체건수 = int((구간나누기(전체쪽, 변수) == 빈구간).sum())
        값 = 전체쪽[정보["열"]].dropna()
        if 이쪽[정보["열"]].notna().sum() == 0:
            짧게, 길게, 종류, 수치 = "기상 자료 결측", f"{정보['설명']} 값이 모두 비어 있음", "결측", None
        elif 전체건수 == 0:
            극값 = 값.min() if 낮을수록나쁨 else 값.max()
            이름 = "최솟값" if 낮을수록나쁨 else "최댓값"
            짧게 = f"{빈구간} {단위} 관측 없음<br>({이름} {극값:.1f}{단위})"
            길게, 종류, 수치 = f"이 기간 {빈구간} {단위} 관측 없음 ({이름} {{수치}}{단위})", "관측없음", 극값
        else:
            짧게 = f"조건부 표본 0건<br>(전체 {전체건수:,}건)"
            길게, 종류, 수치 = f"조건부 표본에 {빈구간} {단위} 기록 없음 (전체 표본 {{수치}}건)", "조건부0건", 전체건수
        결과[행.터미널] = {"짧게": 짧게, "길게": 길게, "종류": 종류, "수치": 수치}
    return 결과


def 빈구간설명(사유: dict[str, dict]) -> str:
    """같은 이유의 터미널을 묶어 한 줄 설명으로 만든다."""
    묶음: dict[tuple, list] = {}
    for 터미널, 내용 in 사유.items():
        묶음.setdefault((내용["종류"], 내용["길게"]), []).append((터미널, 내용["수치"]))
    문장들 = []
    for (종류, 틀), 목록 in 묶음.items():
        수치들 = [v for _, v in 목록 if v is not None]
        if 수치들:
            작은, 큰 = min(수치들), max(수치들)
            if 종류 == "관측없음":
                범위글 = f"{작은:.1f}" if 작은 == 큰 else f"{작은:.1f}~{큰:.1f}"
            else:
                범위글 = f"{작은:,}" if 작은 == 큰 else f"{작은:,}~{큰:,}"
        else:
            범위글 = ""
        문장들.append(f"{'·'.join(t for t, _ in 목록)}: {틀.replace('{수치}', 범위글)}")
    return " / ".join(문장들)


def KPI1통합(표: pd.DataFrame, 변수: str, 비교: str | None = None) -> dict:
    """선택 범위 전체(터미널 통합)의 기준·비교 구간 비교."""
    정보 = 기상구간[변수]
    구간 = 구간나누기(표, 변수)
    기준이름, 비교이름 = 기준비교(변수, 비교)
    기준 = 요약값(표.loc[구간 == 기준이름, "체류시간"])
    비교 = 요약값(표.loc[구간 == 비교이름, "체류시간"])
    return {"기준": 기준, "비교": 비교, "차이": 비교["중앙값"] - 기준["중앙값"],
            "결측": int(표[정보["열"]].isna().sum()), "전체": int(len(표))}


# ---------------- KPI 2 ----------------
def KPI2차이표(표: pd.DataFrame) -> pd.DataFrame:
    결과 = 표.groupby(["터미널", "노출"])["체류시간"].agg(["size", "median"]).unstack("노출")
    결과 = 결과.reindex([t for t in 터미널순서 if t in 결과.index])
    정리 = pd.DataFrame({
        "터미널": 결과.index,
        "비노출건수": 결과.get(("size", 0), pd.Series(0, index=결과.index)).fillna(0).astype(int).values,
        "노출건수": 결과.get(("size", 1), pd.Series(0, index=결과.index)).fillna(0).astype(int).values,
        "비노출중앙값": 결과.get(("median", 0), pd.Series(np.nan, index=결과.index)).values,
        "노출중앙값": 결과.get(("median", 1), pd.Series(np.nan, index=결과.index)).values,
    })
    정리["차이"] = 정리["노출중앙값"] - 정리["비노출중앙값"]
    정리["표본적음"] = (정리["비노출건수"] < 적은표본) | (정리["노출건수"] < 적은표본)
    return 정리.reset_index(drop=True)


def KPI2통합(표: pd.DataFrame) -> dict:
    비노출 = 요약값(표.loc[표["노출"] == 0, "체류시간"])
    노출 = 요약값(표.loc[표["노출"] == 1, "체류시간"])
    return {"비노출": 비노출, "노출": 노출, "차이": 노출["중앙값"] - 비노출["중앙값"],
            "노출비율": 노출["건수"] / len(표) * 100 if len(표) else np.nan, "전체": int(len(표))}


def KPI2구성(표: pd.DataFrame) -> pd.DataFrame:
    """노출·비노출 집단의 GT·작업량 중앙값 (구성 차이 확인용)."""
    결과 = 표.groupby("노출").agg(건수=("체류시간", "size"), GT중앙값=("GT", "median"),
                              작업량중앙값=("작업량", "median"), 체류중앙값=("체류시간", "median"))
    결과.index = 결과.index.map({0: "비노출", 1: "노출"})
    return 결과.reindex(["비노출", "노출"]).reset_index(names="집단")
