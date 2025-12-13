# 🚀 SeniorVideoFactory 설치 및 설정 가이드

이 가이드를 따라하면 5분 안에 시니어 타깃 유튜브 영상을 자동으로 생성할 수 있습니다!

## 📋 필수 준비물

### 1. 시스템 요구사항
- Python 3.8 이상
- FFmpeg (영상 렌더링용)

### 2. API 키 (필수 2개 + 선택 2개)

**필수:**
- **Anthropic API 키** (Claude - 스크립트 생성)
- **OpenAI API 키** (TTS - 음성 합성)

**선택적 (권장):**
- **Pexels API 키** (B-roll 비디오 - 영상에 움직임 추가)
- **Gemini API 키** (이미지 생성 - 향후 기능)

---

## 🛠️ Step 1: 시스템 설치

### FFmpeg 설치

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
1. https://ffmpeg.org/download.html 에서 다운로드
2. 환경변수 PATH에 추가

**설치 확인:**
```bash
ffmpeg -version
```

---

## 🔑 Step 2: API 키 발급

### 1. Anthropic API 키 (Claude)

**발급 방법:**
1. https://console.anthropic.com/ 접속
2. 로그인 또는 회원가입
3. Settings → API Keys로 이동
4. "Create Key" 클릭
5. 키를 복사하여 안전한 곳에 저장

**가격:**
- Claude Sonnet 4: 약 $3/백만 토큰 (입력)
- 15분 영상 1개당 약 $0.10-0.20 예상

### 2. OpenAI API 키 (TTS)

**발급 방법:**
1. https://platform.openai.com/ 접속
2. 로그인 또는 회원가입
3. API Keys 메뉴로 이동
4. "Create new secret key" 클릭
5. 키를 복사하여 안전한 곳에 저장

**가격:**
- TTS-1: $15/백만 문자
- 15분 영상 1개당 약 $0.05-0.10 예상

### 3. Pexels API 키 (B-roll 비디오 - 선택적, 권장)

**발급 방법:**
1. https://www.pexels.com/api/ 접속
2. 로그인 또는 회원가입 (무료)
3. "Get Started" 또는 "Get API Key" 클릭
4. 키를 복사하여 안전한 곳에 저장

**가격:**
- **완전 무료!** 월 200회 요청 한도
- 15분 영상 1개당 약 2-4회 요청 (B-roll scene 수에 따라)
- 월 50-100개 영상 생성 가능

**효과:**
- B-roll 비디오로 영상에 **자연스러운 움직임** 추가
- hook, empathy, summary 등 주요 장면에 스톡 비디오 자동 삽입
- 정적인 슬라이드쇼 느낌 제거

**참고:**
- Pexels API 키가 없으면 모든 scene에 이미지 사용 (Ken Burns 효과)
- API 키를 설정하면 주요 장면에 자동으로 비디오 클립 사용

### 4. Gemini API 키 (이미지 - 선택적)

**발급 방법:**
1. https://makersuite.google.com/app/apikey 접속
2. Google 계정으로 로그인
3. "Create API Key" 클릭
4. 키를 복사하여 안전한 곳에 저장

**참고:**
- 현재 Gemini는 이미지 분석 전용
- 실제 이미지 생성은 향후 DALL-E 또는 Stable Diffusion 연동 예정
- 지금은 플레이스홀더 이미지가 생성됨

---

## ⚙️ Step 3: 프로젝트 설정

### 1. 저장소 클론 (이미 완료된 경우 생략)
```bash
git clone https://github.com/jonghyeuk/youtubemaker.git
cd youtubemaker
```

### 2. Python 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

**.env 파일 생성:**
```bash
cp .env.example .env
```

**.env 파일 편집:**
```bash
nano .env  # 또는 원하는 에디터 사용
```

**API 키 입력:**
```env
# API Keys (필수)
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxx

# API Keys (선택적 - 권장)
PEXELS_API_KEY=xxxxxxxxxxxx

# API Keys (선택적)
GEMINI_API_KEY=xxxxxxxxxxxx

# 나머지 설정은 기본값 사용
```

**저장 및 종료:**
- nano: `Ctrl+O` → `Enter` → `Ctrl+X`
- vim: `:wq`

---

## 🎬 Step 4: 실행

