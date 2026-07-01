# OGC 2026 Rank Tracker

optichallenge.com 리더보드를 **매시간 자동으로 기록**하고, 팀 순위가 시간에 따라 어떻게 바뀌는지 그래프로 보여주는 도구입니다.

- **`fetch_leaderboard.py`** — 리더보드 API를 가져와 `history.json`에 스냅샷을 한 줄씩 쌓는 스크립트
- **`.github/workflows/track.yml`** — GitHub Actions가 매시간(cron) 위 스크립트를 자동 실행
- **`index.html`** — 순위 변화 범프 차트 + 급상승/급하락 + 현재 순위표 뷰어
- 내 컴퓨터가 꺼져 있어도 GitHub 서버에서 돌기 때문에 계속 기록됩니다. **완전 무료.**

---

## 왜 이 구조인가 (중요)

브라우저 페이지는 **열려 있을 때만** 코드가 돕니다. "매시간 자동 기록"은 서버에서 스케줄대로 도는 무언가가 필요하고, 브라우저에서 남의 사이트 API를 직접 부르면 대개 **CORS**에 막힙니다. 그래서 수집은 **GitHub Actions(서버 쪽, CORS 없음)**가 하고, 뷰어는 같은 저장소의 `history.json`만 읽습니다.

---

## 설치 (약 10분)

### 1. 저장소 만들기
GitHub에서 새 repository 생성 → 이 폴더의 파일 4개를 그대로 올립니다
(`index.html`, `fetch_leaderboard.py`, `.github/workflows/track.yml`, `README.md`).

### 2. API 주소 확인 ★
`fetch_leaderboard.py` 맨 위 `API_URL`은 스크린샷에서 확인한 CloudFront JSON 파일 주소로 넣어뒀습니다:

```
https://d32m8h9cownzsg.cloudfront.net/public/leaderboard/leaderboard_group/latest.json
```

다만 스크린샷에서 경로 **가운데 부분이 메뉴에 가려** 있었어서, 이 주소가 정확한지 한 번만 확인해 주세요. DevTools의 그 요청에서 우클릭 → **Copy → Copy URL** 한 값과 다르면, 그 값으로 `API_URL`을 바꾸면 됩니다. (끝의 `?_=...` 캐시버스터는 스크립트가 자동으로 붙이니 빼고 넣어도 됩니다.)

### 3. 데이터 형태 (참고)
이 리더보드는 **점수를 공개하지 않고** `group_rank`로 팀을 **10팀씩 밴드**로 묶어 보여줍니다(1밴드=상위 10팀…). 그래서 이 도구는 **밴드 이동**을 추적하고, 국적·소속(국기·태그)도 함께 표시합니다. 파서는 이미 이 형태(`leaderboard` / `team_name` / `group_rank` / `generated_at`)에 맞춰져 있어 그대로 동작합니다.

### 4. Actions 켜기
- 저장소 **Settings → Actions → General → Workflow permissions** → **Read and write permissions** 체크 (스냅샷을 커밋하려면 필요)
- **Actions** 탭 → "Track leaderboard" → **Run workflow**로 수동 1회 실행해서 잘 도는지 확인
- 성공하면 `history.json`이 생기고, 이후 매시간 자동으로 갱신됩니다

### 5. 뷰어 공개 (GitHub Pages)
- **Settings → Pages** → Source를 **Deploy from a branch** → `main` / `/ (root)` 선택 → Save
- 잠시 뒤 `https://<아이디>.github.io/<저장소>/` 에서 뷰어가 열립니다

---

## 로컬에서 미리 보기
`index.html`을 그냥 브라우저로 열면 됩니다. `history.json`이 아직 없으면 **샘플 데이터**로 화면이 어떻게 보이는지 렌더됩니다(배지에 `sample data` 표시). 실제 데이터가 쌓이면 자동으로 `live`로 바뀝니다.

---

## 알아둘 점

- **시간대**: 스냅샷은 UTC(`Z`)로 저장되고, 뷰어는 브라우저 현지 시간으로 표시합니다. 서울에서 보면 KST로 나옵니다.
- **cron 지연**: GitHub Actions 예약 실행은 서버가 붐비면 몇 분 늦을 수 있습니다. 뷰어는 슬롯이 아니라 실제 타임스탬프를 쓰므로 문제없습니다.
- **60일 규칙**: 저장소에 60일간 아무 활동이 없으면 예약 워크플로가 자동 비활성화됩니다. 예선이 7/28에 끝나므로 이 대회 기간엔 걱정 없습니다.
- **파일 크기**: 매시간이면 대회 내내 수천 개 스냅샷이 쌓여도 수 MB 수준이라 괜찮습니다. 나중에 오래된 스냅샷을 잘라내고 싶으면 스크립트에서 `history["snapshots"] = history["snapshots"][-2000:]` 같은 한 줄로 제한할 수 있습니다.
- **뷰어 옵션**: 상단에서 기간(24h/7d/All)과 표시 팀 수(Top 10/20/30/All)를 바꾸고, 검색창에 팀명을 넣어 특정 팀 선을 고정·강조할 수 있습니다. 같은 밴드의 팀들은 선이 겹치지 않게 살짝 벌려서 그리고, 오른쪽 팀 이름표도 서로 안 겹치게 자동 정렬됩니다.
