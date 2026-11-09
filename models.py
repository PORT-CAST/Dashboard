"""회귀 보정 모형 — KPI별 최종 모형 하나씩 (분석 노트북과 같은 방식으로 대시보드에서 다시 적합).

KPI 1 (기상변수 구간 비교 · 기상 상황 점검): KPI1_final_multiregression 노트북 'M4_time'
  체류시간 ~ 신항더미 × (총톤수 + 총작업량 + 특보유무 + 기상변수 6개) + 월 + 요일 + 연도추세
  - 연속형 변수는 2021~2023 학습자료의 평균·표준편차로 표준화
  - 최종 계수: 2021~2024 전체 32,014건 재적합, 선박 × 14일 블록 이중 군집 공분산
KPI 2 (특보 노출): KPI2_final_multiregression 노트북 '모형 4 + 월·요일·연도추세'
  체류시간 ~ 터미널 × (총톤수 + 총작업량 + 특보유무 + 기상변수 6개) + 월 + 요일 + 연도추세
  - 기준 터미널 BPT_S, 기상변수는 학습자료 평균으로 중심화 (규모 변수는 원 단위)
  - 2021~2023 학습자료 23,557건 적합, 날짜 기준 HAC(28일) 공분산
공통 표본: 체류시간_찐최종.csv에서 결측이 하나라도 있는 행 삭제 (32,014건)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd
import statsmodels.api as sm
import streamlit as st
from scipy.stats import norm
from statsmodels.stats.sandwich_covariance import cov_cluster_2groups, cov_nw_groupsum

import kpi

기준터미널 = "BPT_S"
다른터미널 = ["PNC", "BPTC_G", "BNCT", "PNIT", "HPNT"]
기상변수 = [
    "체류시간_풍속_중앙값_mps",
    "체류시간_최대순간풍속_최댓값_mps",
    "체류시간_유의파고_중앙값_m",
    "체류시간_순간최대파고_최댓값_m",
    "체류시간_시정_최솟값_10m",
    "체류시간_시정_중앙값_10m",
]
규모변수 = ["총톤수", "총작업량"]
# KPI 1 화면의 기상변수 → 모형 변수 (모형에 없으면 None)
KPI1연결 = {
    "최대순간풍속": "체류시간_최대순간풍속_최댓값_mps",
    "풍속": "체류시간_풍속_중앙값_mps",
    "유의파고": None,              # 유의파고 최댓값은 VIF로 제외됨 (모형에는 유의파고 중앙값이 들어 있음)
    "시정": "체류시간_시정_최솟값_10m",
}
# 화면 단위 → 모형 원 단위 배율 (시정: 화면 km, 자료 10m → 1km = 100)
단위배율 = {"체류시간_시정_최솟값_10m": 100.0}

학습시작, 학습끝, 검증끝 = pd.Timestamp("2021-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")
추세기준연도 = 2021


# ---------------- 자료 정리 (두 노트북 공통) ----------------
def 자료정리(원본: pd.DataFrame) -> pd.DataFrame:
    표 = 원본.copy()
    숫자열 = ["체류시간", "총톤수", "총작업량", "체류시간_특보노출시간(h)"] + [
        c for c in 표.columns if c.startswith("체류시간_") and c != "체류시간_특보노출시간(h)"]
    for 열 in 숫자열:
        표[열] = kpi._숫자(표[열]).astype(float)
    for 열 in ["접안일시", "출항일시"]:
        표[열] = pd.to_datetime(표[열], errors="coerce")
    for 열 in ["터미널", "항만구분"]:
        표[열] = 표[열].astype(str).str.strip()
    표 = 표.replace([np.inf, -np.inf], np.nan).dropna().copy()     # 노트북과 같이 결측이 있는 행 전체 삭제
    표["신항더미"] = 표["항만구분"].map({"북항": 0.0, "신항": 1.0})
    표["특보유무"] = (표["체류시간_특보노출시간(h)"] > 0).astype(float)
    표["월"] = 표["접안일시"].dt.month
    표["요일"] = 표["접안일시"].dt.day_of_week          # 월요일 = 0
    표["연도추세"] = (표["접안일시"].dt.year - 추세기준연도).astype(float)
    return 표


def _학습(표: pd.DataFrame) -> pd.DataFrame:
    return 표.loc[(표["접안일시"] >= 학습시작) & (표["출항일시"] < 학습끝)]


def _달력(표: pd.DataFrame) -> pd.DataFrame:
    """월·요일 더미 (첫 범주 제외, 범주 고정) + 연도추세."""
    조각 = []
    for 열, 범주 in [("월", range(1, 13)), ("요일", range(7))]:
        값 = pd.Series(pd.Categorical(표[열], categories=범주), index=표.index)
        조각.append(pd.get_dummies(값, prefix=열, drop_first=True, dtype=float))
    결과 = pd.concat(조각, axis=1)
    결과["연도추세"] = 표["연도추세"].astype(float)
    return 결과


# ---------------- 모형 정의 ----------------
@dataclass
class 적합모형:
    """적합 결과 + 노트북과 같은 공분산 + 설계 정보."""
    이름: str
    짧은이름: str
    설명: str
    종류: str                       # "항만" (신항더미 상호작용) / "터미널" (터미널 상호작용)
    결과: object                     # statsmodels OLS 결과
    공분산: np.ndarray
    공분산설명: str
    적합설명: str
    설계: Callable                   # 원 단위 표 → 설계행렬
    배율: dict = field(default_factory=dict)   # 원 단위 1 → 모형 열 단위 (표준화면 1/표준편차)
    X: pd.DataFrame | None = None
    표: pd.DataFrame | None = None   # 적합 표본 (원 단위)
    신항터미널: set = field(default_factory=set)

    @property
    def params(self):
        return self.결과.params

    @property
    def nobs(self):
        return self.결과.nobs

    @property
    def rsquared(self):
        return self.결과.rsquared

    @property
    def rsquared_adj(self):
        return self.결과.rsquared_adj

    def 항(self, 변수: str, 터미널: str) -> list[tuple[str, float]]:
        """원 단위 변수 1단위 변화가 들어가는 모형 열과 배율 (주효과 + 해당 터미널/항만 상호작용)."""
        배 = self.배율.get(변수, 1.0)
        if self.종류 == "항만":
            항들 = [(변수, 배)]
            if 터미널 in self.신항터미널:
                항들.append((f"신항더미 × {변수}", 배))
            return 항들
        항들 = [(변수, 배)]
        if 터미널 != 기준터미널:
            항들.append((f"터미널_{터미널}:{변수}", 배))
        return 항들

    def 묶음이름(self, 터미널: str) -> str:
        if self.종류 == "항만":
            return "신항" if 터미널 in self.신항터미널 else "북항"
        return 터미널


def _M4_time(표: pd.DataFrame) -> 적합모형:
    학습 = _학습(표)
    연속 = 규모변수 + 기상변수
    중심, 척도 = 학습[연속].mean(), 학습[연속].std()

    def 설계(f: pd.DataFrame) -> pd.DataFrame:
        x = pd.DataFrame({"신항더미": f["신항더미"].astype(float)}, index=f.index)
        for 열 in 규모변수 + ["특보유무"] + 기상변수:
            x[열] = f[열].astype(float) if 열 == "특보유무" else (f[열] - 중심[열]) / 척도[열]
            x[f"신항더미 × {열}"] = x["신항더미"] * x[열]
        x = pd.concat([x, _달력(f)], axis=1)
        return sm.add_constant(x, has_constant="add").astype(float)

    최종 = 표.loc[(표["접안일시"] >= 학습시작) & (표["접안일시"] < 검증끝) & (표["출항일시"] < 검증끝)].copy()
    X = 설계(최종)
    결과 = sm.OLS(최종["체류시간"], X).fit()
    선박 = pd.factorize(최종["선박명"])[0]
    블록 = ((최종["접안일시"] - 학습시작).dt.days // 14).to_numpy()
    공분산, _, _ = cov_cluster_2groups(결과, 선박, 블록, use_correction=True)
    return 적합모형(
        이름="M4_time", 짧은이름="KPI 1 모형 (M4_time)",
        설명="체류시간 ~ 신항더미 × (총톤수 + 총작업량 + 특보유무 + 기상변수 6개) + 월 + 요일 + 연도추세 "
             "(KPI1_final_multiregression 노트북)",
        종류="항만", 결과=결과, 공분산=np.asarray(공분산),
        공분산설명="선박 × 14일 블록 이중 군집 공분산",
        적합설명="2021~2024년 전체 재적합 (연속형 변수는 2021~2023 학습자료 기준 표준화)",
        설계=설계, 배율={v: 1.0 / float(척도[v]) for v in 연속}, X=X, 표=최종,
        신항터미널=set(최종.loc[최종["신항더미"] == 1, "터미널"].unique()),
    )


def _모형4_달력(표: pd.DataFrame) -> 적합모형:
    학습 = _학습(표).copy()
    기상평균 = 학습[기상변수].mean()
    기본 = 규모변수 + ["특보유무"] + 기상변수

    def 설계(f: pd.DataFrame) -> pd.DataFrame:
        b = f[기본].astype(float).copy()
        b[기상변수] = b[기상변수] - 기상평균
        값 = {"const": pd.Series(1.0, index=f.index)}
        for t in 다른터미널:
            값[f"터미널_{t}"] = (f["터미널"] == t).astype(float)
        값.update({c: b[c] for c in 기본})
        for t in 다른터미널:
            for c in 기본:
                값[f"터미널_{t}:{c}"] = 값[f"터미널_{t}"] * b[c]
        X = pd.DataFrame(값, index=f.index, dtype=float)
        return pd.concat([X, _달력(f)], axis=1)

    X = 설계(학습)
    결과 = sm.OLS(학습["체류시간"], X).fit()
    날짜 = pd.DatetimeIndex(학습["접안일시"]).normalize()
    날번호 = (날짜 - 날짜.min()).days.to_numpy(dtype=int)
    공분산 = np.asarray(cov_nw_groupsum(결과, nlags=28, time=날번호, use_correction=False))
    return 적합모형(
        이름="모형 4 + 월·요일·연도추세", 짧은이름="KPI 2 모형 (모형 4 + 월·요일·연도추세)",
        설명="체류시간 ~ 터미널 × (총톤수 + 총작업량 + 특보유무 + 기상변수 6개) + 월 + 요일 + 연도추세 "
             "(KPI2_final_multiregression 노트북)",
        종류="터미널", 결과=결과, 공분산=공분산,
        공분산설명="날짜 기준 HAC(28일) 공분산",
        적합설명="2021~2023년 학습자료로 적합 (2024년은 검증용)",
        설계=설계, X=X, 표=학습,
    )


모형목록: dict[str, Callable] = {"KPI1": _M4_time, "KPI2": _모형4_달력}
모형이름 = {"KPI1": "M4_time", "KPI2": "모형 4 + 월·요일·연도추세"}


@st.cache_resource(show_spinner="회귀 모형을 적합하는 중...")
def 적합(KPI: str, 수정시각: float | None = None):
    """(적합모형, 표본 DataFrame, 독립변수 목록)"""
    원본 = pd.read_csv(kpi.KPI1파일, encoding="utf-8-sig", low_memory=False)
    모형 = 모형목록[KPI](자료정리(원본))
    return 모형, 모형.표, [c for c in 모형.X.columns if c != "const"]


def 불러오기(KPI: str = "KPI1"):
    if not kpi.KPI1파일.exists():
        return None
    return 적합(KPI, kpi.KPI1파일.stat().st_mtime)


def _대비(모형: 적합모형, 가중: dict[str, float]) -> dict:
    """선형결합 c'β 의 효과와 노트북 공분산 기반 95% 정규 근사 구간."""
    c = pd.Series(0.0, index=모형.params.index)
    for 이름, 값 in 가중.items():
        c[이름] += 값
    c = c.to_numpy()
    효과 = float(c @ 모형.params.to_numpy())
    분산 = float(c @ 모형.공분산 @ c)
    se = np.sqrt(분산) if 분산 > 0 else np.nan
    z = norm.ppf(0.975)
    p = float(2 * norm.sf(abs(효과 / se))) if se and se > 0 else np.nan
    return {"효과": 효과, "하한": 효과 - z * se, "상한": 효과 + z * se, "p값": p}


