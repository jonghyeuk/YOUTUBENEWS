"""
Gradio UI - 프롬프트 편집 가능한 콘텐츠 생성기
각 단계별 입력 프롬프트 표시 및 수정 기능
"""
import gradio as gr
from PIL import Image
import os
import json

from pipeline import Pipeline
from engines import ScriptEngine, ImageEngine
from config import DURATION_SPECS

# 전역 파이프라인 인스턴스
pipeline = Pipeline()

# ═══════════════════════════════════════════════════════════════
# 기본 프롬프트 템플릿
# ═══════════════════════════════════════════════════════════════

DEFAULT_SCRIPT_PROMPT = """당신은 YouTube 영상 스크립트 작성 전문가입니다.
아래 원본 텍스트를 바탕으로 {duration}분 분량의 영상 스크립트를 작성해주세요.

## 원본 텍스트
{source_text}

## 작성 규칙
1. 한국 시니어 시청자를 위한 따뜻하고 친근한 톤
2. 감정적 공감을 불러일으키는 표현 사용
3. 씬 단위로 구분하여 작성
4. 각 씬에는 제목과 나레이션 텍스트 포함

## 출력 형식 (JSON)
```json
{{
  "title": "영상 제목",
  "scenes": [
    {{"scene_id": 1, "title": "씬 제목", "text": "나레이션 텍스트"}},
    ...
  ]
}}
```"""

DEFAULT_IMAGE_PROMPT_TEMPLATE = """당신은 이미지 프롬프트 전문가입니다.
아래 씬 내용을 바탕으로 이미지 생성용 프롬프트를 작성해주세요.

## 씬 정보
제목: {scene_title}
내용: {scene_text}

## 스타일 가이드
{style_prefix}

## 규칙
- 영어로 작성
- 400자 이내
- 장면 연출에 초점
- 구체적인 시각적 묘사 포함

이미지 프롬프트:"""


# ═══════════════════════════════════════════════════════════════
# 유틸리티 함수
# ═══════════════════════════════════════════════════════════════

def format_prompt_for_display(prompt: str, variables: dict = None) -> str:
    """프롬프트를 표시용으로 포맷"""
    if variables:
        try:
            return prompt.format(**variables)
        except KeyError:
            return prompt
    return prompt


# ═══════════════════════════════════════════════════════════════
# Step 1: 프로젝트 생성 & 트렌드 분석
# ═══════════════════════════════════════════════════════════════

def create_project(topic: str, duration: int):
    """프로젝트 생성"""
    if not topic.strip():
        return "❌ 주제를 입력해주세요", ""

    project = pipeline.create_project(topic, duration)
    info = f"✅ 프로젝트 생성: {project.project_id}"
    return info, ""


def analyze_trend(keyword: str):
    """트렌드 분석"""
    if not keyword.strip():
        return "❌ 키워드 입력 필요", ""

    try:
        videos = pipeline.step1_analyze_trend(keyword)
        result = "## 🔥 인기 영상\n\n"
        for i, v in enumerate(videos[:5], 1):
            result += f"{i}. **{v.title}**\n"
            result += f"   - 조회수: {v.view_count:,} | ID: `{v.video_id}`\n\n"
        return "✅ 트렌드 분석 완료", result
    except Exception as e:
        return f"❌ 오류: {e}", ""


def extract_transcript(video_id: str):
    """자막 추출"""
    if not video_id.strip():
        return "❌ 영상 ID 입력 필요", ""

    try:
        data = pipeline.step1b_extract_transcript(video_id)
        text = data["transcript"].text
        return f"✅ 자막 추출 완료 ({len(text)}자)", text
    except Exception as e:
        return f"❌ 오류: {e}", ""


# ═══════════════════════════════════════════════════════════════
# Step 2: 스크립트 생성 (프롬프트 편집 가능)
# ═══════════════════════════════════════════════════════════════

def prepare_script_prompt(source_text: str, duration: int):
    """스크립트 생성용 프롬프트 준비"""
    prompt = DEFAULT_SCRIPT_PROMPT.format(
        duration=duration,
        source_text=source_text[:3000] if source_text else "[주제 기반 생성]"
    )
    return prompt


