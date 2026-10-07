---
name: longform-in-session
description: Claude Code 세션 안에서 YOUTUBENEWS 엔진으로 롱폼 영상(부처님 말씀·경전·불교 해설·명상, 그리고 야화 채널의 조선왕조실록 미스터리·괴이·공포 이야기)을 처음부터 끝까지 만드는 절차. 대본은 Claude가 직접 쓰고(Anthropic API 호출 없음), TTS·자막·줌/크로스페이드 렌더·BGM 믹싱은 저장소 엔진(pipeline step5~7)을 그대로 쓴다. 종혁님이 "이 주제로 영상 만들어줘", "부처님 말씀 영상", "경전 내용으로 10분짜리", "반야심경/금강경/법구경 … 영상", "실록에서 미스터리한 사건 하나 해봐", "야화 하나 만들어", "숏 만들듯 여기서 만들어줘"처럼 주제·경전·길이를 주고 영상 제작을 요청하면 앱(Gradio)을 띄우지 말고 반드시 이 스킬을 따른다.
---

# 세션 안에서 롱폼 영상 만들기 (YOUTUBENEWS)

2026-10 반야심경 「불생불멸」 10분 영상을 이 방식으로 만들었고 종혁님이 "이 방식 딱 좋다"고 확정했다.
그 결과물의 대본·그림 설계가 `examples/`에 있으니 처음이면 먼저 열어 본다.
두 번째로 야화 채널용 「1609년 강원도 하늘의 괴물체」(광해군일기, 약 9분)를 만들었다 — 화자별 목소리·싼 2×2 시트·미스터리 배경음이 이때 정해졌다.

## 종혁님이 기대하는 결과 (요구사항)

- **사실 기반**: 픽션 금지. 경전 본문·경전 속 일화·문답, 실록 기사 원문만 쓴다. 실록은 국사편찬위원회 sillok.history.go.kr 기사 원문·국역을 직접 받아(WebFetch는 요약해 버리니 curl로 받아 텍스트 추출) 그대로 인용한다. 현대 해설(예: 파도 비유)은 "오늘날 자주 쓰는 설명"이라고 밝힌다. 원문이 확실하지 않은 구절·숫자는 쓰지 않는다.
- **이야기 흐름**: 경전 — 질문으로 열고(후킹) → 경전 배경 → 핵심 구절 → 비유·해설 → 오해 바로잡기 → 다른 경전 연결 → 정리·맺음.
  실록 야화 — 장면으로 열기 → "지어낸 이야기가 아니다" + 기록 소개 → 원문을 화자별 목소리로 낭독(나레이터가 사이사이 시각·단위 풀이) → 기록의 디테일 → 오늘날 해석(해석이라고 밝힘) → 풀리지 않는 부분 → 맺음.
- **나레이터 — 채널마다 다르다** (종혁님이 샘플 10종을 듣고 고름):
  - **야화(실록·괴이)**: **Seulki** `ksaI0TCD9BstzEzlxj4q`, 속도 1.0, 실측 약 6.9자/초. 기본 음성은 이 채널에 "너무 느리다"고 했다. `script.json`의 `voices.narrator`에 넣는다.
  - **부처님 말씀**: 아래 기본 음성.
- **목소리(부처님 말씀 기본)**: 종혁님이 앱에서 쓰는 그 여성 음성 = 엔진 `elevenlabs2.5`(Turbo v2.5) + 스타일 `불교강의`(voice `4p0HBzAAGyju0nYfNntV`, 한국어 기본 음성) + **속도 1.0**(앱 기본 0.9보다 조금 빠르게 — 종혁님 요청). `scripts/tts.py`의 기본값이 이것이다.
  ※ 첫 제작 때 config의 `불교종교`(voice `zgDzx5jL…`, v3 엔진)를 잘못 골랐다가 다시 만들었다. `불교종교`는 앱 스타일 목록에 없다.
