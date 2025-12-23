"""
Gradio UI - 정보성 콘텐츠 생성기
스타일: 뉴스/정보/믿거나말거나
"""
import os
from dotenv import load_dotenv
load_dotenv()

import gradio as gr
from PIL import Image
import json

from pipeline import Pipeline
from engines import ScriptEngine, ImageEngine
from config import DURATION_SPECS

# 전역 파이프라인 인스턴스
pipeline = Pipeline()

# ═══════════════════════════════════════════════════════════════
# 스타일별 프롬프트 템플릿
# ═══════════════════════════════════════════════════════════════

STYLE_PROMPTS = {
    "뉴스": """당신은 뉴스 리포터입니다. 아래 내용을 뉴스 형식으로 전달하세요.

## 원본 내용
{source_text}

## 작성 규칙
1. 객관적이고 사실 중심의 어조
2. "~입니다", "~했습니다" 형식의 뉴스 문체
3. 핵심 정보를 먼저, 상세 내용은 뒤에
4. 시청자가 신뢰할 수 있는 톤
5. {duration}분 분량으로 작성

## 구조
- 도입: 핵심 내용 요약 (누가, 무엇을, 왜)
- 본문: 상세 내용 전개
- 마무리: 시사점 또는 전망""",

    "정보": """당신은 유익한 정보를 전달하는 전문가입니다. 아래 내용을 정보 영상으로 구성하세요.

## 원본 내용
{source_text}

## 작성 규칙
1. 친근하고 이해하기 쉬운 설명
2. "~해요", "~거든요" 형식의 친근한 문체
3. 핵심 포인트를 명확히 강조
4. 실생활에 적용 가능한 팁 포함
5. {duration}분 분량으로 작성

## 구조
- 도입: 왜 이 정보가 중요한지
- 본문: 핵심 정보 1, 2, 3... 순서대로
- 마무리: 정리 및 실천 방법""",

    "믿거나말거나": """당신은 흥미로운 이야기를 전하는 스토리텔러입니다. 아래 내용을 "믿거나 말거나" 스타일로 구성하세요.

## 원본 내용
{source_text}

## 작성 규칙
1. 호기심을 자극하는 미스터리한 어조
2. "~라고 합니다", "~일까요?" 형식
3. 의문을 던지고 서스펜스 유지
4. 충격적인 반전이나 결말
5. {duration}분 분량으로 작성

## 구조
- 도입: 충격적인 훅으로 시작
- 본문: 의문점을 하나씩 풀어가며
- 마무리: 열린 결말 또는 반전""",

    "불교종교": """당신은 불교적 관점에서 삶의 지혜를 전하는 스토리텔러입니다.

## 원본 내용 (사람의 상태/인생 상황)
{source_text}

## 1단계: 감정 코드 분석
원본 내용이 건드리는 핵심 감정 코드를 파악하세요:
- 불안 / 죄책감 / 후회 / 구원욕구 / 희망 / 분노 / 고립 / 관계집착

## 2단계: 인생 상황 매핑
이 내용이 대변하는 '인생 상황'을 파악하세요:
- 삶이 힘들 때 → 위로
- 돈이 안 풀릴 때 → 마음 다스림
- 관계가 자꾸 깨질 때 → 인연의 의미
- 불안해서 잠이 안 올 때 → 명상/평안

## 3단계: 불교적 서사 생성
파악한 감정코드 + 인생상황을 기반으로 불교/명상/신비스러운 톤의 일상 사연 서사를 만드세요.

## 작성 규칙
1. 명상적이고 신비로운 어조
2. "~입니다", "~합니다" 차분한 문체
3. 불교적 지혜/교훈 포함 (업보, 인연, 무상, 집착 등)
4. 시청자의 감정에 공감하며 위로
5. 일상적 사연 → 불교적 깨달음 흐름
6. {duration}분 분량으로 작성

## 구조
- 도입: 공감되는 인생 상황 제시 (누구나 한번쯤 겪는 힘든 순간)
- 본문: 불교적 관점에서 풀어가는 이야기 (스님 말씀, 경전 인용, 명상 등)
- 전환: 깨달음의 순간
- 마무리: 따뜻한 위로와 실천 가능한 마음가짐"""
}