def generate_script_with_prompt(prompt: str):
    """편집된 프롬프트로 스크립트 생성"""
    if not pipeline.project:
        return "❌ 프로젝트 생성 필요", "", ""

    try:
        # Claude API 호출
        from anthropic import Anthropic
        client = Anthropic()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text

        # JSON 파싱 시도
        try:
            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                json_str = result_text[start:end]
            else:
                json_str = result_text

            data = json.loads(json_str)

            # Script 객체 생성
            from models.types import Script, Scene
            scenes = [
                Scene(
                    scene_id=s["scene_id"],
                    title=s["title"],
                    text=s["text"]
                )
                for s in data["scenes"]
            ]
            script = Script(
                title=data["title"],
                scenes=scenes,
                duration_min=pipeline.project.duration_min
            )
            pipeline.project.script = script

            # 미리보기 생성
            preview = f"# {script.title}\n\n"
            for scene in script.scenes:
                preview += f"## 씬 {scene.scene_id}: {scene.title}\n"
                preview += f"{scene.text}\n\n"

            return "✅ 스크립트 생성 완료", preview, result_text

        except json.JSONDecodeError:
            return "⚠️ JSON 파싱 실패 (원본 텍스트 표시)", result_text, result_text

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
# Step 4: 이미지 프롬프트 생성 (프롬프트 편집 가능)
# ═══════════════════════════════════════════════════════════════