def _가중(모형: 적합모형, 차이들: dict[str, float], 터미널: str) -> dict[str, float]:
    """원 단위 변화량 {변수: 차이} → 모형 열 가중치."""
    가중: dict[str, float] = {}
    for 변수, 차 in 차이들.items():
        for 열, 배 in 모형.항(변수, 터미널):
            가중[열] = 가중.get(열, 0.0) + 차 * 배
    return 가중


def 특보효과(모형: 적합모형) -> pd.DataFrame:
    """터미널별 특보 노출 보정 효과 (다른 변수가 같을 때 노출 − 비노출, 시간)."""
    return pd.DataFrame([{"터미널": t, **_대비(모형, _가중(모형, {"특보유무": 1.0}, t))} for t in kpi.터미널순서])


def 기상효과(모형: 적합모형, 모형변수: str, 차이: float, 터미널: str) -> dict:
    """한 터미널에서 모형변수가 원 단위로 '차이'만큼 달라질 때의 보정 효과 (나머지 변수는 같다고 가정)."""
    return _대비(모형, _가중(모형, {모형변수: 차이}, 터미널))


def KPI1보정표(결과, 차이표: pd.DataFrame, 범위: pd.DataFrame, 변수: str, 비교: str | None) -> pd.DataFrame | None:
    """KPI 1 화면의 (기준 구간 → 비교 구간) 이동을 모형 효과로 바꾼다.

    두 구간의 대표값 = 해당 터미널·구간 기록의 기상값 중앙값. 효과 = 기울기 × (비교 대표값 − 기준 대표값).
    모형에 없는 변수면 None.
    """
    모형변수 = KPI1연결.get(변수)
    if 모형변수 is None:
        return None
    기준이름, 비교이름 = kpi.기준비교(변수, 비교)
    열 = kpi.기상구간[변수]["열"]
    구간 = kpi.구간나누기(범위, 변수)
    배율 = 단위배율.get(모형변수, 1.0)
    행들 = []
    for t in 차이표["터미널"]:
        이쪽 = 범위["터미널"] == t
        기준값 = 범위.loc[이쪽 & (구간 == 기준이름), 열].median()
        비교값 = 범위.loc[이쪽 & (구간 == 비교이름), 열].median()
        if pd.isna(기준값) or pd.isna(비교값):
            행들.append({"터미널": t, "기준대표값": 기준값, "비교대표값": 비교값,
                       "효과": np.nan, "하한": np.nan, "상한": np.nan, "p값": np.nan})
            continue
        효과 = 기상효과(결과, 모형변수, (비교값 - 기준값) * 배율, t)
        행들.append({"터미널": t, "기준대표값": 기준값, "비교대표값": 비교값, **효과})
    return pd.DataFrame(행들, columns=["터미널", "기준대표값", "비교대표값", "효과", "하한", "상한", "p값"])