- **그림 — 돈을 아끼고, 한 번에 뽑아 잘라 쓴다**: 품질은 좀 떨어져도 되지만 일관성은 지킨다. 기본은 **`build_prompts.py --cheap`의 2×2 시트**(gpt-image-1-mini 1536×1024 medium, 시트 1장=출력 1,668토큰=컷 4개, 2번 시트부터 1번 시트를 참조). fal 키가 있으면 컷별 fal(4-A)도 싸지만 컷마다 따로 그려 일관성은 시트보다 약하다. 4K gpt-image-2 시트는 종혁님이 고품질을 명시할 때만, 비용을 먼저 알리고.
- **화풍은 Claude가 정한다**: 종혁님이 화풍을 말하지 않으면 경전의 시대·장소와 분위기에 맞춰 Claude가 고른다(필요하면 한 줄로 물어봐도 된다). 저장소의 화풍 블록(korea 수묵담채 / china 도상화 / india 스케치)은 출발점일 뿐 꼭 따를 필요는 없다 — `fal_images.py --style "..."`로 직접 쓴 화풍 문장을 줄 수 있다.
- **실패는 돈이다**: 유료 API가 실패하면 자동 재시도하지 말고 원인부터 확인한다.
- **연출**: 그림을 그대로 두지 말고 줌인/줌아웃·팬으로 움직이고, 그림 사이는 크로스페이드(엔진 기본 1초).
- **목소리 — 화자마다 따로**: 나레이터는 위 기본 음성. 인용·보고·대사 등 다른 화자가 있으면 화자마다 다른 목소리를 Claude가 골라 `script.json`의 `voices`에 넣는다(5번 참고). ElevenLabs 글자 수는 넉넉하다.
- **배경음 — 내용 분위기에 맞춘다**: 불교·명상은 `meditation`, 야화·괴이·공포는 `mystery` 프리셋. 처음부터 끝까지 깐다.
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
`예상 초 = 총 글자수 / 4.4 + 1.5 + 2 × 씬수` (기본 음성 기준 — 야화 Seulki는 6.9, 남성 보고 화자는 0.9 속도로 약 6.4를 쓴다). 10분이면 20씬 기준 약 2,450자, 25씬이면 약 2,400자.
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

**B(기본, 2×2 시트)**: `visual.json` — 아래 형식. 사람 무리(마을 사람들 등)도 `characters`에 이름(예: VILLAGERS)으로 넣어야 한다 — 이름이 없는 컷은 자동으로 'no people'이 붙는다.

`examples/heart_sutra_visual.json` 형식: `style`(화풍 한 문단), `characters`(이름 → 외모·옷), `panels`(컷 설명, 영상 순서).
- `panels` 수 = `script.json`의 `images` 합계, **4의 배수**로 맞춘다(2×2 시트 단위).
- 컷 설명에 인물을 넣을 때는 `characters`의 **대문자 이름 그대로** 쓴다. 이름이 없는 컷은 자동으로 "no people"이 붙는다.
- 인물은 외모가 서로 확실히 구분되게(나이·체형·옷 색) 정한다.

### 4-A. 그림 생성 — fal (FAL_KEY가 있을 때, 컷별)

```bash
S=.claude/skills/longform-in-session/scripts; W=projects/<이름>
python $S/fal_images.py $W --style "<Claude가 정한 화풍 문장>"   # 또는 --region korea|china|india (저장소 화풍 블록)
```
- 화풍은 저장소 `storymaker/ai_prompt_generator.py`의 `REGIONAL_ENGINE_STYLES[region]["fal"]`(앱의 이미지 스타일 드롭다운과 같은 것)를 쓴다.
- 결과는 1024×576 정도라 1080p에서 약간 부드럽다 — 종혁님 기준으로 충분하다.
- 실패하면 멈춘다. 다시 실행하면 이미 만든 컷은 건너뛰니 재과금이 없다.
- 생성 후 밀착 시트로 분위기·내용이 맞는지 확인하고, 엉뚱한 컷만 지우고 다시 실행한다.

### 4-B. 그림 생성 — 싼 2×2 시트 (기본)

```bash
python $S/build_prompts.py $W/visual.json $W --cheap
python $S/imggen.py $W/jobs/sheet_1.json          # 1번 먼저 → 눈으로 확인(화풍·시대·구분선)
for k in 2 3 4 5 6; do python $S/imggen.py $W/jobs/sheet_$k.json & done; wait   # 1번을 참조
for k in 1 2 3 4 5 6; do python $S/split_sheet.py $W/sheets/sheet_$k.jpg $((4*k-3)) $W/panels; done
```
- 컷은 약 760×500(3:2)이다. 엔진이 16:9로 위아래를 조금 잘라 1080p로 키운다 — 부드럽지만 종혁님이 감수한 품질.
- 구분선이 흰색으로 나오기도 한다 → `split_sheet.py`는 색이 아니라 '균일함'(표준편차 최소)으로 선을 찾는다.