def prepare_image_prompts(style_prefix: str):
    """각 씬별 이미지 프롬프트 준비"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 스크립트 생성 필요", ""

    prompts = []
    for scene in pipeline.project.script.scenes:
        prompt = DEFAULT_IMAGE_PROMPT_TEMPLATE.format(
            scene_title=scene.title,
            scene_text=scene.text[:500],
            style_prefix=style_prefix or "Cinematic, high quality, detailed"
        )
        prompts.append(f"### 씬 {scene.scene_id}: {scene.title}\n```\n{prompt}\n```\n")

    return "✅ 프롬프트 준비 완료", "\n".join(prompts)


def generate_image_prompts_with_claude(master_prompt: str):
    """Claude로 이미지 프롬프트 일괄 생성"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 스크립트 생성 필요", ""

    try:
        from anthropic import Anthropic
        client = Anthropic()

        # 전체 스크립트 텍스트
        script_text = ""
        for scene in pipeline.project.script.scenes:
            script_text += f"[씬 {scene.scene_id}: {scene.title}]\n{scene.text}\n\n"

        prompt = f"""{master_prompt}

## 스크립트
{script_text}

## 출력 형식
각 씬별로 이미지 프롬프트를 영어로 작성해주세요:
씬 1: [프롬프트]
씬 2: [프롬프트]
..."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.content[0].text
        return "✅ 이미지 프롬프트 생성 완료", result

    except Exception as e:
        return f"❌ 오류: {e}", ""


def parse_and_show_image_prompts(prompts_text: str):
    """이미지 프롬프트 파싱 및 표시"""
    lines = prompts_text.strip().split("\n")
    parsed = []

    for line in lines:
        line = line.strip()
        if line.startswith("씬") or line.startswith("Scene"):
            # "씬 1: 프롬프트" 형식 파싱
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    parsed.append(parts[1].strip())

    if not parsed:
        # 줄별로 그냥 사용
        parsed = [l.strip() for l in lines if l.strip() and not l.startswith("#")]

    return parsed


# ═══════════════════════════════════════════════════════════════
# Step 5: 이미지 생성 (개별 프롬프트 편집 가능)
# ═══════════════════════════════════════════════════════════════

def generate_images_from_text(prompts_text: str, engine: str):
    """텍스트에서 프롬프트 추출 후 이미지 생성"""
    if not pipeline.project:
        return "❌ 프로젝트 생성 필요", []

    try:
        # 프롬프트 파싱
        prompts = parse_and_show_image_prompts(prompts_text)

        if not prompts:
            return "❌ 프롬프트를 파싱할 수 없습니다", []

        # 이미지 생성
        image_paths = pipeline.step4_generate_images_from_prompts(
            prompts=prompts,
            engine=engine
        )

        # 갤러리용 이미지 로드
        images = [Image.open(p) for p in image_paths]

        return f"✅ 이미지 생성 완료 ({len(images)}장)", images

    except Exception as e:
        return f"❌ 오류: {e}", []


# ═══════════════════════════════════════════════════════════════
# Step 6-7: 자막 & 영상
# ═══════════════════════════════════════════════════════════════

def generate_subtitles(use_whisper: bool):
    """자막 생성"""
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
    """영상 렌더링"""
    if not pipeline.project or not pipeline.project.cut_paths:
        return "❌ 이미지 생성 필요", None

    try:
        video_path = pipeline.step6_render_video(use_ken_burns, use_bgm)
        return "✅ 렌더링 완료", video_path
    except Exception as e:
        return f"❌ 오류: {e}", None


def finalize_video():
    """최종 영상"""
    if not pipeline.project or not pipeline.project.video_path:
        return "❌ 렌더링 필요", None

    try:
        final_path = pipeline.step7_burn_subtitles()
        return "✅ 최종 영상 완료!", final_path
    except Exception as e:
        return f"❌ 오류: {e}", None


# ═══════════════════════════════════════════════════════════════
# Gradio UI
# ═══════════════════════════════════════════════════════════════

with gr.Blocks(title="콘텐츠 생성기", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🎬 AI 콘텐츠 생성기")
    gr.Markdown("**프롬프트 편집 가능** - 각 단계의 AI 입력 프롬프트를 확인하고 수정할 수 있습니다")

    status = gr.Textbox(label="📊 상태", lines=2, interactive=False)

    with gr.Tabs():
        # ─────────────────────────────────────────────
        # Tab 1: 프로젝트 & 트렌드
        # ─────────────────────────────────────────────
        with gr.Tab("1️⃣ 프로젝트 & 트렌드"):
            with gr.Row():
                with gr.Column():
                    topic_input = gr.Textbox(label="주제 / 키워드", placeholder="예: 조선시대 이야기")
                    duration_input = gr.Radio([5, 10, 15, 20], value=10, label="영상 길이 (분)")
                    create_btn = gr.Button("프로젝트 생성", variant="primary")

                    gr.Markdown("---")
                    trend_btn = gr.Button("🔍 트렌드 분석")
                    video_id_input = gr.Textbox(label="참조 영상 ID", placeholder="예: dQw4w9WgXcQ")
                    extract_btn = gr.Button("📜 자막 추출")

                with gr.Column():
                    trend_result = gr.Markdown(label="트렌드 결과")
                    transcript_result = gr.Textbox(label="추출된 자막", lines=10)

        # ─────────────────────────────────────────────
        # Tab 2: 스크립트 생성 (프롬프트 편집)
        # ─────────────────────────────────────────────
        with gr.Tab("2️⃣ 스크립트 생성"):
            gr.Markdown("### 📝 스크립트 생성 프롬프트")
            gr.Markdown("*아래 프롬프트를 수정하여 스크립트 생성 방식을 조정할 수 있습니다*")

            with gr.Row():
                with gr.Column():
                    script_prompt_input = gr.Textbox(
                        label="🔧 입력 프롬프트 (Claude에게 보내는 명령)",
                        lines=20,
                        value=DEFAULT_SCRIPT_PROMPT
                    )
                    prepare_script_btn = gr.Button("📋 자막에서 프롬프트 준비")
                    generate_script_btn = gr.Button("🚀 스크립트 생성", variant="primary")

                with gr.Column():
                    script_preview = gr.Markdown(label="생성된 스크립트")
                    script_raw = gr.Textbox(label="원본 응답 (JSON)", lines=10, visible=False)

        # ─────────────────────────────────────────────
        # Tab 3: TTS
        # ─────────────────────────────────────────────
        with gr.Tab("3️⃣ TTS 생성"):
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
        # Tab 4: 이미지 프롬프트 (프롬프트 편집)
        # ─────────────────────────────────────────────
        with gr.Tab("4️⃣ 이미지 프롬프트"):
            gr.Markdown("### 🎨 이미지 프롬프트 생성")
            gr.Markdown("*Claude로 이미지 프롬프트를 생성하거나, 직접 작성할 수 있습니다*")

            with gr.Row():
                with gr.Column():
                    style_prefix_input = gr.Textbox(
                        label="스타일 프리픽스",
                        placeholder="예: Cinematic, Korean traditional, warm lighting",
                        lines=2
                    )

                    image_master_prompt = gr.Textbox(
                        label="🔧 이미지 프롬프트 생성 마스터 프롬프트",
                        lines=10,
                        value="""당신은 이미지 프롬프트 전문가입니다.