# 공통 JSON 출력 형식
JSON_OUTPUT_FORMAT = """

## 이미지 배분 규칙
각 씬마다 image_count(1~5)와 importance(1~5)를 지정:
- 핵심 장면: image_count 3~5, importance 4~5
- 일반 장면: image_count 1~2, importance 2~3

## 출력 형식 (JSON)
```json
{{
  "title": "영상 제목",
  "scenes": [
    {{
      "scene_id": 1,
      "title": "씬 제목",
      "text": "나레이션 텍스트",
      "image_count": 2,
      "importance": 3
    }}
  ]
}}
```"""

DEFAULT_IMAGE_PROMPT_TEMPLATE = """당신은 이미지 프롬프트 전문가입니다.
각 씬에 지정된 이미지 개수만큼 프롬프트를 영어로 작성해주세요.

## 규칙
- 400자 이내
- 장면 연출에 초점
- 일관된 스타일 유지
- 구체적인 시각적 묘사

## 이미지 배분 원칙
- 중요 씬(importance 4-5): 감정 변화별로 다른 장면
- 일반 씬(importance 2-3): 핵심 순간 위주"""

# 스타일별 이미지 프롬프트 템플릿
STYLE_IMAGE_PROMPTS = {
    "뉴스": DEFAULT_IMAGE_PROMPT_TEMPLATE,
    "정보": DEFAULT_IMAGE_PROMPT_TEMPLATE,
    "믿거나말거나": DEFAULT_IMAGE_PROMPT_TEMPLATE + """

## 스타일 특징
- 어두운 분위기, 서스펜스
- 미스터리한 조명과 그림자
- 긴장감 있는 구도""",
    "불교종교": """당신은 불교/명상 스타일 이미지 프롬프트 전문가입니다.
각 씬에 지정된 이미지 개수만큼 프롬프트를 영어로 작성해주세요.

## 규칙
- 400자 이내
- 명상적이고 신비로운 분위기
- 따뜻하고 위로가 되는 이미지
- 자연, 고요함, 빛 활용

## 스타일 특징
- 부드러운 황금빛/새벽빛 조명
- 연꽃, 물결, 산, 사찰 등 불교적 요소
- 평화로운 자연 배경 (대나무, 안개 낀 산)
- 명상하는 실루엣
- 촛불, 향 연기, 기도하는 손
- 밤하늘 별, 보름달

## 감정 코드별 비주얼
- 불안/고립: 안개 속 외로운 실루엣 → 빛이 비추는 장면으로 전환
- 후회/죄책감: 어두운 곳에서 빛을 향해 걸어가는 모습
- 희망/구원: 연꽃이 피어나는 장면, 해돋이
- 평안/깨달음: 고요한 호수에 비친 달, 명상 자세

## 이미지 배분 원칙
- 도입 씬: 공감되는 힘든 상황 비주얼
- 본문 씬: 점점 밝아지는 톤
- 마무리 씬: 평화롭고 따뜻한 장면"""
}


# 스타일별 입력 가이드
STYLE_GUIDES = {
    "뉴스": """**💡 입력 팁**: 뉴스 기사나 사실 기반 내용을 붙여넣으세요.""",
    "정보": """**💡 입력 팁**: 설명할 주제나 정보를 입력하세요. (예: 항산화 물질 5가지)""",
    "믿거나말거나": """**💡 입력 팁**: 미스터리한 주제나 흥미로운 이야기를 입력하세요.""",
    "불교종교": """**💡 불교종교 스타일**: '사람의 상태'로 입력하세요!

❌ 잘못된 입력: 불교 업보, 기도하면 돈 벌까, 전생 인연
✅ 올바른 입력: 삶이 힘들 때, 돈이 안 풀릴 때, 관계가 자꾸 깨질 때, 불안해서 잠이 안 올 때

→ **감정 코드**: 불안 / 죄책감 / 후회 / 구원욕구 / 희망 / 분노 / 고립 / 관계집착
→ 이 감정을 자극하는 인생 상황으로 입력하면 공감 높은 서사가 생성됩니다."""
}

def update_style_guide(style: str):
    """스타일 변경시 가이드 업데이트"""
    return STYLE_GUIDES.get(style, STYLE_GUIDES["정보"])


def get_style_image_prompt(style: str):
    """스타일에 맞는 이미지 프롬프트 템플릿 반환"""
    return STYLE_IMAGE_PROMPTS.get(style, DEFAULT_IMAGE_PROMPT_TEMPLATE)


