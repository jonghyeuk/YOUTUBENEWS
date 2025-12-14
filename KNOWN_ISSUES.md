# SeniorVideoFactory - 개발 중 발견된 문제점 및 도움 요청

---

## 📌 프로젝트 개요

**SeniorVideoFactory**는 시니어 타깃 유튜브 영상을 자동으로 생성하는 시스템입니다.

### 전체 파이프라인 (8단계)
```
키워드 입력
  ↓
1. Topic Engine      → 제목 3개 생성 (Claude API)
  ↓
2. Profile Engine    → 영상 프로필 생성 (카테고리, 템플릿 선택)
  ↓
3. Script Engine     → Scene별 대본 생성 (Claude API)
  ↓
4. Image Engine      → Scene별 이미지 생성 (DALL-E 2/3)
  ↓
5. VideoClip Engine  → B-roll 비디오 검색/다운로드 (Pexels API)
  ↓
6. Thumbnail Engine  → 썸네일 생성 (DALL-E)
  ↓
7. TTS Engine        → 나레이션 음성 생성 (OpenAI TTS / Google TTS)
  ↓
8. Video Engine      → 최종 영상 렌더링 (FFmpeg)
```

### 핵심 기술 스택
- **Claude API**: 제목/대본 생성
- **OpenAI API**: 이미지(DALL-E), TTS
- **Pexels API**: B-roll 스톡 비디오
- **FFmpeg**: 영상 합성 (Ken Burns, fade, pad 효과)
- **병렬 처리**: ThreadPoolExecutor로 이미지 4개 동시 생성

### 주요 기능
- **자동 해상도 전환**: Shorts(9:16) vs 일반(16:9)
- **비용 최적화**: DALL-E 2/3 선택 가능
- **병렬 처리**: 이미지 생성 4x 속도 향상
- **재시도 로직**: 타임아웃 시 exponential backoff
- **폴백 메커니즘**: 실패 시에도 파이프라인 계속 진행

---

## 🔴 해결되지 않은 문제 (도움 필요)

### 1. **비디오 해상도 자동 전환 - 일관성 검증 미흡**
**문제점:**
- Shorts(세로)와 일반 영상(가로)의 자동 전환이 구현되었지만
- 모든 엔진(VideoClipEngine, ImageEngine, VideoEngine)이 일관되게 동작하는지 완전히 검증되지 않음
- 특히 Pexels 비디오 검색 시 aspect ratio 불일치 가능성

**현재 상태:**
- `VIDEO_RESOLUTION` 환경변수 기반 자동 전환 구현
- Pexels에서 orientation (portrait/landscape) 동적 검색
- 일부 테스트만 완료

**현재 구현:**
```python
# video_clip_engine.py
if height > width:  # 1080x1920 (세로)
    self.orientation = "portrait"
else:  # 1920x1080 (가로)
    self.orientation = "landscape"

# Pexels API 검색
params = {"query": query, "orientation": self.orientation}
```

**검증 필요:**
- ✅ Pexels에서 올바른 orientation 비디오 검색하는지?
- ❓ 다운로드된 비디오가 실제로 요청한 해상도와 맞는지?
- ❓ FFmpeg pad 필터가 비율 불일치 시 제대로 작동하는지?
- ❓ Shorts(세로)와 일반(가로) 모두 실제로 정상 렌더링되는지?

**요청 사항:**
- 다양한 키워드로 Shorts(1분) / 일반(3분, 5분) 영상 생성 테스트
- 렌더링된 영상 해상도 확인
- 이상한 crop/padding 발생 시 로그 공유

**파일:** `engines/video_clip_engine.py:52-67`, `engines/video_engine.py:183-195`

---

### 2. **병렬 이미지 생성 - 타임아웃 최적화**
**문제점:**
- 현재 타임아웃 120초 설정
- 이미지가 많을 경우(10개 이상) 일부 이미지가 여전히 타임아웃될 수 있음
- 재시도 로직(2회)이 있지만 실패 시 placeholder로 폴백

