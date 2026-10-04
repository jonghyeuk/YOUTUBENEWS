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
- **목소리**: 차분한 여성. `config.py`의 `불교종교` 스타일(voice `zgDzx5jL…`, 속도 0.85)을 쓴다.
- **그림**: 시대와 내용에 맞고 **인물이 일관**돼야 한다. 그림 장수는 Claude가 정하고, **한 번에 그리드로 뽑아 잘라 쓴다**.
- **연출**: 그림을 그대로 두지 말고 줌인/줌아웃·팬으로 움직이고, 그림 사이는 크로스페이드(엔진 기본 1초).
- **배경음**: 사색적·명상적 불교 배경음을 처음부터 끝까지 깐다.
- **길이**: 요청 길이(예: 10분)에 맞춘다.

## 전체 순서

작업 폴더는 `projects/<영문이름>/`(gitignore 대상). 스크립트는 모두 이 스킬의 `scripts/`에 있다.

```
1. 대본 script.json 작성 ─┐
2. 길이 맞추기(샘플 TTS)  │
3. 그림 설계 visual.json  ├→ 4. 그림 생성·자르기 → 5. 전체 TTS → 6. BGM → 7. 렌더 → 8. 검증 → 9. 전달
```

### 0. 환경 준비 (새 컨테이너마다)

```bash
python3 -m venv /tmp/venv && . /tmp/venv/bin/activate
pip install -q --upgrade pip setuptools wheel
pip install -q "moviepy==1.0.3" pydub elevenlabs python-dotenv anthropic openai pillow numpy requests
```
시스템 pip로는 moviepy 1.0.3 빌드가 `install_layout` 오류로 실패한다 → venv를 쓴다.
키는 프록시가 주입한다(OpenAI·ElevenLabs). Gemini 키는 무효였다.

### 1. 대본 — `script.json`

형식은 `examples/heart_sutra_script.json`과 같다: `{"title", "scenes": [{"id","title","images","text"}]}`.
- 씬 25개 안팎, 씬당 110~150자. `images`는 씬에 들어갈 그림 수(1~2). 긴 씬·전환이 있는 씬은 2.
- 나레이션은 **한글만**(한자·숫자 금지: "기원전 이 세기", "이백육십 자"). TTS가 한자·숫자를 잘못 읽고, 자막도 이 텍스트가 그대로 나온다.
- 경전 인용은 독송음 그대로 쓰고 바로 뒤에 우리말 풀이를 붙인다.

### 2. 길이 맞추기

이 음성은 실측 **초당 약 5.7자**(공백 포함). 엔진이 시작 1.5초 + 씬마다 2초 무음을 넣는다.
`예상 초 = 총 글자수 / 5.7 + 1.5 + 2 × 씬수`. 10분이면 25씬 기준 약 3,100~3,300자.
전체 합성 전에 씬 1~2개만 합성해 속도를 확인하면 낭비가 없다.

### 3. 그림 설계 — `visual.json`

`examples/heart_sutra_visual.json` 형식: `style`(화풍 한 문단), `characters`(이름 → 외모·옷), `panels`(컷 설명, 영상 순서).
- `panels` 수 = `script.json`의 `images` 합계, **4의 배수**로 맞춘다(2×2 시트 단위).
- 컷 설명에 인물을 넣을 때는 `characters`의 **대문자 이름 그대로** 쓴다. 이름이 없는 컷은 자동으로 "no people"이 붙는다.
- 인물은 외모가 서로 확실히 구분되게(나이·체형·옷 색) 정한다.

### 4. 그림 생성·자르기

```bash
S=.claude/skills/longform-in-session/scripts; W=projects/<이름>
python $S/build_prompts.py $W/visual.json $W
python $S/imggen.py $W/jobs/ref.json                 # 인물 기준 시트 → 반드시 눈으로 확인
for j in $W/jobs/sheet_*.json; do python $S/imggen.py $j & done; wait   # 4개씩 병렬이면 충분
python $S/split_sheet.py $W/sheets/sheet_1.jpg 1 $W/panels          # 시트 k → 첫 컷 번호 4k-3
```
- 시트는 3840×2160, 2×2라서 컷 하나가 약 1912×1072다(1080p에 바로 맞음). 3×3은 컷이 1280×720이라 흐려지니 쓰지 않는다.
- **시트마다 직접 열어 확인**한다(축소본을 만들어 Read). 인물이 엉뚱한 칸에 들어가거나 시대가 틀린 칸은 그 칸만 단독 이미지(`size: "2048x1152"`, 참조 이미지 첨부)로 다시 만들어 해당 `panel_XX.jpg`를 덮어쓴다. 시트 전체를 다시 뽑는 것보다 싸다.
- 32컷 전체를 한 장의 밀착 시트로 만들어 순서·크롭을 마지막으로 확인한다.
- 비용: 4K 고품질 1장당 출력 13,600 이미지 토큰. 시트 8장 + 기준 시트면 약 12만 토큰.
- 429 `credit_balance_exhausted`가 나오면 즉시 멈추고 종혁님께 충전을 요청한다.

### 5. 전체 TTS

```bash
python $S/tts.py $W --style 불교종교 --calm
```
`--calm`: 해설·교리 내용이면 슬픔 계열 감정 태그를 차분한 태그로 바꾼다(이 실행에서만, config 변경 없음).
결과 `audio_full.mp3` 길이를 확인하고 요청 길이와 크게 다르면 대본을 다듬어 다시 합성한다.

### 6. 배경음

```bash
python $S/make_bgm.py $W <오디오길이+20초>
```
ElevenLabs 키에 음악 생성 권한이 없어서 효과음(드론·싱잉볼·피리·종)을 생성해 배치한다. 결과는 `bgm.mp3`.
종혁님께는 "효과음으로 구성한 배경음"이라고 사실대로 말한다.

### 7. 렌더

```bash
nohup python $S/render.py $W --style 불교종교 --bgm-volume 0.18 > $W/render.log 2>&1 &
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