### 4-C. 그림 생성 — OpenAI 컷별 / 4K 시트 (특별한 경우)

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

### 5. 전체 TTS — 화자별 목소리

`script.json`에 화자 목소리를 넣고, 씬 텍스트 안에 `[@화자]` 태그로 바꾼다(태그 앞은 narrator, `[@narrator]`로 되돌림). 태그는 자막에서 자동으로 지워진다.
```json
"voices": {"narrator": "4p0HBzAAGyju0nYfNntV", "강릉": "K3qo7ugXmpT87FDhLBbN", "양양": "ZZ4xhVcc83kZBfNIlIIz"},
"voice_speed": {"강릉": 0.9, "양양": 0.9}
```
쓸 수 있는 음성(이 키는 voices_read 권한이 없어 목록 조회 불가 → 저장소 config·youtubemaker에 있던 ID). 같은 문장으로 잰 값:

| 이름 | voice_id | 음높이 | 속도(1.0) | 쓰임 |
|---|---|---|---|---|
| 나레이터(종혁님 기본, 여성) | 4p0HBzAAGyju0nYfNntV | ~176Hz | 4.2자/초 | 부처님 말씀 해설 (야화엔 느림) |
| **Seulki (여성)** | ksaI0TCD9BstzEzlxj4q | – | 6.9 | **야화 나레이터 (종혁님 선택)** |
| Anna Kim (여성) | uyVNoMrnUku1dZyVEXwD | – | 7.4 | 여성 화자 |
| 불교종교 여성 | zgDzx5jLLCqEp6Fl7Kl7 | – | 6.3 | 여성 화자 |
| kr_male | 1W00IGEmNmwmsDeYy7ag | ~121Hz | 6.7 | 굵은 남성 |
| Harry Kim | pb3lVZVjdFWbkhPKlelB | ~120Hz | 6.8 | 대화형 남성 |
| K3qo7u | K3qo7ugXmpT87FDhLBbN | ~149Hz | 6.6 | 스토리텔링 |
| Im Pildu (암행어사) | ZZ4xhVcc83kZBfNIlIIz | ~173Hz | 7.7 | 권위 있는 인물 |
| Taehyung | m3gJBS8OofDJfycyA2Ip | ~213Hz | 8.5 | 젊은 남성 |
| Dolsoi | IAETYMYM3nJvjnlkVTKI | ~173Hz | 5.9 | 코믹 — 진지한 이야기엔 쓰지 않음 |

목소리를 새로 고를 때는 같은 문장을 여러 목소리로 읽힌 샘플(앞에 번호만큼 '삑')을 한 파일로 만들어 종혁님께 들려주고 고르게 한다 — Claude는 들을 수 없다.
남성 음성들은 기본 나레이터보다 1.6배쯤 빨라 `voice_speed` 0.9를 준다. 길이 계산 때 화자 부분은 약 6자/초로 잡는다.


```bash
python $S/tts.py $W --sample 1     # 첫 씬만 → sample.mp3 를 종혁님께 보내 목소리 확인
python $S/tts.py $W                # 기본값: elevenlabs2.5 / 불교강의 / 1.0
```
`불교강의`는 v2.5 감정표에 없어 전 구간 neutral 톤으로 나간다(앱과 동일).
결과 `audio_full.mp3` 길이를 확인하고 요청 길이와 크게 다르면 대본을 다듬어 다시 합성한다.

### 6. 배경음

```bash
python $S/make_bgm.py $W <오디오길이+20초> --preset meditation|mystery
```
ElevenLabs 키에 음악 생성 권한이 없어서 효과음을 생성해 배치한다 — meditation: 드론·싱잉볼·피리·종 / mystery: 어두운 드론·찬 바람·먼 천둥·북·징. 새 분위기가 필요하면 `PRESETS`에 추가한다. 결과는 `bgm.mp3`.
종혁님께는 "효과음으로 구성한 배경음"이라고 사실대로 말한다.

### 7. 렌더

```bash
nohup python $S/render.py $W --bgm-volume 0.18   # mystery는 0.2 > $W/render.log 2>&1 &
```
10분 영상에 약 30분 걸린다(4코어). 기다릴 때는 `render.log`를 확인하는 until 루프를 쓴다.

### 7-1. 썸네일 + 채널 오프닝·엔딩 붙이기 (야화 채널은 항상)