**현재 구현:**
```python
# image_engine.py
self.openai_client = OpenAI(timeout=120.0)  # 2분

with ThreadPoolExecutor(max_workers=4) as executor:
    # 4개 이미지 동시 생성

for attempt in range(max_retries + 1):  # 총 3회 시도
    try:
        response = self.openai_client.images.generate(...)
    except Exception:
        wait_time = 2 ** attempt  # 2초, 4초 백오프
        time.sleep(wait_time)
```

**실제 상황:**
- 5분 영상 = 약 8개 이미지 필요
- 4개씩 병렬 처리 → 2 라운드 (Round 1: 4개, Round 2: 4개)
- 1개당 평균 30-60초 소요 (DALL-E 3 기준)
- 가끔 특정 이미지가 120초 초과 → placeholder 사용됨

**요청 사항:**
- 실제 사용 시 타임아웃이 자주 발생하는지?
- 발생한다면 몇 %의 이미지가 실패하는지?
- 타임아웃을 180초로 늘리면 해결될 것 같은지?
- 또는 재시도 3회로 늘리는 게 나을지?

**파일:** `engines/image_engine.py:230-293`

---

### 3. **FFmpeg 에러 처리 - 불완전한 검증**
**문제점:**
- FFmpeg 명령 실패 시 에러 메시지가 불명확할 때가 있음
- exit status 코드가 플랫폼마다 다를 수 있음 (Windows vs Linux)
- 비디오 코덱, 해상도 호환성 문제 가능성

**현재 구현:**
```python
# video_engine.py
vf = (
    f"scale={resolution}:force_original_aspect_ratio=decrease,"
    f"pad={res_for_pad}:(ow-iw)/2:(oh-ih)/2,"  # 중앙 정렬
    f"setsar=1,"
    f"fade=in:0:{int(fps*0.5)},fade=out:{fade_out_start}:{fade_duration_frames}"
)
```

**과거 해결한 에러:**
- ✅ `pad=1920x1080` → `pad=1920:1080` (형식 수정)
- ✅ fade out 프레임 계산 오버플로우 수정
- ✅ exit status 4294967274 해결

**현재 우려사항:**
- Pexels에서 다운로드한 비디오가 다양한 코덱/포맷일 수 있음
- 일부 비디오가 호환되지 않을 가능성
- 에러 발생 시 정확한 원인 파악 어려움

**요청 사항:**
- FFmpeg 에러 발생 시 **전체 로그** 공유 (stderr 포함)
- 어떤 키워드/비디오에서 실패했는지
- 비디오 파일 정보 (코덱, 해상도, 길이)

**파일:** `engines/video_engine.py:163-257`

---

## 🟡 임시 해결된 문제 (개선 필요)

### 4. **제목 생성 - Claude API 의존성**
**문제점:**
- 제목 생성이 Claude API에 완전히 의존
- API 실패 시 폴백 메커니즘 없음
- 비용이 발생함 (매번 API 호출)

**현재 구현:**
```python
# topic_engine.py
response = self.client.messages.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": prompt}]
)
# API 실패 시 → Exception 발생, 프로그램 중단
```

**문제 상황:**
- Claude API가 다운되거나 rate limit 초과 시 제목 생성 불가
- 사용자가 영상 제작을 시작조차 못함
- 대안이 없음

**개선 방향 (선택사항):**
- 로컬 템플릿 기반 폴백 추가?
  - 예: "{키워드}에 대해 알아야 할 중요한 사실들"
- API 실패 시에도 기본 제목으로 계속 진행?
- 캐싱으로 비용 절감? (같은 키워드 재사용 시)

**질문:**
- Claude API 실패가 실제로 자주 발생하는지?
- 폴백이 꼭 필요한지, 아니면 그냥 재시도하면 되는지?