# ---------------- 기상 상황 점검: 시나리오 ----------------
# 시나리오 = 과거 기록 중 조건에 맞는 기록들의 기상값 6개 중앙값 (터미널별). 짝 변수가 함께 움직여 현실적인 조합이 된다.
_돌풍, _파고, _시정, _특보시간 = ("체류시간_최대순간풍속_최댓값_mps", "체류시간_순간최대파고_최댓값_m",
                           "체류시간_시정_최솟값_10m", "체류시간_특보노출시간(h)")
시나리오정의 = {
    "평온": {"설명": "돌풍 5m/s 미만 · 최대파고 1m 미만 · 시정 10km 이상 · 특보 없음", "아이콘": "sunny",
           "조건": lambda 표: (표[_돌풍] < 5) & (표[_파고] < 1) & (표[_시정] >= 1000) & (표[_특보시간] == 0)},
    "강풍": {"설명": "체류 중 돌풍 최댓값 9m/s 이상", "아이콘": "air",
           "조건": lambda 표: 표[_돌풍] >= 9},
    "높은 파도": {"설명": "체류 중 순간최대파고 최댓값 2m 이상", "아이콘": "waves",
              "조건": lambda 표: 표[_파고] >= 2},
    "저시정": {"설명": "체류 중 시정 최솟값 1km 미만", "아이콘": "foggy",
            "조건": lambda 표: 표[_시정] < 100},
    "폭풍급": {"설명": "돌풍 9m/s 이상 그리고 최대파고 2m 이상", "아이콘": "thunderstorm",
            "조건": lambda 표: (표[_돌풍] >= 9) & (표[_파고] >= 2)},
}
기준시나리오 = "평온"
기상이름 = {
    "체류시간_풍속_중앙값_mps": ("풍속 중앙값", "m/s", 1.0),
    "체류시간_최대순간풍속_최댓값_mps": ("돌풍 최댓값", "m/s", 1.0),
    "체류시간_유의파고_중앙값_m": ("유의파고 중앙값", "m", 1.0),
    "체류시간_순간최대파고_최댓값_m": ("순간최대파고 최댓값", "m", 1.0),
    "체류시간_시정_최솟값_10m": ("시정 최솟값", "km", 0.01),
    "체류시간_시정_중앙값_10m": ("시정 중앙값", "km", 0.01),
}