### UI 모드 (추천)

**1. UI 실행:**
```bash
python app.py
```

**2. 브라우저 접속:**
```
http://localhost:7860
```

**3. 사용 방법:**
1. 주제어 입력 (예: "고혈압 관리")
2. 영상 길이 선택 (10분/15분/20분)
3. "🎬 영상 생성하기" 버튼 클릭
4. 완료 후 영상 다운로드

### CLI 모드 (터미널)

**직접 실행:**
```bash
python main.py
```

**Python 코드로 실행:**
```python
from main import run_pipeline

result = run_pipeline(
    keyword="고혈압 관리",
    duration_minutes=15
)

print(f"영상: {result['video_path']}")
print(f"썸네일: {result['thumbnail_path']}")
```

---

## 🧪 Step 5: 테스트

### API 키 작동 확인

**Python으로 간단 테스트:**
```python
import os
from dotenv import load_dotenv

load_dotenv()

# 필수 키
print("필수 API 키:")
print("  Anthropic:", "✓" if os.getenv("ANTHROPIC_API_KEY") else "✗")
print("  OpenAI:", "✓" if os.getenv("OPENAI_API_KEY") else "✗")

# 선택적 키
print("\n선택적 API 키:")
print("  Pexels:", "✓" if os.getenv("PEXELS_API_KEY") else "✗ (B-roll 비디오 미사용)")
print("  Gemini:", "✓" if os.getenv("GEMINI_API_KEY") else "✗ (이미지 미사용)")
```

### 간단한 영상 생성 테스트
```bash
python -c "from main import run_pipeline; run_pipeline('테스트', 10)"
```

---

## 📁 출력 파일 위치

생성된 파일들은 `export/` 디렉토리에 저장됩니다:

```
export/
└── 고혈압_관리_20250124_143022/
    ├── video.mp4           # 최종 영상
    ├── thumbnail.png       # 썸네일
    ├── meta.json           # 메타데이터
    ├── images/             # Scene별 이미지 (정적 scene용)
    │   ├── scene_000_hook.png
    │   ├── scene_001_empathy.png
    │   └── ...
    ├── videos/             # B-roll 비디오 클립 (동적 scene용)
    │   ├── broll_000_hook.mp4
    │   ├── broll_001_empathy.mp4
    │   └── ...
    └── audio/              # Scene별 오디오
        ├── audio_000_hook.mp3
        ├── audio_001_empathy.mp3
        └── ...
```

---

## ❓ 문제 해결

### API 키 오류
```
Error: Anthropic API key not found
```
**해결:** `.env` 파일이 프로젝트 루트에 있는지 확인하고 API 키가 정확한지 확인

### FFmpeg 오류
```
ffmpeg: command not found
```
**해결:** FFmpeg 설치 및 PATH 설정 확인

### 모듈 import 오류
```
ModuleNotFoundError: No module named 'anthropic'
```
**해결:** `pip install -r requirements.txt` 다시 실행

### 포트 충돌 (UI 모드)
```
OSError: [Errno 48] Address already in use
```
**해결:**
```bash
# 다른 포트 사용
python app.py --port 7861
```

---

## 💰 예상 비용

**15분 영상 1개 생성 기준:**

| 항목 | 예상 비용 |
|------|----------|
| Claude (스크립트) | $0.10-0.20 |
| OpenAI TTS (음성) | $0.05-0.10 |
| **합계** | **$0.15-0.30** |

**월 100개 영상 생성 시:** 약 $15-30

---

## 🎯 다음 단계

API 키 설정이 완료되었다면:

1. **UI 실행**: `python app.py`
2. **첫 영상 생성**: 주제어 입력 → 생성
3. **결과 확인**: `export/` 디렉토리에서 확인

**추가 커스터마이징:**
- `config/settings.yaml`: 기본 설정 변경
- `engines/prompt_templates.py`: 프롬프트 템플릿 수정
- `engines/image_engine.py`: 이미지 스타일 커스터마이징

---

## 📞 지원

문제가 발생하면:
1. GitHub Issues에 문의
2. README.md 참고
3. 로그 확인: 콘솔 출력 메시지 확인

---

**축하합니다! 이제 시니어 타깃 영상을 자동으로 생성할 수 있습니다! 🎉**