**파일:** `engines/topic_engine.py:90-155`

---

### 5. **나레이션 파싱 - 정규식 의존**
**문제점:**
- Claude 응답 형식이 바뀌면 파싱 실패 가능
- 여러 개의 정규식 패턴을 시도하지만 완벽하지 않음
- 한글 인코딩 변형("내레이션" vs "나레이션") 처리

**현재 구현:**
```python
# script_engine.py
patterns = [
    r'\*\*[내나]레이션:\*\*\s*["\"\'](.+?)["\"\']',  # 따옴표 안
    r'\*\*[내나]레이션:\*\*\s*([^*\n].+?)(?=\n\*\*|\n\n|$)',  # 따옴표 없이
    # ... 4개 패턴
]
# 모든 패턴 실패 시 → Warning + 전체 텍스트 사용
```

**과거 문제:**
- ❌ TTS가 "**화면**:", "**나레이션**:" 레이블까지 읽음
- ❌ "(10초)" 같은 가이드라인도 TTS가 읽음

**현재 상태:**
- ✅ 대부분의 경우 올바르게 나레이션만 추출
- ⚠️ Claude가 응답 형식을 바꾸면 실패 가능성 있음

**개선 방향 (선택사항):**
- Claude에게 JSON 형식으로 응답 요청?
  ```json
  {
    "narration": "실제 나레이션 텍스트",
    "image_prompt": "이미지 설명"
  }
  ```
- 더 robust한 마크다운 파서 사용?

**질문:**
- 현재 파싱 실패가 자주 발생하는지?
- JSON 형식으로 바꾸는 게 나을지?

**파일:** `engines/script_engine.py:211-231`

---

### 6. **B-roll 비디오 검색 - Pexels 제한**
**문제점:**
- Pexels API 무료 플랜은 요청 제한 있음
- 검색 키워드가 한국어일 경우 결과 부족
- 비디오 품질/길이가 요구사항에 안 맞을 수 있음

**현재 구현:**
```python
# video_clip_engine.py
# Pexels API로 비디오 검색
params = {"query": query, "orientation": self.orientation}
response = requests.get(PEXELS_API_URL, headers=headers, params=params)

# 검색 결과 없으면 이미지로 폴백
if not videos:
    scene.use_video = False
```

**제한 사항:**
- Pexels API 무료 플랜: 200 요청/시간
- 한국어 키워드 검색 결과 부족 (예: "무릎 통증" → 결과 없음)
- 비디오 길이가 요구사항보다 짧을 수 있음

**개선 방향 (선택사항):**
- 한국어 → 영어 자동 번역 추가?
- Pixabay, Unsplash Video API 추가?
- 로컬 비디오 라이브러리 지원?

**질문:**
- Pexels 검색이 실제로 충분한지?
- 한국어 키워드에서 자주 실패하는지?
- 다른 API가 필요한지?

**파일:** `engines/video_clip_engine.py:98-173`

---

## 🟢 완전히 해결된 문제

### ✅ DALL-E 2 구현 완료
- 이전: 모든 옵션이 DALL-E 3 사용 (가짜 옵션)
- 현재: DALL-E 2/3 실제로 분리 구현
- 비용 절감 가능 (50% 저렴)

### ✅ TTS 가이드라인 읽기 문제
- 이전: "**화면:**", "**나레이션:**" 레이블까지 TTS가 읽음
- 현재: 정규식으로 실제 나레이션만 추출
- 한글 인코딩 변형 처리

### ✅ FFmpeg pad 필터 형식 오류
- 이전: `pad=1920x1080` (잘못된 형식)
- 현재: `pad=1920:1080` (올바른 형식)
- exit status 오류 해결

### ✅ Claude 모델 404 에러
- 이전: 존재하지 않는 모델명 사용
- 현재: `claude-sonnet-4-20250514` 사용
- API 호출 성공

