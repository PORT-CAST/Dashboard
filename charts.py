"""대시보드 그래프 (plotly).

색 역할 (흰 배경 기준 색각 이상·대비 검사 통과)
- 기준 집단(기준 기상구간, 비노출): 파랑 #5A86C6
- 비교 집단(높은 기상구간, 특보 노출): 주황 #D9732A
- 전체 표본 / 조건부 표본 비교: 보라 #8A6BC4 / 청록 #2A9D8F
- 단일 계열(차이, 중앙값): 남색 #2F5D9E,  기상구간 순서: 파랑 단색 밝음→어두움
표본이 적은 막대(10건 미만)는 빗금으로 표시한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

기준색, 비교색 = "#5A86C6", "#D9732A"
전체색, 조건부색 = "#8A6BC4", "#2A9D8F"
단일색 = "#2F5D9E"
구간색 = ["#B7CBE9", "#86A8DA", "#5A86C6", "#2F5D9E"]
글자, 보조글자, 격자 = "#1B2433", "#5B6780", "#ECE8E6"
설정 = {"displayModeBar": False, "responsive": True}


def _틀(그림: go.Figure, 높이: int, y제목: str = "시간", 범례: bool = False) -> go.Figure:
    그림.update_layout(
        height=높이, margin=dict(l=8, r=8, t=8 if not 범례 else 36, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Pretendard Variable, Pretendard, sans-serif", size=13, color=글자),
        bargap=0.35, bargroupgap=0.08, showlegend=범례,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(color=보조글자)),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=격자, font=dict(color=글자)),
    )
    그림.update_xaxes(showgrid=False, linecolor=격자, tickfont=dict(color=보조글자))
    그림.update_yaxes(title=dict(text=y제목, font=dict(color=보조글자, size=12)), gridcolor=격자,
                    zerolinecolor="#C9C2BF", tickfont=dict(color=보조글자))
    return 그림


def _빗금(적음: pd.Series) -> dict:
    # overlay: 막대 색은 그대로 두고 흰 빗금만 덧그린다
    return dict(shape=["/" if x else "" for x in 적음], fillmode="overlay", fgcolor="#FFFFFF", size=7, solidity=0.45)


def _부호(값: float) -> str:
    return "-" if pd.isna(값) else f"{값:+.1f}h"


def 차이막대(표: pd.DataFrame, 기준이름: str, 비교이름: str, 높이: int = 320,
            사유: dict | None = None) -> go.Figure:
    """터미널별 증가량(비교 - 기준). 표: 터미널, 기준건수, 비교건수, 차이, 표본적음 (+ 기준중앙값, 비교중앙값)."""
    기준건수 = 표.get("기준건수", 표.get("비노출건수"))
    비교건수 = 표.get("비교건수", 표.get("노출건수"))
    글들 = [f"{_부호(d)}<br><span style='font-size:11px'>n {a:,}·{b:,}</span>"
          for d, a, b in zip(표["차이"], 기준건수, 비교건수)]
    그림 = go.Figure(go.Bar(
        x=표["터미널"], y=표["차이"], marker=dict(color=단일색, cornerradius=4, pattern=_빗금(표["표본적음"])),
        text=글들, textposition="outside", textfont=dict(color=글자), cliponaxis=False,
        customdata=np.stack([기준건수, 비교건수, 표["표본적음"].map({True: "표본 적음(10건 미만)", False: ""})], axis=1),
        hovertemplate=(f"<b>%{{x}}</b><br>차이 %{{y:+.1f}}시간<br>{기준이름} %{{customdata[0]:,}}건 · "
                       f"{비교이름} %{{customdata[1]:,}}건<br>%{{customdata[2]}}<extra></extra>"),
    ))
    값 = 표["차이"].to_numpy(dtype=float)
    최대 = np.nanmax(np.abs(값)) if np.isfinite(값).any() else 1
    최소 = np.nanmin(값) if np.isfinite(값).any() else 0
    # 차이를 계산할 수 없는 터미널(한쪽 구간 0건)은 빈칸 대신 안내 글자를 표시
    for 터, d, a, b in zip(표["터미널"], 표["차이"], 기준건수, 비교건수):
        if pd.isna(d):
            글 = (사유 or {}).get(터, {}).get("짧게") or f"자료 없음<br>({비교이름 if b == 0 else 기준이름} 0건)"
            그림.add_annotation(x=터, y=0, yshift=16, showarrow=False, font=dict(size=11, color=보조글자), text=글)
    그림.update_yaxes(range=[min(0, 최소 * 1.4), 최대 * 1.45 if 최대 > 0 else 1])
    return _틀(그림, 높이, "중앙값 차이 (시간)")


def 두집단막대(표: pd.DataFrame, 기준이름: str, 비교이름: str, 높이: int = 320) -> go.Figure:
    """터미널별 두 집단의 체류시간 중앙값을 나란히."""
    기준열, 비교열 = ("기준중앙값", "비교중앙값") if "기준중앙값" in 표 else ("비노출중앙값", "노출중앙값")
    기준건수열, 비교건수열 = ("기준건수", "비교건수") if "기준건수" in 표 else ("비노출건수", "노출건수")
    그림 = go.Figure()
    for 이름, 열, 건수열, 색 in [(기준이름, 기준열, 기준건수열, 기준색), (비교이름, 비교열, 비교건수열, 비교색)]:
        적음 = 표[건수열] < 10
        그림.add_bar(x=표["터미널"], y=표[열], name=이름,
                   marker=dict(color=색, cornerradius=4, pattern=_빗금(적음), line=dict(color="#FFFFFF", width=2)),
                   customdata=표[건수열], hovertemplate=f"<b>%{{x}}</b> · {이름}<br>중앙값 %{{y:.1f}}시간<br>%{{customdata:,}}건<extra></extra>")
    return _틀(그림, 높이, "체류시간 중앙값 (시간)", 범례=True)


def 구간막대(표: pd.DataFrame, 단위: str, 높이: int = 300, 낮을수록나쁨: bool = False) -> go.Figure:
    """기상구간별 체류시간 중앙값 (선택 범위 통합). 표: 구간, 건수, 중앙값.
    색은 나쁜 조건일수록 진하게 (시정처럼 낮을수록 나쁘면 순서를 뒤집는다)."""
    색들 = 구간색[-len(표):] if len(표) <= len(구간색) else 구간색
    if 낮을수록나쁨:
        색들 = 색들[::-1]
    글들 = [f"{m:.1f}h<br><span style='font-size:11px'>n {n:,}</span>" if n else "자료 없음"
          for m, n in zip(표["중앙값"], 표["건수"])]
    그림 = go.Figure(go.Bar(
        x=[f"{g} {단위}" for g in 표["구간"]], y=표["중앙값"], text=글들, textposition="outside", cliponaxis=False,
        marker=dict(color=색들, cornerradius=4, pattern=_빗금(표["건수"] < 10)), textfont=dict(color=글자),
        customdata=np.stack([표["건수"], 표["P90"]], axis=1),
        hovertemplate="<b>%{x}</b><br>중앙값 %{y:.1f}시간 · P90 %{customdata[1]:.1f}시간<br>%{customdata[0]:,}건<extra></extra>",
    ))
    최대 = np.nanmax(표["중앙값"].to_numpy(dtype=float)) if 표["건수"].sum() else 1
    그림.update_yaxes(range=[0, 최대 * 1.3])
    return _틀(그림, 높이, "체류시간 중앙값 (시간)")


def 표본비교막대(전체: pd.DataFrame, 조건부: pd.DataFrame, 높이: int = 320) -> go.Figure:
    """KPI 2: 전체 표본과 조건부 표본의 터미널별 차이."""
    그림 = go.Figure()
    for 이름, 표, 색 in [("전체 표본", 전체, 전체색), ("조건부 표본 (GT·작업량 범위)", 조건부, 조건부색)]:
        그림.add_bar(x=표["터미널"], y=표["차이"], name=이름,
                   marker=dict(color=색, cornerradius=4, pattern=_빗금(표["표본적음"]), line=dict(color="#FFFFFF", width=2)),
                   customdata=np.stack([표["비노출건수"], 표["노출건수"]], axis=1),
                   hovertemplate=(f"<b>%{{x}}</b> · {이름}<br>차이 %{{y:+.1f}}시간<br>"
                                  "비노출 %{customdata[0]:,}건 · 노출 %{customdata[1]:,}건<extra></extra>"))
    return _틀(그림, 높이, "노출 − 비노출 중앙값 (시간)", 범례=True)


def 터미널분포막대(표: pd.DataFrame, 높이: int = 300) -> go.Figure:
    """터미널별 체류시간 중앙값(막대)과 P90(점)."""
    그림 = go.Figure()
    그림.add_bar(x=표["터미널"], y=표["중앙값"], name="중앙값", marker=dict(color=기준색, cornerradius=4),
               customdata=표["건수"], hovertemplate="<b>%{x}</b><br>중앙값 %{y:.1f}시간<br>%{customdata:,}건<extra></extra>")
    그림.add_scatter(x=표["터미널"], y=표["P90"], name="P90 (상위 10% 경계)", mode="markers",
                   marker=dict(symbol="diamond", size=11, color=비교색, line=dict(color="#FFFFFF", width=2)),
                   hovertemplate="<b>%{x}</b><br>P90 %{y:.1f}시간<extra></extra>")
    return _틀(그림, 높이, "체류시간 (시간)", 범례=True)


보정색 = "#C27C0E"   # 회귀 보정 효과 (보라·청록과 함께 색각 이상 검사 통과)


def 보정비교막대(계열들: list[dict], 높이: int = 340, y제목: str = "증가량 (시간)") -> go.Figure:
    """터미널별 여러 계열(단순 차이, 조건부, 회귀 보정)을 나란히.

    계열 = {"이름", "표"(터미널·값 열), "값열", "색", "하한열"/"상한열"(선택, 신뢰구간), "적음열"(선택, 빗금), "건수글"(선택)}
    """
    그림 = go.Figure()
    for 계열 in 계열들:
        표 = 계열["표"]
        값 = 표[계열["값열"]]
        오차 = None
        if 계열.get("하한열"):
            오차 = dict(type="data", symmetric=False, array=(표[계열["상한열"]] - 값).to_numpy(),
                      arrayminus=(값 - 표[계열["하한열"]]).to_numpy(), color="#5B6780", thickness=1.4, width=4)
        적음 = 표[계열["적음열"]] if 계열.get("적음열") else pd.Series(False, index=표.index)
        글 = 계열.get("건수글")
        그림.add_bar(
            x=표["터미널"], y=값, name=계열["이름"], error_y=오차,
            marker=dict(color=계열["색"], cornerradius=4, pattern=_빗금(적음), line=dict(color="#FFFFFF", width=2)),
            customdata=np.stack([글 if 글 is not None else [""] * len(표),
                                 표[계열["하한열"]] if 계열.get("하한열") else [np.nan] * len(표),
                                 표[계열["상한열"]] if 계열.get("상한열") else [np.nan] * len(표)], axis=1),
            hovertemplate=(f"<b>%{{x}}</b> · {계열['이름']}<br>%{{y:+.1f}}시간"
                           + ("<br>95% 신뢰구간 %{customdata[1]:+.1f} ~ %{customdata[2]:+.1f}" if 계열.get("하한열") else "")
                           + "<br>%{customdata[0]}<extra></extra>"),
        )
    return _틀(그림, 높이, y제목, 범례=True)



def 시나리오막대(표: pd.DataFrame, 주의: float, 위험: float, 선택: str | None = None, 높이: int = 340) -> go.Figure:
    """터미널별 평온 대비 예상 증가량(95% 신뢰구간)과 주의·위험 경계선. 표: 터미널, 효과, 하한, 상한, 단계, 건수."""
    투명 = [1.0 if (선택 is None or t == 선택) else 0.35 for t in 표["터미널"]]
    그림 = go.Figure(go.Bar(
        x=표["터미널"], y=표["효과"],
        marker=dict(color=보정색, opacity=투명, cornerradius=4),
        error_y=dict(type="data", symmetric=False, array=(표["상한"] - 표["효과"]).to_numpy(),
                     arrayminus=(표["효과"] - 표["하한"]).to_numpy(), color="#5B6780", thickness=1.4, width=4),
        customdata=np.stack([표["하한"], 표["상한"], 표["단계"], 표["건수"]], axis=1),
        hovertemplate=("<b>%{x}</b><br>평온 대비 %{y:+.1f}시간 (%{customdata[2]})<br>"
                       "95% 신뢰구간 %{customdata[0]:+.1f} ~ %{customdata[1]:+.1f}<br>%{customdata[3]}<extra></extra>"),
    ))
    # 값 글자는 신뢰구간 위쪽 끝에 둔다 (막대·오차선과 겹치지 않게)
    for t, v, 위, 단계 in zip(표["터미널"], 표["효과"], 표["상한"], 표["단계"]):
        그림.add_annotation(x=t, y=위, yshift=12, showarrow=False, text=f"<b>{v:+.1f}h</b> · {단계}",
                          font=dict(size=12, color=글자), bgcolor="rgba(255,255,255,0.9)", borderpad=2)
    # 경계선 이름은 그래프 오른쪽 바깥에
    for 값, 이름 in [(주의, "주의"), (위험, "위험")]:
        그림.add_hline(y=값, line=dict(color="#8A8F99", width=1.2, dash="dash"))
        그림.add_annotation(xref="paper", x=1.0, xanchor="left", y=값, showarrow=False, xshift=6,
                          text=f"{이름} {값:g}h", font=dict(size=11, color=보조글자))
    최대 = max(float(np.nanmax(표["상한"])) if len(표) else 0, 위험) * 1.25
    그림.update_yaxes(range=[min(0, float(np.nanmin(표["하한"])) * 1.2), 최대])
    그림 = _틀(그림, 높이, "평온 대비 예상 증가량 (시간)")
    그림.update_layout(margin=dict(r=62))
    return 그림


증가색, 감소색 = "#C27C0E", "#5A86C6"   # 기여도: 늘리는 쪽 / 줄이는 쪽 (색각 이상 검사 통과)


def 기여도막대(표: pd.DataFrame, 높이: int = 300) -> go.Figure:
    """변수별 기여(시간) 가로 막대. 표: 이름, 기여, 설명(평온→현재 값)."""
    표 = 표.iloc[::-1]
    그림 = go.Figure(go.Bar(
        y=표["이름"], x=표["기여"], orientation="h",
        marker=dict(color=[증가색 if v >= 0 else 감소색 for v in 표["기여"]], cornerradius=4),
        text=[f"{v:+.1f}h" for v in 표["기여"]], textposition="outside", cliponaxis=False,
        textfont=dict(color=글자), customdata=표["설명"],
        hovertemplate="<b>%{y}</b><br>%{customdata}<br>체류시간 %{x:+.2f}시간<extra></extra>",
    ))
    최대 = max(float(np.abs(표["기여"]).max()) if len(표) else 1, 0.5) * 1.35
    그림.update_xaxes(range=[-최대, 최대], zeroline=True, zerolinecolor="#9AA3B2", zerolinewidth=1.5,
                    title=dict(text="평온 대비 체류시간 변화 (시간)", font=dict(color=보조글자, size=12)), showgrid=True,
                    gridcolor=격자)
    그림 = _틀(그림, 높이, "")
    그림.update_yaxes(gridcolor="rgba(0,0,0,0)", title=None)
    그림.update_layout(bargap=0.4, margin=dict(l=8, r=40, t=8, b=8))
    return 그림
