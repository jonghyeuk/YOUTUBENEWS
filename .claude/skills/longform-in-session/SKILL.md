---
name: longform-in-session
description: Claude Code 세션 안에서 YOUTUBENEWS 엔진으로 롱폼 영상(특히 부처님 말씀·경전·불교 해설, 명상 콘텐츠)을 처음부터 끝까지 만드는 절차. 대본은 Claude가 직접 쓰고(Anthropic API 호출 없음), TTS·자막·줌/크로스페이드 렌더·BGM 믹싱은 저장소 엔진(pipeline step5~7)을 그대로 쓴다. 종혁님이 "이 주제로 영상 만들어줘", "부처님 말씀 영상", "경전 내용으로 10분짜리", "반야심경/금강경/법구경 … 영상", "숏 만들듯 여기서 만들어줘"처럼 주제·경전·길이를 주고 영상 제작을 요청하면 앱(Gradio)을 띄우지 말고 반드시 이 스킬을 따른다.
---

# 세션 안에서 롱폼 영상 만들기 (YOUTUBENEWS)

2026-10 반야심경 「불생불멸」 10분 영상을 이 방식으로 만들었고 종혁님이 "이 방식 딱 좋다"고 확정했다.
그 결과물의 대본·그림 설계가 `examples/`에 있으니 처음이면 먼저 열어 본다.

## 종혁님이 기대하는 결과 (요구사항)

- **사실 기반**: 픽션 금지. 경전 본문·경전 속 일화·문답만 쓴다. 현대 해설(예: 파도 비유)은 "오늘날 자주 쓰는 설명"이라고 밝힌다. 원문이 확실하지 않은 구절·숫자는 쓰지 않는다.
- **이야기 흐름**: 질문으로 열고(후킹) → 경전 배경 → 핵심 구절 → 비유·해설 → 오해 바로잡기 → 다른 경전 연결 → 정리·맺음.
- **목소리**: 종혁님이 앱에서 쓰는 그 여성 음성 = 엔진 `elevenlabs2.5`(Turbo v2.5) + 스타일 `불교강의`(voice `4p0HBzAAGyju0nYfNntV`, 한국어 기본 음성) + **속도 1.0**(앱 기본 0.9보다 조금 빠르게 — 종혁님 요청). `scripts/tts.py`의 기본값이 이것이다.
  ※ 첫 제작 때 config의 `불교종교`(voice `zgDzx5jL…`, v3 엔진)를 잘못 골랐다가 다시 만들었다. `불교종교`는 앱 스타일 목록에 없다.
- **그림 — 돈을 아낀다**: 상황·분위기만 맞으면 된다(인물이 조금 달라도 괜찮음). 기본은 **fal FLUX-schnell(장당 약 0.003달러)**(4-A). 인물 일관성이 꼭 필요하다고 할 때만 OpenAI(4-B)를 쓰고, 그때도 싼 설정이 기본이며 비싼 4K 시트는 먼저 예상 비용을 알린다.
- **화풍은 Claude가 정한다**: 종혁님이 화풍을 말하지 않으면 경전의 시대·장소와 분위기에 맞춰 Claude가 고른다(필요하면 한 줄로 물어봐도 된다). 저장소의 화풍 블록(korea 수묵담채 / china 도상화 / india 스케치)은 출발점일 뿐 꼭 따를 필요는 없다 — `fal_images.py --style "..."`로 직접 쓴 화풍 문장을 줄 수 있다.
- **실패는 돈이다**: 유료 API가 실패하면 자동 재시도하지 말고 원인부터 확인한다.
- **연출**: 그림을 그대로 두지 말고 줌인/줌아웃·팬으로 움직이고, 그림 사이는 크로스페이드(엔진 기본 1초).
- **배경음**: 사색적·명상적 불교 배경음을 처음부터 끝까지 깐다.
- **길이**: 요청 길이(예: 10분)에 맞춘다.

## 전체 순서

작업 폴더는 `projects/<영문이름>/`(gitignore 대상). 스크립트는 모두 이 스킬의 `scripts/`에 있다.
롱폼은 이 저장소(YOUTUBENEWS)에서만 만든다. youtubemaker는 숏 전용이니 롱폼 작업으로 건드리지 않는다.

```
1. 대본 script.json 작성 ─┐
2. 길이 맞추기(샘플 TTS)  │
3. 그림 프롬프트         ├→ 4. 그림 생성(A: fal / B: 시트) → 5. 전체 TTS → 6. BGM → 7. 렌더 → 8. 검증 → 9. 전달
```

### 0. 환경 준비 (새 컨테이너마다)

```bash
python3 -m venv /tmp/venv && . /tmp/venv/bin/activate
pip install -q --upgrade pip setuptools wheel
pip install -q "moviepy==1.0.3" pydub elevenlabs python-dotenv anthropic openai pillow numpy requests
```
시스템 pip로는 moviepy 1.0.3 빌드가 `install_layout` 오류로 실패한다 → venv를 쓴다.
키는 프록시가 주입한다(OpenAI·ElevenLabs). Gemini 키는 무효였다.
fal은 환경 변수 `FAL_KEY`가 필요하다: 세션 제목 표시줄의 클라우드 환경 메뉴 → Edit → 환경 변수에 등록(새 세션부터 적용). 키를 채팅으로 받지 않는다. `pip install fal-client`도 venv에 추가한다.