def 시나리오프로필(표: pd.DataFrame) -> pd.DataFrame:
    """터미널 × 시나리오별 기상값 6개 중앙값과 근거 기록 수 (긴 표)."""
    행들 = []
    for t in kpi.터미널순서:
        이쪽 = 표.loc[표["터미널"] == t]
        for 이름, 정의 in 시나리오정의.items():
            맞음 = 이쪽.loc[정의["조건"](이쪽)]
            행 = {"터미널": t, "시나리오": 이름, "건수": int(len(맞음))}
            for v in 기상변수:
                행[v] = 맞음[f"{v}"].median()
            행들.append(행)
    return pd.DataFrame(행들)


def 시나리오효과(모형, 프로필: pd.DataFrame, 터미널: str, 시나리오: str, 특보: bool = False) -> dict:
    """같은 선박(규모·작업량 동일)이 평온 대신 이 시나리오를 겪을 때의 체류시간 차이 (시간, 95% CI)."""
    기준 = 프로필.set_index(["터미널", "시나리오"]).loc[(터미널, 기준시나리오)]
    대상 = 프로필.set_index(["터미널", "시나리오"]).loc[(터미널, 시나리오)]
    차이들 = {v: float(대상[v] - 기준[v]) for v in 기상변수}
    if 특보:
        차이들["특보유무"] = 1.0
    가중 = _가중(모형, 차이들, 터미널)
    if not any(abs(x) > 1e-12 for x in 가중.values()):
        return {"효과": 0.0, "하한": 0.0, "상한": 0.0, "p값": np.nan}
    return _대비(모형, 가중)