```bash
# 썸네일: thumb.json(배경 컷, 인물 위치, 태그, 줄별 글자·색, 소제목) → thumbnail.jpg(1920) + thumbnail_yt.jpg(1280, 업로드용)
python $S/thumbnail.py $W
python $S/brand.py $W --channel yahwa --intro-image panels/panel_XX.jpg --outro-image panels/panel_YY.jpg --thumbnail thumbnail.jpg --thumb-sec 3
```
- 썸네일 기본 디자인 = **종혁님이 youtubemaker에서 만든 '야담' 썸네일**(`thumbnail.py`의 `layout: "yadam"`, 원본과 픽셀 차이 평균 0.6으로 동일 확인): 1280×720, 배경 어둡게(darken 0.35~0.45), 가운데 정렬, 상단 흰 글씨 / 메인 금색 2줄(외곽선+그림자) / 하단 연금색, 가평한석봉체. Claude가 따로 만든 `layout: "side"`(정자체+빨간 태그)는 종혁님이 "화면 구성을 못한다"고 평가했다 — 요청 없으면 쓰지 않는다.
- 썸네일 문구 규칙(종혁님 youtube_metadata_engine.py): 메인은 **2줄** — 1줄 수식어·상황(3~8자), 2줄 핵심 메시지(5~12자). 좋은 예 "그날 밤\n사라진 신부", "떠난 다음 날\n처가에 닥친 화". 나쁜 예 "충격\n진실이 밝혀졌다"(너무 일반적). 유튜브 제목과 같을 필요 없다. 사실과 어긋나는 문구 금지(예: 토정비결을 쓰지 않은 사람에게 "토정비결의 주인").
- 배경 컷: 메인 글씨가 가운데 오므로 얼굴이 정중앙인 컷은 글씨에 가린다 — 인물이 한쪽에 있거나 실루엣·풍경 컷이 낫다. 2장 이상 시안을 만들어 종혁님이 고르게 한다.
- 영상 맨 앞에 썸네일을 3초 보여 주고(찬 바람 소리 아주 작게) 번개 오프닝으로 크로스페이드한다.
- 본편(final.mp4)은 다시 렌더하지 않고 앞뒤에 붙인다 → `final_branded.mp4`. 이후 검증·전달은 이 파일로.
- 오프닝: 채널 고정 효과음(번개+천둥, `assets/channels/yahwa/opening.mp3`) + 흰 번개 섬광 + 어둡게 줌. 오프닝 그림은 이 편의 어두운 하늘/밤 장면이 잘 어울린다.
- 엔딩: 나레이터 멘트 "…좋아요와 구독 부탁드립니다. 오늘도 신비한 실록의 이야기를 찾아서…" + 채널 고정 엔딩 음악(대금·장구) + 자막 + 페이드아웃.
- 채널 고정 소리는 처음 한 번 생성해 저장소에 넣어 두었다(종혁님 요청: 한 번 정한 오프닝 소리를 계속 쓴다). 바꾸려면 파일을 지우고 다시 실행한다. 멘트는 `assets/channels/yahwa.json`의 `outro_text`.
- 음량: 본편 최종 믹스의 나레이션 음량을 재서 엔딩 목소리를 거기에 맞춘다(고정값을 쓰면 엔딩이 10dB 커졌었다).

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

## 유튜브 제목·설명·태그 (종혁님 youtube_metadata_engine.py 규칙)

- 제목: 50자 이내, **검색 키워드 필수**(야화: 조선왕조실록·실록·인물 이름·사건명·토정비결 같은 검색어), 호기심 요소(의문문, 숫자, "비밀", "아무도 몰랐던"), 감정 자극("소름", "충격")은 쓰되 **구체적인 내용**과 함께 — 뻔한 표현 금지. 대괄호로 경전·출처 키워드를 붙인다(종혁님 채널에서 반응 좋았던 형식). 2~3개 후보를 주고 추천 1개.
- 설명: 문단을 줄바꿈으로 나눈다 — [1] 핵심 스토리 2~3줄 [2] 챕터 타임스탬프(첫 줄 0:00, 썸네일·오프닝이 붙은 최종 영상 기준) [3] 출처·사실/전승 구분 [4] 해시태그.
- 태그: 짧은 키워드 + 롱테일("밤에 듣는 이야기", "조선시대 미스터리") 15~25개.

## 보고할 때

- 쓴 비용(이미지 호출 수·토큰), 다시 만든 컷과 그 이유, 확인 못 한 것은 그대로 말한다.
- 대본에서 사실과 해설을 어떻게 구분했는지 한 줄로 밝힌다.