### 1. 대본 — `script.json`

형식은 `examples/heart_sutra_script.json`과 같다: `{"title", "scenes": [{"id","title","images","text"}]}`.
- 씬 25개 안팎, 씬당 110~150자. `images`는 씬에 들어갈 그림 수(1~2). 긴 씬·전환이 있는 씬은 2.
- 나레이션은 **한글만**(한자·숫자 금지: "기원전 이 세기", "이백육십 자"). TTS가 한자·숫자를 잘못 읽고, 자막도 이 텍스트가 그대로 나온다.
- 경전 인용은 독송음 그대로 쓰고 바로 뒤에 우리말 풀이를 붙인다.

### 2. 길이 맞추기

기본 음성(불교강의 / elevenlabs2.5 / 1.0)은 실측 **초당 약 4.4자**(공백 포함, 3,326자 → 말 762초)다. 음성·속도를 바꾸면 `--sample 1`로 다시 잰다.
(첫 제작 때 다른 음성 기준 5.7자/초로 대본을 써서, 목소리를 바꾸자 10분 → 15분이 됐다.) 엔진이 시작 1.5초 + 씬마다 2초 무음을 넣는다.
`예상 초 = 총 글자수 / 4.4 + 1.5 + 2 × 씬수`. 10분이면 20씬 기준 약 2,450자, 25씬이면 약 2,400자.
전체 합성 전에 씬 1~2개만 합성해 속도를 확인하면 낭비가 없다.

### 3. 그림 프롬프트 — 잘 쓰기

싼 모델일수록 프롬프트가 결과를 좌우한다. 컷마다 영어로, 아래 순서로 한두 문장:
1. **주제 하나**: 무엇이 화면 중심인가 (사람이면 나이·옷·자세, 사물이면 재질·상태)
2. **장소·시대**: 고대 인도 라자그리하의 바위산, 조선 산사, 기원전 2세기 그리스풍 궁전 … — 경전 배경과 맞게
3. **시간·빛**: dawn / golden hour / moonlight / single oil lamp — 분위기는 빛이 만든다
4. **구도**: wide shot / medium shot / close-up / from behind / low angle — 앞뒤 컷과 겹치지 않게 섞는다
5. **분위기 한 단어**: serene, contemplative, solemn …
- 사람이 없어야 하는 컷은 `no people` 을 쓴다. 모든 컷 끝에 `no text, no letters`.
- 추상 개념(공·무아·연기)은 직접 그리려 하지 말고 그것을 보여 주는 장면(파도, 등불, 낙엽, 흩어지는 구름)으로 바꾼다.
- 화풍 문장은 쓰지 않는다 — 스크립트가 저장소 화풍 블록을 앞에 붙인다(4-A) / visual.json의 style을 쓴다(4-B).
- 예: `An elderly monk in a saffron robe sitting alone on a seaside rock at sunset, seen from behind, watching the waves, serene, no text, no letters`


**A(기본, fal)**: `prompts.json` = 컷별 영어 장면 묘사 리스트(컷 수 = `images` 합계). 화풍은 스크립트가 붙이니 장면·분위기·조명만 쓴다.

**B(인물 일관성 필요할 때만)**: `visual.json` — 아래 형식.

`examples/heart_sutra_visual.json` 형식: `style`(화풍 한 문단), `characters`(이름 → 외모·옷), `panels`(컷 설명, 영상 순서).
- `panels` 수 = `script.json`의 `images` 합계, **4의 배수**로 맞춘다(2×2 시트 단위).
- 컷 설명에 인물을 넣을 때는 `characters`의 **대문자 이름 그대로** 쓴다. 이름이 없는 컷은 자동으로 "no people"이 붙는다.
- 인물은 외모가 서로 확실히 구분되게(나이·체형·옷 색) 정한다.

### 4-A. 그림 생성 — fal (기본)

```bash
S=.claude/skills/longform-in-session/scripts; W=projects/<이름>
python $S/fal_images.py $W --style "<Claude가 정한 화풍 문장>"   # 또는 --region korea|china|india (저장소 화풍 블록)
```
- 화풍은 저장소 `storymaker/ai_prompt_generator.py`의 `REGIONAL_ENGINE_STYLES[region]["fal"]`(앱의 이미지 스타일 드롭다운과 같은 것)를 쓴다.
- 결과는 1024×576 정도라 1080p에서 약간 부드럽다 — 종혁님 기준으로 충분하다.
- 실패하면 멈춘다. 다시 실행하면 이미 만든 컷은 건너뛰니 재과금이 없다.
- 생성 후 밀착 시트로 분위기·내용이 맞는지 확인하고, 엉뚱한 컷만 지우고 다시 실행한다.