def 예상체류(모형, 표: pd.DataFrame, 프로필: pd.DataFrame, 터미널: str, 시나리오: str, 특보: bool = False) -> float:
    값 = 프로필.set_index(["터미널", "시나리오"]).loc[(터미널, 시나리오)]
    return 예상체류값(모형, 표, 터미널, {v: float(값[v]) for v in 기상변수}, 특보)


# ---------------- 기상 상황 점검: 슬라이더 (변수별 직접 조절) ----------------
# 화면 단위 슬라이더 범위: (최소, 최대, 간격). 관측 최댓값을 조금 넘는 데까지.
슬라이더범위 = {
    "체류시간_풍속_중앙값_mps": (0.0, 10.0, 0.1),
    "체류시간_최대순간풍속_최댓값_mps": (0.0, 20.0, 0.1),
    "체류시간_유의파고_중앙값_m": (0.0, 3.0, 0.1),
    "체류시간_순간최대파고_최댓값_m": (0.0, 8.0, 0.1),
    "체류시간_시정_최솟값_10m": (0.0, 50.0, 0.1),
    "체류시간_시정_중앙값_10m": (0.0, 50.0, 0.1),
}
# 물리적으로 함께 성립해야 하는 관계 (작은쪽, 큰쪽, 안내문)
관계점검 = [
    ("체류시간_풍속_중앙값_mps", "체류시간_최대순간풍속_최댓값_mps", "돌풍 최댓값이 풍속 중앙값보다 작습니다"),
    ("체류시간_유의파고_중앙값_m", "체류시간_순간최대파고_최댓값_m", "순간최대파고 최댓값이 유의파고 중앙값보다 작습니다"),
    ("체류시간_시정_최솟값_10m", "체류시간_시정_중앙값_10m", "시정 최솟값이 시정 중앙값보다 큽니다"),
]