# ═══════════════════════════════════════════════════════════════
# Step 1: 프로젝트 생성
# ═══════════════════════════════════════════════════════════════

def create_project(topic: str, duration: int, style: str):
    """프로젝트 생성"""
    if not topic.strip():
        return "❌ 주제를 입력해주세요", ""

    project = pipeline.create_project(topic, duration)

    # 스타일별 프롬프트 준비
    style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["정보"])

    info = f"✅ 프로젝트 생성: {project.project_id}\n📝 스타일: {style}"
    return info, style


def prepare_script_prompt(source_text: str, duration: int, style: str):
    """스타일에 맞는 스크립트 프롬프트 생성"""
    if not source_text.strip():
        source_text = "[주제를 직접 입력하거나 원본 텍스트를 붙여넣으세요]"

    base_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["정보"])
    prompt = base_prompt.format(
        source_text=source_text[:5000],
        duration=duration
    )
    prompt += JSON_OUTPUT_FORMAT

    return prompt


# ═══════════════════════════════════════════════════════════════
# Step 2: 스크립트 생성
# ═══════════════════════════════════════════════════════════════

def generate_script_with_prompt(prompt: str):
    """편집된 프롬프트로 스크립트 생성"""
    if not pipeline.project:
        return "❌ 프로젝트 생성 필요", "", ""

    try:
        from anthropic import Anthropic
        client = Anthropic()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text

        # JSON 파싱
        try:
            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                json_str = result_text[start:end]
            else:
                json_str = result_text

            data = json.loads(json_str)

            from models.types import Script, Scene
            scenes = [
                Scene(
                    scene_id=s["scene_id"],
                    title=s["title"],
                    text=s["text"],
                    image_count=s.get("image_count", 2),
                    importance=s.get("importance", 3)
                )
                for s in data["scenes"]
            ]

            total_images = sum(s.image_count for s in scenes)

            script = Script(
                title=data["title"],
                scenes=scenes,
                duration_min=pipeline.project.duration_min,
                total_panels=total_images
            )
            pipeline.project.script = script

            # 미리보기
            preview = f"# {script.title}\n\n"
            preview += f"**총 {len(scenes)}개 씬 | 이미지 {total_images}장**\n\n"

            for scene in script.scenes:
                stars = "⭐" * scene.importance
                preview += f"## 씬 {scene.scene_id}: {scene.title}\n"
                preview += f"🖼️ {scene.image_count}장 | {stars}\n\n"
                preview += f"{scene.text}\n\n---\n\n"

            return "✅ 스크립트 생성 완료", preview, result_text

        except json.JSONDecodeError:
            return "⚠️ JSON 파싱 실패", result_text, result_text

    except Exception as e:
        return f"❌ 오류: {e}", "", ""


# ═══════════════════════════════════════════════════════════════
# Step 3: TTS 생성
# ═══════════════════════════════════════════════════════════════