### 4-B. 그림 생성 — OpenAI (fal을 못 쓸 때 / 인물 일관성이 필요할 때)

**기본은 싼 설정**(종혁님 요청): `gpt-image-1-mini`, `1536x1024`, `quality: medium`, 컷당 1장.
`{"prompt": "<화풍 문장>. <컷 묘사>", "out": "panels/panel_01.jpg"}` job을 컷마다 만들어 `imggen.py`로 돌린다.
인물을 맞추고 싶으면 job에 `"refs": [기준 이미지]`를 넣는다(편집 API, 같은 싼 모델).

아래 4K 2×2 시트 방식은 **종혁님이 고품질·인물 일관성을 명시적으로 원할 때만** 쓴다(장당 비용이 훨씬 큼):

```bash
python $S/build_prompts.py $W/visual.json $W
python $S/imggen.py $W/jobs/ref.json                 # 인물 기준 시트 → 반드시 눈으로 확인
for j in $W/jobs/sheet_*.json; do python $S/imggen.py $j & done; wait   # 4개씩 병렬이면 충분
python $S/split_sheet.py $W/sheets/sheet_1.jpg 1 $W/panels          # 시트 k → 첫 컷 번호 4k-3
```
- 시트는 3840×2160, 2×2라서 컷 하나가 약 1912×1072다(1080p에 바로 맞음). 3×3은 컷이 1280×720이라 흐려지니 쓰지 않는다.
- **시트마다 직접 열어 확인**한다(축소본을 만들어 Read). 인물이 엉뚱한 칸에 들어가거나 시대가 틀린 칸은 그 칸만 단독 이미지(`size: "2048x1152"`, 참조 이미지 첨부)로 다시 만들어 해당 `panel_XX.jpg`를 덮어쓴다. 시트 전체를 다시 뽑는 것보다 싸다.
- 32컷 전체를 한 장의 밀착 시트로 만들어 순서·크롭을 마지막으로 확인한다.
- 비용: 4K 고품질 1장당 출력 13,600 이미지 토큰. 시트 8장 + 기준 시트면 약 12만 토큰.
- **실패하면 재시도하기 전에 원인부터 본다.** 실패한 4K 요청도 과금될 수 있다(첫 제작 때 원인 확인 없이 재시도해 7장 분량을 날렸다). `imggen.py`는 기본적으로 재시도하지 않는다.
- 429 `credit_balance_exhausted`가 나오면 즉시 멈추고 종혁님께 충전을 요청한다.
- 시트를 뽑기 전에 예상 호출 수와 비용을 종혁님께 먼저 알린다.

### 5. 전체 TTS

```bash
python $S/tts.py $W --sample 1     # 첫 씬만 → sample.mp3 를 종혁님께 보내 목소리 확인
python $S/tts.py $W                # 기본값: elevenlabs2.5 / 불교강의 / 1.0
```
`불교강의`는 v2.5 감정표에 없어 전 구간 neutral 톤으로 나간다(앱과 동일).
결과 `audio_full.mp3` 길이를 확인하고 요청 길이와 크게 다르면 대본을 다듬어 다시 합성한다.

### 6. 배경음

```bash
python $S/make_bgm.py $W <오디오길이+20초>
```
ElevenLabs 키에 음악 생성 권한이 없어서 효과음(드론·싱잉볼·피리·종)을 생성해 배치한다. 결과는 `bgm.mp3`.
종혁님께는 "효과음으로 구성한 배경음"이라고 사실대로 말한다.

### 7. 렌더

```bash
nohup python $S/render.py $W --style 불교강의 --bgm-volume 0.18 > $W/render.log 2>&1 &
```
10분 영상에 약 30분 걸린다(4코어). 기다릴 때는 `render.log`를 확인하는 until 루프를 쓴다.

### 8. 검증 (보내기 전에 반드시)

- `ffprobe`로 영상과 오디오 길이가 0.2초 이내로 같은지 확인한다.
- 장면 경계 몇 곳(`audio_segments.json`의 `start_time` + 1초)에서 프레임을 뽑아 **나레이션과 그림이 맞는지, 자막(나눔명조)이 정상인지** 눈으로 본다.
- 문제가 있으면 원인을 찾는다. 엔진을 고쳐야 하면 고치고 PR로 올린다.

### 9. 전달

앱 전송 한도는 **30MB**다. 원본(1080p 10분 ≈ 230MB)은 보낼 수 없다.
```bash
bash $S/preview.sh $W/final.mp4 $W/preview_480p.mp4   # 28MB 전후 전체 길이 미리보기
```
미리보기를 보내고, 원본 경로를 알려 준다. 원본이 필요하면 30MB 이하 조각으로 나눠 보낸다.

## 보고할 때

- 쓴 비용(이미지 호출 수·토큰), 다시 만든 컷과 그 이유, 확인 못 한 것은 그대로 말한다.
- 대본에서 사실과 해설을 어떻게 구분했는지 한 줄로 밝힌다.