def 입력점검(값들: dict[str, float]) -> list[str]:
    """모형 단위의 여섯 기상값과 변수 간 물리 관계를 확인한다."""
    if any(v not in 값들 or not np.isfinite(값들[v]) or 값들[v] < 0 for v in 기상변수):
        return ["기상값은 결측 없이 0 이상의 유한한 값이어야 합니다."]
    return [설명 for 작은, 큰, 설명 in 관계점검 if 값들[작은] > 값들[큰] + 1e-9]


def 화면값(v: str, 모형값: float) -> float:
    return 모형값 * 기상이름[v][2]


def 모형값(v: str, 화면값_: float) -> float:
    return 화면값_ / 기상이름[v][2]


def 기울기(모형, 터미널: str) -> dict[str, float]:
    """터미널별 기상변수 원 단위 1당 체류시간 변화와 특보 효과."""
    p = 모형.params
    return {v: float(sum(p[열] * 배 for 열, 배 in 모형.항(v, 터미널))) for v in 기상변수 + ["특보유무"]}


def 평온기준(표: pd.DataFrame, 프로필: pd.DataFrame, 터미널: str) -> dict[str, float]:
    """터미널의 평온 기준값: 극값 3개는 평온 기록의 중앙값, 짝 변수 3개는 그 극값에서의 예측값 (슬라이더와 같은 방식)."""
    평온 = 프로필.set_index(["터미널", "시나리오"]).loc[(터미널, 기준시나리오)]
    값 = {v: float(평온[v]) for v in 기상변수}
    for _, _, 주, 종, 관계 in 짝변수:
        값[종] = 조건예측(표, 주, 종, 값[주], 관계)
    return 값


def 조절효과(모형, 프로필: pd.DataFrame, 터미널: str, 값들: dict[str, float], 특보: bool,
          평온: dict[str, float] | None = None) -> dict:
    """설정값(원 단위)이 그 터미널 평온 값과 다를 때의 체류시간 차이 (95% CI) + 변수별 기여."""
    문제 = 입력점검(값들)
    if 문제:
        raise ValueError(" · ".join(문제))
    if 평온 is None:
        평온 = 프로필.set_index(["터미널", "시나리오"]).loc[(터미널, 기준시나리오)]
    기 = 기울기(모형, 터미널)
    차이들 = {v: float(값들[v] - 평온[v]) for v in 기상변수}
    기여 = {v: 기[v] * 차 for v, 차 in 차이들.items()}
    if 특보:
        차이들["특보유무"] = 1.0
        기여["특보유무"] = 기["특보유무"]
    가중 = _가중(모형, 차이들, 터미널)
    전체 = (_대비(모형, 가중) if any(abs(x) > 1e-12 for x in 가중.values())
          else {"효과": 0.0, "하한": 0.0, "상한": 0.0, "p값": np.nan})
    return {**전체, "기여": 기여}


def 예상체류값(모형, 표: pd.DataFrame, 터미널: str, 값들: dict[str, float], 특보: bool) -> float:
    """그 터미널 보통 선박(총톤수·총작업량 중앙값)의 모형 예상 체류시간.

    월·요일·연도추세 항은 그 터미널 적합 표본의 평균값(기간 평균 달력)으로 고정한다.
    """
    이쪽 = 표.loc[표["터미널"] == 터미널]
    행 = 이쪽.iloc[[0]].copy()
    행["총톤수"], 행["총작업량"] = 이쪽["총톤수"].median(), 이쪽["총작업량"].median()
    행["특보유무"] = 1.0 if 특보 else 0.0
    for v in 기상변수:
        행[v] = float(값들[v])
    x = 모형.설계(행).iloc[0]
    달력열 = [c for c in 모형.X.columns if c.startswith(("월_", "요일_")) or c == "연도추세"]
    x[달력열] = 모형.X.loc[이쪽.index, 달력열].mean()
    return float(np.dot(모형.params.to_numpy(), x[모형.params.index].to_numpy()))