각 씬에 맞는 이미지 프롬프트를 영어로 작성해주세요.

규칙:
- 400자 이내
- 장면 연출에 초점
- 일관된 스타일 유지
- 구체적인 시각적 묘사"""
                    )

                    gen_prompts_btn = gr.Button("🤖 Claude로 프롬프트 생성")

                with gr.Column():
                    image_prompts_output = gr.Textbox(
                        label="📝 이미지 프롬프트 (편집 가능)",
                        lines=15,
                        placeholder="씬 1: [프롬프트]\n씬 2: [프롬프트]\n..."
                    )
                    gr.Markdown("*위 프롬프트를 직접 수정할 수 있습니다*")

        # ─────────────────────────────────────────────
        # Tab 5: 이미지 생성
        # ─────────────────────────────────────────────
        with gr.Tab("5️⃣ 이미지 생성"):
            gr.Markdown("### 🖼️ 이미지 생성")

            with gr.Row():
                with gr.Column():
                    image_engine = gr.Radio(
                        ["fal", "dalle", "imagen"],
                        value="fal",
                        label="이미지 엔진",
                        info="fal.ai(빠름) | DALL-E(고품질) | Imagen"
                    )

                    final_prompts = gr.Textbox(
                        label="최종 이미지 프롬프트 (편집 가능)",
                        lines=10,
                        placeholder="각 줄이 하나의 이미지 프롬프트입니다"
                    )

                    gen_images_btn = gr.Button("🎨 이미지 생성", variant="primary")

                with gr.Column():
                    images_gallery = gr.Gallery(label="생성된 이미지", columns=3)

        # ─────────────────────────────────────────────
        # Tab 6: 자막 & 영상
        # ─────────────────────────────────────────────
        with gr.Tab("6️⃣ 자막 & 영상"):
            with gr.Row():
                with gr.Column():
                    use_whisper = gr.Checkbox(label="Whisper 타임스탬프", value=False)
                    subtitle_btn = gr.Button("📄 자막 생성")

                    gr.Markdown("---")

                    with gr.Row():
                        use_ken_burns = gr.Checkbox(label="Ken Burns", value=True)
                        use_bgm = gr.Checkbox(label="BGM", value=False)

                    render_btn = gr.Button("🎬 영상 렌더링")
                    final_btn = gr.Button("✅ 최종 영상", variant="primary")

                with gr.Column():
                    subtitle_preview = gr.Textbox(label="자막 (SRT)", lines=10)
                    video_preview = gr.Video(label="영상")
                    final_video = gr.Video(label="최종 영상")

    # ═══════════════════════════════════════════════════════════════
    # 이벤트 연결
    # ═══════════════════════════════════════════════════════════════

    # Tab 1
    create_btn.click(create_project, [topic_input, duration_input], [status, trend_result])
    trend_btn.click(analyze_trend, [topic_input], [status, trend_result])
    extract_btn.click(extract_transcript, [video_id_input], [status, transcript_result])

    # Tab 2: 자막 → 프롬프트 준비
    def prep_script(transcript, duration):
        prompt = prepare_script_prompt(transcript, duration)
        return prompt

    prepare_script_btn.click(
        prep_script,
        [transcript_result, duration_input],
        [script_prompt_input]
    )

    generate_script_btn.click(
        generate_script_with_prompt,
        [script_prompt_input],
        [status, script_preview, script_raw]
    )

    # Tab 3
    tts_btn.click(generate_tts, [tts_engine], [status, audio_preview])

    # Tab 4: 이미지 프롬프트 생성
    gen_prompts_btn.click(
        generate_image_prompts_with_claude,
        [image_master_prompt],
        [status, image_prompts_output]
    )

    # Tab 4 → Tab 5: 프롬프트 복사
    image_prompts_output.change(
        lambda x: x,
        [image_prompts_output],
        [final_prompts]
    )

    # Tab 5
    gen_images_btn.click(
        generate_images_from_text,
        [final_prompts, image_engine],
        [status, images_gallery]
    )

    # Tab 6
    subtitle_btn.click(generate_subtitles, [use_whisper], [status, subtitle_preview])
    render_btn.click(render_video, [use_ken_burns, use_bgm], [status, video_preview])
    final_btn.click(finalize_video, [], [status, final_video])


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
