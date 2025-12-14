# SeniorVideoFactory

시니어 타깃 유튜브 영상 자동 생성 시스템

## 🚀 빠른 시작 (5분 완성)

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. API 키 설정
cp .env.example .env
# .env 파일을 열어서 API 키 입력

# 3. UI 실행
python app.py

# 4. 브라우저에서 http://localhost:7860 접속
```

**자세한 설정 방법:** [`SETUP_GUIDE.md`](SETUP_GUIDE.md) 참고

---

## 프로젝트 개요

**SeniorVideoFactory**는 주제어 한 줄만 입력하면, 시니어(중장년층) 타깃에 맞는 유튜브 영상을 자동으로 생성하는 로컬 프로그램입니다.

### 핵심 특징

- 🎯 **주제어 입력만으로 완성**: "고혈압 관리", "무릎 통증", "연금 준비" 등
- ⏱️ **영상 길이 선택**: 10분 / 15분 / 20분
- 🎥 **비율 조절 시스템**: 비디오/이미지 비율을 0-100%로 자유롭게 조절
- 🖥️ **깔끔한 UI**: Gradio 기반 직관적인 웹 인터페이스
- 🤖 **AI 기반 자동화**:
  - Claude로 시니어 맞춤형 스크립트 자동 작성
  - OpenAI TTS로 음성 합성 (시니어 맞춤 속도)
  - OpenAI DALL-E 3로 고품질 AI 이미지 생성
  - Pexels API로 무료 B-roll 스톡 비디오 자동 삽입
  - FFmpeg으로 영상 렌더링 (Ken Burns 효과)
  - 카테고리별 맞춤 템플릿 (건강/돈/감성/추억)

## 전체 파이프라인

```
[1] 주제어 입력 + 설정 (비디오 비율, DALL-E 3 사용 여부)
    ↓
[2] TopicScoring & TitleThumbnailEngine
    - 검색 트렌드/랭킹 분석
    - 시니어 적합도 평가
    - 제목/썸네일 컨셉 생성
    ↓
[3] ContentProfileEngine
    - 카테고리 분류 (건강/돈/감성/추억 등)
    - 영상 길이 결정
    - 템플릿 선택
    ↓
[4] ScriptEngine (Claude API)
    - 시니어 템플릿 기반 대본 생성
    - Scene별 구조화
    - B-roll 비디오 비율에 따라 자동 할당
    ↓
[5] ImageEngine (DALL-E 3 / Placeholder)
    - Scene별 AI 이미지 생성
    - 썸네일 이미지 생성
    ↓
[6] VideoClipEngine (Pexels API)
    - B-roll 스톡 비디오 검색
    - HD 비디오 자동 다운로드
    ↓
[7] TTSEngine (OpenAI TTS)
    - Scene별 음성 합성
    - 시니어 맞춤 속도/톤 적용 (0.92x)
    ↓
[8] VideoRenderEngine (FFmpeg)
    - 이미지/비디오 + 오디오 결합
    - Ken Burns 효과 적용
    - 최종 MP4 생성
    ↓
[9] 출력
    - video.mp4 (최종 영상)
    - thumbnail.png (썸네일)
    - meta.json (메타데이터)
    - images/ (AI 생성 이미지들)
    - videos/ (B-roll 비디오 클립들)
    - audio/ (TTS 음성 파일들)
```

## 설치

### 1. 시스템 요구사항

- Python 3.8 이상
- FFmpeg

```bash
# Ubuntu/Debian
sudo apt-get install -y ffmpeg

# Mac
brew install ffmpeg

# Windows
# https://ffmpeg.org/download.html 에서 다운로드
```

### 2. Python 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env.example`을 `.env`로 복사하고 API 키를 입력:

```bash
cp .env.example .env
```

`.env` 파일 편집:

```env
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

## 사용법

### CLI 실행

```bash
# 간단 실행
python ui/cli.py
```

대화형 CLI에서:
1. 주제어 입력 (예: "고혈압 관리")
2. 영상 길이 선택 (10분/15분/20분)
3. 생성 시작

### Python 코드로 실행

```python
from main import run_pipeline

result = run_pipeline(
    keyword="고혈압 관리",
    duration_minutes=15
)

print(f"영상 생성 완료: {result['video_path']}")
```

## 프로젝트 구조

```
SeniorVideoFactory/
├── main.py                      # 메인 파이프라인
├── config/
│   └── settings.yaml           # 설정 파일
├── engines/
│   ├── topic_engine.py         # 주제 스코어링 & 제목/썸네일 생성
│   ├── profile_engine.py       # 컨텐츠 프로필 빌더
│   ├── script_engine.py        # 시나리오 생성
│   ├── image_engine.py         # 이미지 생성 (Gemini)
│   ├── tts_engine.py           # 음성 합성
│   └── video_engine.py         # 영상 렌더링 (FFmpeg)
├── models/
│   └── types.py                # 데이터 모델 정의
├── ui/
│   └── cli.py                  # CLI 인터페이스
├── utils/
│   ├── http_client.py          # HTTP 클라이언트
│   └── logger.py               # 로깅 유틸
└── export/                     # 결과물 저장 디렉토리
```

## 시니어 모드 (v1)

### 지원 카테고리

| 카테고리 | 키워드 예시 | 추천 길이 | 템플릿 |
|---------|-----------|---------|--------|
| **건강** | 혈압, 당뇨, 무릎, 허리 | 8분 | senior_info_4points |
| **돈** | 연금, 재테크, 주식 | 7분 | senior_info_3points |
| **감성** | 외로움, 행복, 관계 | 6분 | senior_story_healing |
| **추억** | 옛날, 청춘, 90년대 | 7분 | senior_story_reminiscence |

### 시니어 맞춤 설정

- **언어**: 한국어 (ko-KR)
- **말투**: 따뜻하고 천천히 (warm_slow)
- **속도**: 0.92배속
- **텍스트 밀도**: 낮음 (이해하기 쉽게)
- **화면 전환**: 느리게

## 개발 로드맵

### ✅ 현재 상태 (v1.0 - 완성!)

- [x] 프로젝트 구조 설계
- [x] 데이터 모델 정의
- [x] 전체 엔진 구현
- [x] Claude API 연동 (스크립트 생성)
- [x] OpenAI TTS 연동 (음성 합성)
- [x] FFmpeg 렌더링 파이프라인
- [x] Gradio 웹 UI
- [x] 시니어 맞춤 프롬프트 시스템
- [x] 카테고리별 이미지 스타일 가이드

**지금 바로 사용 가능합니다!** API 키만 입력하면 됩니다.

### 향후 개선 계획

- [ ] 실제 이미지 생성 API 연동 (DALL-E/Stable Diffusion)
- [ ] 온라인 트렌드 분석 (Google Trends, YouTube API)
- [ ] 자동 자막 생성 (SRT)
- [ ] 여러 모드 추가 (키즈, 청년, 일반 등)
- [ ] 유튜브 자동 업로드
- [ ] 배치 처리 (여러 영상 한번에 생성)

## 기술 스택

- **Python 3.8+**
- **LLM**: Claude Sonnet 4 (Anthropic)
- **TTS**: OpenAI TTS-1
- **이미지**: 플레이스홀더 (향후 DALL-E/SD)
- **영상 처리**: FFmpeg (Ken Burns 효과 포함)
- **UI**: Gradio (웹 기반)

## 라이선스

MIT License

## 기여

이슈와 PR을 환영합니다!

## 문의

프로젝트 관련 문의사항은 이슈로 남겨주세요.
