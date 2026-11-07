# PORTCAST 대시보드

부산항의 기상·해양 데이터와 풀컨테이너선 운항 데이터를 결합해, 환경 조건에 따른 체류시간과 터미널별 운영 변화를 보여 주는 Streamlit 대시보드입니다. (현재: 초안)

## 실행 방법

```bash
git clone https://github.com/PORT-CAST/Dashboard.git
cd Dashboard

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt

python -m streamlit run app.py
```

`pip`, `streamlit` 대신 `python -m pip`, `python -m streamlit`을 쓰면 가상환경과 다른 Python이 섞이지 않습니다.

## AI 요약 기능 (Gemini) — 각자 API 키 필요

AI 요약 버튼은 Google Gemini API를 사용합니다. **API 키는 저장소에 포함되어 있지 않으므로 각자 발급받아 넣어야 합니다.** 키가 없어도 대시보드는 실행되며, 요약 기능만 동작하지 않습니다.

1. https://aistudio.google.com/apikey 에서 Google 계정으로 로그인 → **Create API key** (무료, 카드 등록 없음)
2. 예시 파일을 복사해 `secrets.toml`을 만듭니다.
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
3. `.streamlit/secrets.toml`에 발급받은 키를 넣습니다. (`config.toml`이 아닙니다)
   ```toml
   GEMINI_API_KEY = "발급받은_키"
   ```
4. 대시보드를 다시 실행합니다.

### 주의

- **`secrets.toml`은 절대 커밋하지 마세요.** `.gitignore`에 등록되어 있지만, 커밋 전 `git status`로 한 번 더 확인하세요.
- 키를 팀원끼리 공유하지 말고 각자 발급받아 사용하세요. 키 주인의 무료 사용 한도를 함께 쓰게 됩니다.
- 무료 등급은 분당·하루 요청 수 제한이 있습니다. 한도를 넘으면 잠시 뒤 다시 시도하세요.
- 무료 등급에 보낸 내용은 Google 서비스 개선에 사용될 수 있으므로 비공개 자료는 요약에 넣지 마세요.
- 키가 노출되었다면 AI Studio에서 해당 키를 삭제하고 새로 발급받으세요.
- 요약 버튼은 화면에 분석 결과가 연결된 뒤에 활성화됩니다. (`app.py`의 `"분석결과"`)

## 폴더 구조

```
app.py                  화면 구성과 메뉴
ui.py                   색상, 상단 배너, 지표칸, 패널, AI 요약칸
criteria.py             기상 상황 판정 기준(주의·위험 값)
terminal_map.py         터미널 위치 개념도
requirements.txt        필요한 패키지
.streamlit/config.toml  테마·글꼴 설정
.streamlit/secrets.toml.example  API 키 예시 (복사해서 secrets.toml로 사용)
assets/                 배너 이미지(containership.png) 등
static/                 Pretendard 글꼴
```

## 바꾸는 곳

- 배너 사진: `assets/containership.png` 교체
- 배너 높이: `ui.py`의 `.hero` 스타일 `height:280px`
- 판정 기준: `criteria.py`
- 그래프·표: 각 화면 함수의 `ui.빈자리(...)`를 실제 그래프나 표 코드로 교체