def generate_tts(engine: str):
    """TTS 생성"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 스크립트 생성 필요", None

    try:
        audio_path = pipeline.step3_generate_tts(engine)
        total = sum(s.duration for s in pipeline.project.audio_segments)
        return f"✅ TTS 완료 ({total:.1f}초)", audio_path
    except Exception as e:
        return f"❌ 오류: {e}", None


# ═══════════════════════════════════════════════════════════════
# Step 4: 이미지 프롬프트
# ═══════════════════════════════════════════════════════════════

def get_image_allocation_summary():
    """이미지 배분 요약"""
    if not pipeline.project or not pipeline.project.script:
        return "스크립트 생성 후 확인 가능"

    summary = "## 📊 이미지 배분\n\n"
    total = 0

    for scene in pipeline.project.script.scenes:
        stars = "⭐" * scene.importance
        bar = "█" * scene.image_count + "░" * (5 - scene.image_count)
        summary += f"**씬 {scene.scene_id}**: {scene.title[:20]}\n"
        summary += f"  {bar} {scene.image_count}장 | {stars}\n\n"
        total += scene.image_count

    summary += f"---\n**총 이미지: {total}장**"
    return summary


def generate_image_prompts_with_claude(master_prompt: str):
    """Claude로 이미지 프롬프트 생성"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 스크립트 생성 필요", "", "스크립트 생성 후 확인 가능"

    try:
        from anthropic import Anthropic
        client = Anthropic()

        script_text = ""
        total_images = 0
        for scene in pipeline.project.script.scenes:
            stars = "⭐" * scene.importance
            script_text += f"[씬 {scene.scene_id}: {scene.title}]\n"
            script_text += f"이미지: {scene.image_count}장 | {stars}\n"
            script_text += f"{scene.text}\n\n"
            total_images += scene.image_count

        prompt = f"""{master_prompt}

## 스크립트 (총 {total_images}장)
{script_text}

## 출력 형식
이미지 1: [프롬프트]
이미지 2: [프롬프트]
..."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.content[0].text
        allocation = get_image_allocation_summary()
        return f"✅ 프롬프트 생성 완료 ({total_images}장)", result, allocation

    except Exception as e:
        return f"❌ 오류: {e}", "", get_image_allocation_summary()


def parse_image_prompts(prompts_text: str):
    """이미지 프롬프트 파싱"""
    lines = prompts_text.strip().split("\n")
    parsed = []

    for line in lines:
        line = line.strip()
        if line.startswith("이미지") or line.startswith("Image"):
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2 and parts[1].strip():
                    parsed.append(parts[1].strip())

    if not parsed:
        parsed = [l.strip() for l in lines if l.strip() and not l.startswith("#") and len(l.strip()) > 20]

    return parsed


# ═══════════════════════════════════════════════════════════════
# Step 5: 이미지 생성
# ═══════════════════════════════════════════════════════════════

def generate_images_from_text(prompts_text: str, engine: str):
    """이미지 생성"""
    if not pipeline.project:
        return "❌ 프로젝트 생성 필요", []

    try:
        prompts = parse_image_prompts(prompts_text)
        if not prompts:
            return "❌ 프롬프트 파싱 실패", []

        image_paths = pipeline.step4_generate_images_from_prompts(
            prompts=prompts,
            engine=engine
        )

        images = [Image.open(p) for p in image_paths]
        return f"✅ 이미지 생성 완료 ({len(images)}장)", images

    except Exception as e:
        return f"❌ 오류: {e}", []


# ═══════════════════════════════════════════════════════════════
# Step 6: 자막 & 영상
# ═══════════════════════════════════════════════════════════════

def generate_subtitles(use_whisper: bool):
    if not pipeline.project or not pipeline.project.audio_segments:
        return "❌ TTS 생성 필요", ""
    try:
        path = pipeline.step5_generate_subtitles(use_whisper)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return "✅ 자막 생성 완료", content[:2000]
    except Exception as e:
        return f"❌ 오류: {e}", ""


def render_video(use_ken_burns: bool, use_bgm: bool):
    if not pipeline.project or not pipeline.project.cut_paths:
        return "❌ 이미지 생성 필요", None
    try:
        video_path = pipeline.step6_render_video(use_ken_burns, use_bgm)
        return "✅ 렌더링 완료", video_path
    except Exception as e:
        return f"❌ 오류: {e}", None


def finalize_video():
    if not pipeline.project or not pipeline.project.video_path:
        return "❌ 렌더링 필요", None
    try:
        final_path = pipeline.step7_burn_subtitles()
        return "✅ 최종 영상 완료!", final_path
    except Exception as e:
        return f"❌ 오류: {e}", None


# ═══════════════════════════════════════════════════════════════
# 트렌드 분석 (선택적)
# ═══════════════════════════════════════════════════════════════

def analyze_trend(keyword: str):
    """트렌드 분석"""
    if not keyword.strip():
        return "❌ 키워드 입력 필요", ""

    try:
        videos = pipeline.step1_analyze_trend(keyword)
        result = "## 🔥 인기 영상\n\n"

        for i, v in enumerate(videos[:10], 1):
            result += f"**{i}. {v.title}**\n"
            result += f"- 조회수: {v.view_count:,} | 좋아요: {v.like_count:,}\n"
            result += f"- ID: `{v.video_id}`\n\n"

        return "✅ 분석 완료", result
    except Exception as e:
        return f"❌ 오류: {e}", ""


def extract_transcript(video_id: str):
    """자막 추출"""
    if not video_id.strip():
        return "❌ 영상 ID 입력 필요", ""

    try:
        data = pipeline.step1b_extract_transcript(video_id)
        text = data["transcript"].original_text
        return f"✅ 자막 추출 완료 ({len(text)}자)", text
    except Exception as e:
        return f"❌ 오류: {e}", ""


# ═══════════════════════════════════════════════════════════════
# Gradio UI
# ═══════════════════════════════════════════════════════════════

with gr.Blocks(title="AI 콘텐츠 생성기") as app:
    gr.Markdown("# 🎬 AI 콘텐츠 생성기")
    gr.Markdown("주제/원본 입력 → 스타일 선택 → 대본/이미지/영상 자동 생성")

    status = gr.Textbox(label="📊 상태", lines=2, interactive=False)
    selected_style = gr.State("정보")

    with gr.Tabs():
        # ─────────────────────────────────────────────
        # Tab 1: 프로젝트 생성
        # ─────────────────────────────────────────────
        with gr.Tab("1️⃣ 프로젝트"):
            with gr.Row():
                with gr.Column():
                    topic_input = gr.Textbox(
                        label="주제",
                        placeholder="예: 항산화 물질 5가지, 조선시대 미스터리",
                        lines=2
                    )
                    duration_input = gr.Radio([5, 10, 15, 20], value=10, label="영상 길이 (분)")

                    style_input = gr.Radio(
                        ["뉴스", "정보", "믿거나말거나", "불교종교"],
                        value="정보",
                        label="콘텐츠 스타일",
                        info="뉴스: 객관적 보도 | 정보: 친근한 설명 | 믿거나말거나: 미스터리 | 불교종교: 명상/위로/깨달음"
                    )

                    create_btn = gr.Button("🚀 프로젝트 생성", variant="primary")

                with gr.Column():
                    gr.Markdown("### 📝 원본 텍스트 (선택)")
                    style_guide = gr.Markdown("""**💡 입력 팁**: 기사/대본을 붙여넣거나 주제만 입력하세요.""")
                    source_input = gr.Textbox(
                        label="기사/대본 붙여넣기",
                        placeholder="뉴스 기사, 블로그 글, 또는 직접 작성한 내용을 여기에 붙여넣으세요.\n비워두면 주제만으로 생성합니다.",
                        lines=15
                    )

        # ─────────────────────────────────────────────
        # Tab 2: 스크립트 생성
        # ─────────────────────────────────────────────
        with gr.Tab("2️⃣ 스크립트"):
            gr.Markdown("### 📝 스크립트 생성")

            with gr.Row():
                with gr.Column():
                    script_prompt_input = gr.Textbox(
                        label="🔧 프롬프트 (수정 가능)",
                        lines=20
                    )
                    prepare_btn = gr.Button("📋 프롬프트 준비")
                    generate_script_btn = gr.Button("🚀 스크립트 생성", variant="primary")

                with gr.Column():
                    script_preview = gr.Markdown(label="생성된 스크립트")
                    script_raw = gr.Textbox(label="원본 JSON", lines=10, visible=False)

        # ─────────────────────────────────────────────
        # Tab 3: TTS
        # ─────────────────────────────────────────────
        with gr.Tab("3️⃣ TTS"):
            with gr.Row():
                with gr.Column():
                    tts_engine = gr.Radio(
                        ["wavenet", "elevenlabs", "openai"],
                        value="wavenet",
                        label="TTS 엔진"
                    )
                    tts_btn = gr.Button("🔊 TTS 생성", variant="primary")
                with gr.Column():
                    audio_preview = gr.Audio(label="생성된 오디오")

        # ─────────────────────────────────────────────
        # Tab 4: 이미지 프롬프트
        # ─────────────────────────────────────────────
        with gr.Tab("4️⃣ 이미지 프롬프트"):
            with gr.Row():
                with gr.Column(scale=2):
                    allocation_display = gr.Markdown(value="스크립트 생성 후 확인 가능")
                    refresh_btn = gr.Button("🔄 새로고침", size="sm")

                    image_master_prompt = gr.Textbox(
                        label="🔧 마스터 프롬프트",
                        lines=10,
                        value=DEFAULT_IMAGE_PROMPT_TEMPLATE
                    )
                    gen_prompts_btn = gr.Button("🤖 프롬프트 생성", variant="primary")

                with gr.Column(scale=3):
                    image_prompts_output = gr.Textbox(
                        label="📝 이미지 프롬프트 (편집 가능)",
                        lines=20,
                        placeholder="이미지 1: [프롬프트]\n이미지 2: [프롬프트]..."
                    )

        # ─────────────────────────────────────────────
        # Tab 5: 이미지 생성
        # ─────────────────────────────────────────────
        with gr.Tab("5️⃣ 이미지 생성"):
            with gr.Row():
                with gr.Column():
                    image_engine = gr.Radio(
                        ["fal", "dalle", "imagen"],
                        value="fal",
                        label="이미지 엔진"
                    )
                    final_prompts = gr.Textbox(label="최종 프롬프트", lines=10)
                    gen_images_btn = gr.Button("🎨 이미지 생성", variant="primary")

                with gr.Column():
                    images_gallery = gr.Gallery(label="생성된 이미지", columns=3)

        # ─────────────────────────────────────────────
        # Tab 6: 영상 렌더링
        # ─────────────────────────────────────────────
        with gr.Tab("6️⃣ 영상"):
            with gr.Row():
                with gr.Column():
                    use_whisper = gr.Checkbox(label="Whisper 자막", value=False)
                    subtitle_btn = gr.Button("📄 자막 생성")

                    gr.Markdown("---")
                    use_ken_burns = gr.Checkbox(label="Ken Burns 효과", value=True)
                    use_bgm = gr.Checkbox(label="BGM", value=False)
                    render_btn = gr.Button("🎬 렌더링")
                    final_btn = gr.Button("✅ 최종 영상", variant="primary")

                with gr.Column():
                    subtitle_preview = gr.Textbox(label="자막 (SRT)", lines=8)
                    video_preview = gr.Video(label="영상")
                    final_video = gr.Video(label="최종 영상")

        # ─────────────────────────────────────────────
        # Tab 7: 트렌드 분석 (선택)
        # ─────────────────────────────────────────────
        with gr.Tab("📊 트렌드 분석"):
            gr.Markdown("### 🔍 YouTube 트렌드 분석 (선택적 기능)")
            gr.Markdown("*참고용으로 인기 영상을 검색하고 자막을 추출할 수 있습니다*")

            with gr.Row():
                with gr.Column():
                    trend_keyword = gr.Textbox(label="검색 키워드", placeholder="예: 건강 정보")
                    trend_btn = gr.Button("🔍 트렌드 분석")

                    gr.Markdown("---")
                    video_id_input = gr.Textbox(label="영상 ID", placeholder="예: dQw4w9WgXcQ")
                    extract_btn = gr.Button("📜 자막 추출")

                with gr.Column():
                    trend_result = gr.Markdown(label="검색 결과")
                    transcript_result = gr.Textbox(label="추출된 자막", lines=10)

    # ═══════════════════════════════════════════════════════════════
    # 이벤트 연결
    # ═══════════════════════════════════════════════════════════════

    # Tab 1: 프로젝트 생성
    style_input.change(update_style_guide, [style_input], [style_guide])
    style_input.change(get_style_image_prompt, [style_input], [image_master_prompt])

    create_btn.click(
        create_project,
        [topic_input, duration_input, style_input],
        [status, selected_style]
    )

    # Tab 2: 스크립트
    prepare_btn.click(
        prepare_script_prompt,
        [source_input, duration_input, style_input],
        [script_prompt_input]
    )

    generate_script_btn.click(
        generate_script_with_prompt,
        [script_prompt_input],
        [status, script_preview, script_raw]
    )

    # Tab 3: TTS
    tts_btn.click(generate_tts, [tts_engine], [status, audio_preview])

    # Tab 4: 이미지 프롬프트
    refresh_btn.click(get_image_allocation_summary, [], [allocation_display])
    gen_prompts_btn.click(
        generate_image_prompts_with_claude,
        [image_master_prompt],
        [status, image_prompts_output, allocation_display]
    )
    image_prompts_output.change(lambda x: x, [image_prompts_output], [final_prompts])

    # Tab 5: 이미지 생성
    gen_images_btn.click(
        generate_images_from_text,
        [final_prompts, image_engine],
        [status, images_gallery]
    )

    # Tab 6: 영상
    subtitle_btn.click(generate_subtitles, [use_whisper], [status, subtitle_preview])
    render_btn.click(render_video, [use_ken_burns, use_bgm], [status, video_preview])
    final_btn.click(finalize_video, [], [status, final_video])

    # Tab 7: 트렌드 (선택)
    trend_btn.click(analyze_trend, [trend_keyword], [status, trend_result])
    extract_btn.click(extract_transcript, [video_id_input], [status, transcript_result])


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
