"""터미널 위치 개념도. 터미널을 누르면 그 터미널만 색이 들어오고 파이썬으로 선택값을 보낸다.

좌표는 화면 배치용이며 실제 지형과 축척이 아니다.
신항은 부두 번호 순서(1, 2, 4, 5부두), 북항은 감만, 신선대 순서로 놓았다.
"""
import streamlit as st

_CSS = """
:host {display:block}
svg {display:block;width:100%;height:auto}
.sea {fill:#E7ECF4}
.land {fill:#F6F2F1}
.quay {fill:#CABAB7}
.area {font-size:15px;font-weight:700;fill:#042653}
.t {cursor:pointer;outline:none}
.t rect {fill:#FFFFFF;stroke:#042653;stroke-opacity:.2;stroke-width:1;transition:fill .15s,opacity .15s}
.t .c {font-size:14px;font-weight:700;fill:#042653;text-anchor:middle;transition:opacity .15s}
.t .s {font-size:12px;fill:#5B6780;text-anchor:middle;transition:opacity .15s}
.t:hover rect, .t:focus-visible rect {stroke:#F9A657;stroke-opacity:1;stroke-width:2}
.picked .t:not(.on) rect {fill:#F1EFEE}
.picked .t:not(.on) text {opacity:.65}
.t.on rect {fill:#F9A657;stroke:#021D4C;stroke-opacity:1;stroke-width:1.5}
.t.on .c, .t.on .s {fill:#021D4C}
"""

_JS = """
const 터미널 = [
  ['PNIT', '1부두', 16], ['PNC', '2부두', 86], ['HPNT', '4부두', 156], ['BNCT', '5부두', 226],
  ['BPTC_G', '감만', 348], ['BPT_S', '신선대', 430],
];
const 칸 = ([코드, 설명, x]) => {
  const 폭 = x > 300 ? 76 : 64;
  return `<g class="t" data-t="${코드}" role="button" tabindex="0" aria-label="${코드} ${설명}">
    <rect x="${x}" y="84" width="${폭}" height="60" rx="10"></rect>
    <text class="c" x="${x + 폭 / 2}" y="110">${코드}</text>
    <text class="s" x="${x + 폭 / 2}" y="129">${설명}</text></g>`;
};
const 그림 = `<svg viewBox="0 -30 530 194" role="group" aria-label="터미널 선택 지도">
  <rect class="sea" y="-30" width="530" height="194" rx="12"></rect>
  <rect class="land" y="-30" width="530" height="60" rx="12"></rect>
  <path class="land" d="M0 12 Q0 0 12 0 H518 Q530 0 530 12 V62 C505 74 478 60 452 70 C430 78 410 64 384 70 C360 76 342 96 326 88 C300 74 285 64 250 68 C190 74 130 62 70 68 C40 71 20 66 0 72 Z"></path>
  <rect class="quay" x="14" y="76" width="286" height="4" rx="2"></rect>
  <rect class="quay" x="344" y="76" width="170" height="4" rx="2"></rect>
  <text class="area" x="16" y="36">신항</text>
  <text class="area" x="346" y="36">북항</text>
  ${터미널.map(칸).join('')}
</svg>`;

export default function ({ parentElement, data, setTriggerValue }) {
  const 틀 = parentElement.querySelector('#지도');
  if (!틀.dataset.준비) {
    틀.innerHTML = 그림;
    틀.dataset.준비 = '1';
  }
  틀.querySelectorAll('.t').forEach((칸요소) => {
    const 보내기 = () => setTriggerValue('pick', 칸요소.dataset.t);
    칸요소.onclick = 보내기;
    칸요소.onkeydown = (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); 보내기(); }
    };
    const 선택됨 = 칸요소.dataset.t === data.sel;
    칸요소.classList.toggle('on', 선택됨);
    칸요소.setAttribute('aria-pressed', 선택됨 ? 'true' : 'false');
  });
  틀.classList.toggle('picked', Boolean(data.sel));
}
"""

터미널지도 = st.components.v2.component(
    "portcast_terminal_map", html='<div id="지도"></div>', css=_CSS, js=_JS)