@st.cache_data(show_spinner=False)
def _마할라노비스준비(_표: pd.DataFrame, 키: str):
    값 = _표[[f"{v}" for v in 기상변수]].to_numpy(dtype=float)
    평균 = 값.mean(axis=0)
    역 = np.linalg.pinv(np.cov(값, rowvar=False))
    차 = 값 - 평균
    거리 = np.einsum("ij,jk,ik->i", 차, 역, 차)
    return 평균, 역, np.sort(거리)


def 드문정도(표: pd.DataFrame, 값들: dict[str, float]) -> float:
    """이 6개 기상값 조합보다 '더 평범하지 않은' 과거 기록의 비율(%). 작을수록 드문 조합."""
    평균, 역, 정렬거리 = _마할라노비스준비(표, f"{len(표)}")
    x = np.array([값들[v] for v in 기상변수], dtype=float) - 평균
    d = float(x @ 역 @ x)
    return float((len(정렬거리) - np.searchsorted(정렬거리, d)) / len(정렬거리) * 100)


# 짝 변수: 먼저 정하는 변수(최댓값·최솟값) → 범위가 맞춰지는 변수(중앙값)
짝변수 = [
    ("바람", "air", "체류시간_최대순간풍속_최댓값_mps", "체류시간_풍속_중앙값_mps", "le"),   # 풍속 중앙값 ≤ 돌풍 최댓값
    ("파도", "waves", "체류시간_순간최대파고_최댓값_m", "체류시간_유의파고_중앙값_m", "le"),  # 유의파고 중앙값 ≤ 최대파고
    ("시정", "visibility", "체류시간_시정_최솟값_10m", "체류시간_시정_중앙값_10m", "ge"),    # 시정 중앙값 ≥ 시정 최솟값
]
# 먼저 정하는 변수의 슬라이더 범위 (화면 단위): 관측 기록이 충분한 데까지
주변수범위 = {
    "체류시간_최대순간풍속_최댓값_mps": (0.0, 15.0, 0.1),
    "체류시간_순간최대파고_최댓값_m": (0.0, 5.5, 0.1),
    "체류시간_시정_최솟값_10m": (0.0, 50.0, 0.1),
}


def _가까운쌍(표: pd.DataFrame, 주: str, 종: str, 주값: float, 이웃: int) -> np.ndarray:
    """절대거리 순으로 선택한다. 같은 거리에서는 원래 행 순서를 유지한다."""
    쌍 = 표[[주, 종]].replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    if len(쌍) == 0 or 이웃 < 1 or not np.isfinite(주값):
        raise ValueError("기상값 보완에 사용할 유효한 기록과 입력값이 필요합니다.")
    순서 = np.argsort(np.abs(쌍[:, 0] - 주값), kind="stable")[:이웃]
    return 쌍[순서]


def 조건예측(표: pd.DataFrame, 주: str, 종: str, 주값: float, 관계: str, 이웃: int = 400) -> float:
    """주 변수가 주값(모형 단위)일 때 종 변수의 예측값 = 가장 가까운 과거 기록 '이웃'건의 중앙값 (물리 관계 적용)."""
    주변 = _가까운쌍(표, 주, 종, 주값, 이웃)
    값 = float(np.median(주변[:, 1]))
    return min(값, 주값) if 관계 == "le" else max(값, 주값)


def 조건범위(표: pd.DataFrame, 주: str, 종: str, 주값: float, 관계: str, 이웃: int = 400) -> tuple[float, float]:
    """주 변수가 주값(모형 단위)일 때, 과거 기록에서 종 변수가 나타난 범위 (1~99 백분위, 모형 단위).

    주값과 가장 가까운 기록 '이웃'건으로 계산하고, 물리적 관계(le: 종 ≤ 주, ge: 종 ≥ 주)를 함께 적용한다.
    """
    주변 = _가까운쌍(표, 주, 종, 주값, 이웃)[:, 1]
    아래, 위 = float(np.quantile(주변, 0.01)), float(np.quantile(주변, 0.99))
    if 관계 == "le":
        위 = min(위, 주값)
    else:
        아래 = max(아래, 주값)
    if 위 < 아래:
        아래 = 위 = (주값 if 관계 == "le" else 주값)
    return 아래, 위