### ✅ Google Cloud TTS 구현 완료
- WaveNet 한국어 네이티브 음성 지원
- OpenAI TTS와 동일한 인터페이스
- 실패 시 자동 폴백

---

## 📋 우선순위별 개선 필요 사항

### 🔥 높음 (High Priority)
1. **비디오 해상도 전환 검증** - Shorts/일반 영상 전체 테스트 필요
2. **이미지 생성 타임아웃 최적화** - 실사용 데이터 기반 조정
3. **FFmpeg 에러 디버깅** - 실패 케이스 수집 및 분석

### ⚡ 중간 (Medium Priority)
4. **제목 생성 폴백 메커니즘** - API 실패 시 대비 (필요 시)
5. **B-roll 비디오 다양화** - Pexels 제한 해결 (필요 시)
6. **나레이션 파싱 개선** - JSON 형식 전환 고려

### 💡 낮음 (Low Priority)
7. **비용 최적화** - 캐싱, 프리로드 등
8. **성능 개선** - 병렬 처리 확대

---

## 🛠️ 실제 사용 피드백 요청

### 1. **전체 파이프라인 테스트**
다양한 키워드로 실제 영상 생성 후 피드백 부탁드립니다:

**테스트 케이스:**
- ✅ Shorts (1분): "고혈압 관리"
- ✅ 일반 (3분): "무릎 통증 예방"
- ✅ 일반 (5분): "노후 자금 준비"

**확인 사항:**
- 영상이 정상적으로 생성되는지?
- 해상도가 올바른지? (Shorts: 1080x1920, 일반: 1920x1080)
- 이미지 타임아웃이 발생하는지?
- B-roll 비디오 검색이 잘 되는지?
- TTS 음질이 괜찮은지?

### 2. **에러 발생 시**
에러 발생하면 다음 정보 공유 부탁드립니다:

- 키워드 및 설정 (길이, 비율 등)
- 콘솔 전체 로그 (특히 `[ERROR]` 포함)
- 어느 단계에서 실패했는지
- 생성된 파일들 (이미지/비디오/오디오)

### 3. **비용 및 성능**
실제 사용 후 피드백:

- 5분 영상 1개 생성 비용이 얼마나 나오는지?
- 전체 생성 시간이 얼마나 걸리는지?
- 어느 단계가 가장 오래 걸리는지?
- 이미지 생성 성공률 (%)

### 4. **품질 개선**
생성된 영상 품질 관련:

- 제목이 클릭베이트처럼 느껴지는지?
- 나레이션 내용이 자연스러운지?
- 이미지가 주제와 잘 맞는지?
- B-roll 비디오가 적절한지?
- TTS 발음이 부자연스러운 부분이 있는지?

---

## 📝 참고 사항

### 설계 철학
- **폴백 우선**: 모든 단계에서 실패 시 대안 제공 (placeholder 이미지, 이미지로 폴백 등)
- **파이프라인 지속**: 에러 발생해도 최대한 다음 단계로 진행
- **로그 추적**: 각 단계마다 상세한 로그로 문제 진단 가능

### 로그 읽는 법
```
[TopicEngine] Generating titles...
[ScriptEngine] Generating script...
[ImageEngine] [0] Starting image generation...
  [0] Using DALL-E 3
  [0] ✓ Success!
[TTSEngine] Generating audio for hook
  Voice: alloy (OpenAI TTS)
  ✓ Saved: audio_000_hook.mp3 (10.5s)
[VideoEngine] Rendering final video...
  ✓ Video saved: final_video.mp4
```

### 개발 히스토리
- **2025-01**: 초기 구현 (DALL-E 3, OpenAI TTS)
- **이번 세션**: DALL-E 2 추가, Google TTS 구현, 나레이션 파싱 개선, 문제점 문서화

---

**감사합니다! 실제 사용 후 피드백 기다리겠습니다.** 🙏
