"""
Gradio UI - AI 콘텐츠 생성기
스타일: 뉴스/정보/믿거나말거나/불교종교
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

## 주제/내용
{topic}

## 작성 규칙
1. 객관적이고 사실 중심의 어조
2. "~입니다", "~했습니다" 형식의 뉴스 문체
3. 핵심 정보를 먼저, 상세 내용은 뒤에
4. 시청자가 신뢰할 수 있는 톤
5. {duration}분 분량으로 작성

## 구조
- 도입: 핵심 내용 요약
- 본문: 상세 내용 전개
- 마무리: 시사점 또는 전망""",

    "정보": """당신은 유익한 정보를 전달하는 전문가입니다.

## 주제/내용
{topic}

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

    "믿거나말거나": """당신은 흥미로운 이야기를 전하는 스토리텔러입니다.

## 주제/내용
{topic}

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

## 주제/내용 (사람의 상태/인생 상황)
{topic}

## 1단계: 감정 코드 분석
원본 내용이 건드리는 핵심 감정 코드를 파악하세요:
- 불안 / 죄책감 / 후회 / 구원욕구 / 희망 / 분노 / 고립 / 관계집착

## 2단계: 인생 상황 매핑
- 삶이 힘들 때 → 위로
- 돈이 안 풀릴 때 → 마음 다스림
- 관계가 자꾸 깨질 때 → 인연의 의미
- 불안해서 잠이 안 올 때 → 명상/평안

## 3단계: 불교적 서사 생성
파악한 감정코드 + 인생상황을 기반으로 불교/명상/신비스러운 톤의 서사를 만드세요.

## 작성 규칙
1. 명상적이고 신비로운 어조
2. "~입니다", "~합니다" 차분한 문체
3. 불교적 지혜/교훈 포함 (업보, 인연, 무상, 집착 등)
4. 시청자의 감정에 공감하며 위로
5. {duration}분 분량으로 작성

## 구조
- 도입: 공감되는 인생 상황 제시
- 본문: 불교적 관점에서 풀어가는 이야기
- 전환: 깨달음의 순간
- 마무리: 따뜻한 위로와 실천 가능한 마음가짐"""
}

# JSON 출력 형식 + 이미지 프롬프트 통합
INTEGRATED_OUTPUT_FORMAT = """

## 출력 형식 (JSON) - 대본 + 이미지 프롬프트 통합
각 씬마다 나레이션과 이미지 프롬프트를 함께 작성하세요.

```json
{{
  "title": "영상 제목",
  "scenes": [
    {{
      "scene_id": 1,
      "title": "씬 제목",
      "text": "나레이션 텍스트 (이 씬에서 읽을 내용)",
      "image_prompts": [
        "English image prompt 1 for this scene, detailed visual description, mood, lighting, composition",
        "English image prompt 2 for this scene (if needed)"
      ],
      "importance": 3
    }}
  ]
}}
```

## 이미지 프롬프트 규칙
- 영어로 작성
- 400자 이내
- 구체적인 시각적 묘사 (조명, 색감, 구도)
- 씬당 1~4개 (중요도에 따라)
- 전체 이미지 총합: {duration}분 영상 기준 약 {total_images}장"""

# 스타일별 이미지 스타일 가이드
STYLE_IMAGE_GUIDES = {
    "뉴스": "Professional news broadcast style, clean composition, neutral lighting",
    "정보": "Bright, friendly infographic style, clear visuals, warm colors",
    "믿거나말거나": "Dark mysterious atmosphere, dramatic lighting, suspenseful mood, shadows",
    "불교종교": "Serene meditation style, golden dawn light, lotus flowers, misty mountains, peaceful temple, soft glow, silhouette meditation pose"
}

# 스타일별 입력 가이드
STYLE_GUIDES = {
    "뉴스": "**💡 뉴스**: 사실 기반 내용을 입력하세요.",
    "정보": "**💡 정보**: 설명할 주제를 입력하세요. (예: 항산화 물질 5가지)",
    "믿거나말거나": "**💡 믿거나말거나**: 미스터리한 주제나 흥미로운 이야기를 입력하세요.",
    "불교종교": """**💡 불교종교**: '사람의 상태'로 입력하세요!

❌ 불교 업보, 기도하면 돈 벌까
✅ 삶이 힘들 때, 돈이 안 풀릴 때, 관계가 자꾸 깨질 때

**감정 코드**: 불안 / 죄책감 / 후회 / 구원욕구 / 희망 / 분노 / 고립"""
}

def update_style_guide(style: str):
    return STYLE_GUIDES.get(style, STYLE_GUIDES["정보"])


# ═══════════════════════════════════════════════════════════════
# 통합 스크립트 + 이미지 프롬프트 생성
# ═══════════════════════════════════════════════════════════════

def generate_script_and_images(topic: str, duration: int, style: str):
    """주제 입력 → 스크립트 + 이미지 프롬프트 한번에 생성"""
    if not topic.strip():
        return "❌ 주제를 입력해주세요", "", ""

    try:
        # 프로젝트 생성
        project = pipeline.create_project(topic, duration)

        # 분량에 따른 이미지 수 계산
        total_images = duration * 2  # 분당 약 2장

        # 스타일별 프롬프트 구성
        base_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["정보"])
        image_style = STYLE_IMAGE_GUIDES.get(style, "")

        prompt = base_prompt.format(topic=topic, duration=duration)
        prompt += INTEGRATED_OUTPUT_FORMAT.format(duration=duration, total_images=total_images)
        prompt += f"\n\n## 이미지 스타일\n{image_style}"

        # Claude API 호출
        from anthropic import Anthropic
        client = Anthropic()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
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

            # Script 객체 생성
            from models.types import Script, Scene
            scenes = []
            all_image_prompts = []

            for s in data["scenes"]:
                image_prompts = s.get("image_prompts", [])
                all_image_prompts.extend(image_prompts)

                scenes.append(Scene(
                    scene_id=s["scene_id"],
                    title=s["title"],
                    text=s["text"],
                    image_count=len(image_prompts),
                    importance=s.get("importance", 3)
                ))

            script = Script(
                title=data["title"],
                scenes=scenes,
                duration_min=duration,
                total_panels=len(all_image_prompts)
            )
            pipeline.project.script = script

            # 스크립트 미리보기
            preview = f"# {script.title}\n\n"
            preview += f"**{len(scenes)}개 씬 | 이미지 {len(all_image_prompts)}장**\n\n"

            for i, scene in enumerate(script.scenes):
                preview += f"### 씬 {scene.scene_id}: {scene.title}\n"
                preview += f"🖼️ {scene.image_count}장\n\n"
                preview += f"{scene.text}\n\n---\n\n"

            # 이미지 프롬프트 포맷팅
            prompts_text = ""
            for i, prompt in enumerate(all_image_prompts, 1):
                prompts_text += f"이미지 {i}: {prompt}\n\n"

            return f"✅ 생성 완료! {len(scenes)}개 씬, {len(all_image_prompts)}장 이미지", preview, prompts_text

        except json.JSONDecodeError:
            return "⚠️ JSON 파싱 실패 - 원본 확인", result_text, ""

    except Exception as e:
        return f"❌ 오류: {e}", "", ""


# ═══════════════════════════════════════════════════════════════
# TTS 생성
# ═══════════════════════════════════════════════════════════════

def generate_tts(engine: str):
    if not pipeline.project or not pipeline.project.script:
        return "❌ 스크립트 생성 필요", None
    try:
        audio_path = pipeline.step3_generate_tts(engine)
        total = sum(s.duration for s in pipeline.project.audio_segments)
        return f"✅ TTS 완료 ({total:.1f}초)", audio_path
    except Exception as e:
        return f"❌ 오류: {e}", None


# ═══════════════════════════════════════════════════════════════
# 이미지 생성
# ═══════════════════════════════════════════════════════════════

def parse_image_prompts(prompts_text: str):
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


def generate_images_from_text(prompts_text: str, engine: str):
    if not pipeline.project:
        return "❌ 스크립트 먼저 생성하세요", []
    try:
        prompts = parse_image_prompts(prompts_text)
        if not prompts:
            return "❌ 프롬프트 파싱 실패", []

        image_paths = pipeline.step4_generate_images_from_prompts(prompts=prompts, engine=engine)
        images = [Image.open(p) for p in image_paths]
        return f"✅ 이미지 생성 완료 ({len(images)}장)", images
    except Exception as e:
        return f"❌ 오류: {e}", []


# ═══════════════════════════════════════════════════════════════
# 영상 렌더링
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
# 트렌드 분석 (참고용)
# ═══════════════════════════════════════════════════════════════

def analyze_trend(keyword: str):
    if not keyword.strip():
        return "❌ 키워드 입력 필요", "", []
    try:
        videos = pipeline.step1_analyze_trend(keyword)
        result = "## 🔥 인기 영상\n\n"
        choices = []
        for i, v in enumerate(videos[:10], 1):
            result += f"**{i}. {v.title}**\n"
            result += f"- 조회수: {v.view_count:,} | 댓글: {v.comment_count:,}\n\n"
            choices.append(f"{i}. {v.title[:40]}... ({v.video_id})")
        return "✅ 분석 완료", result, gr.update(choices=choices, value=None)
    except Exception as e:
        return f"❌ 오류: {e}", "", []


def extract_transcript_and_comments(selection: str):
    if not selection:
        return "❌ 영상을 선택해주세요", "", ""
    try:
        video_id = selection.split("(")[-1].replace(")", "").strip()
    except:
        return "❌ 영상 ID 파싱 실패", "", ""

    transcript_text = ""
    comments_text = ""
    status_msg = []

    try:
        data = pipeline.step1b_extract_transcript(video_id)
        transcript_text = data["transcript"].original_text
        status_msg.append(f"✅ 자막: {len(transcript_text)}자")
    except Exception as e:
        if "disabled" in str(e).lower():
            transcript_text = "[자막 비활성화됨]"
            status_msg.append("⚠️ 자막 없음")
        else:
            status_msg.append("❌ 자막 실패")

    try:
        from engines.trend_engine import TrendEngine
        trend_engine = TrendEngine()
        comments = trend_engine.get_top_comments(video_id, max_results=15)
        if comments:
            comments_text = "## 💬 인기 댓글\n\n"
            for i, c in enumerate(comments[:10], 1):
                text = c.get("text", "").replace("\n", " ")[:150]
                comments_text += f"**{i}.** 👍{c.get('like_count', 0)} {text}\n\n"
            status_msg.append(f"✅ 댓글: {len(comments)}개")
    except:
        status_msg.append("❌ 댓글 실패")

    return " | ".join(status_msg), transcript_text, comments_text


# ═══════════════════════════════════════════════════════════════
# Gradio UI - 간소화된 버전
# ═══════════════════════════════════════════════════════════════

with gr.Blocks(title="AI 콘텐츠 생성기") as app:
    gr.Markdown("# 🎬 AI 콘텐츠 생성기")
    gr.Markdown("주제 입력 → 스타일 선택 → 스크립트/이미지/영상 자동 생성")

    status = gr.Textbox(label="📊 상태", lines=1, interactive=False)

    with gr.Tabs():
        # ─────────────────────────────────────────────
        # Tab 1: 스크립트 생성 (통합)
        # ─────────────────────────────────────────────
        with gr.Tab("1️⃣ 스크립트 생성"):
            with gr.Row():
                with gr.Column(scale=1):
                    topic_input = gr.Textbox(
                        label="📝 주제 / 내용",
                        placeholder="짧게: 삶이 힘들 때\n\n또는 길게: 요즘 직장에서 스트레스 받고 집에서도 힘들고 남편은 게임만 하고...\n\n또는 스토리: 어떤 여자가 있었는데 10년간 모은 돈을 사기당해서...",
                        lines=10
                    )

                    with gr.Row():
                        duration_input = gr.Radio(
                            [5, 10, 15, 20],
                            value=10,
                            label="영상 길이 (분)"
                        )

                    style_input = gr.Radio(
                        ["뉴스", "정보", "믿거나말거나", "불교종교"],
                        value="정보",
                        label="스타일"
                    )

                    style_guide = gr.Markdown(STYLE_GUIDES["정보"])

                    generate_btn = gr.Button("🚀 스크립트 생성", variant="primary", size="lg")

                with gr.Column(scale=2):
                    script_preview = gr.Markdown(label="📖 스크립트", value="*주제를 입력하고 생성 버튼을 누르세요*")

                    gr.Markdown("---")
                    gr.Markdown("### 🎨 이미지 프롬프트")
                    image_prompts = gr.Textbox(
                        label="생성된 이미지 프롬프트 (수정 가능)",
                        lines=10,
                        placeholder="스크립트 생성 후 자동으로 채워집니다"
                    )

        # ─────────────────────────────────────────────
        # Tab 2: TTS
        # ─────────────────────────────────────────────
        with gr.Tab("2️⃣ TTS"):
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
        # Tab 3: 이미지 생성
        # ─────────────────────────────────────────────
        with gr.Tab("3️⃣ 이미지 생성"):
            with gr.Row():
                with gr.Column():
                    image_engine = gr.Radio(
                        ["fal", "dalle", "imagen"],
                        value="fal",
                        label="이미지 엔진"
                    )
                    final_prompts = gr.Textbox(
                        label="이미지 프롬프트",
                        lines=8,
                        info="Tab 1에서 생성된 프롬프트가 자동으로 복사됩니다"
                    )
                    gen_images_btn = gr.Button("🎨 이미지 생성", variant="primary")
                with gr.Column():
                    images_gallery = gr.Gallery(label="생성된 이미지", columns=3)

        # ─────────────────────────────────────────────
        # Tab 4: 영상 렌더링
        # ─────────────────────────────────────────────
        with gr.Tab("4️⃣ 영상"):
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
                    subtitle_preview = gr.Textbox(label="자막 (SRT)", lines=6)
                    video_preview = gr.Video(label="영상")
                    final_video = gr.Video(label="최종 영상")

        # ─────────────────────────────────────────────
        # Tab 5: 트렌드 분석 (참고용)
        # ─────────────────────────────────────────────
        with gr.Tab("📊 트렌드 (참고)"):
            gr.Markdown("### 🔍 YouTube 트렌드 분석")
            gr.Markdown("*아이디어 참고용 - 인기 영상 검색*")

            with gr.Row():
                with gr.Column(scale=1):
                    trend_keyword = gr.Textbox(label="검색 키워드", placeholder="예: 삶이 힘들 때")
                    trend_btn = gr.Button("🔍 검색", variant="primary")

                    video_selector = gr.Dropdown(label="📺 영상 선택", choices=[], interactive=True)
                    extract_btn = gr.Button("📥 자막/댓글 추출")

                with gr.Column(scale=2):
                    trend_result = gr.Markdown()
                    with gr.Row():
                        transcript_result = gr.Textbox(label="자막", lines=8)
                        comments_result = gr.Markdown(label="댓글")

    # ═══════════════════════════════════════════════════════════════
    # 이벤트 연결
    # ═══════════════════════════════════════════════════════════════

    # 스타일 변경시 가이드 업데이트
    style_input.change(update_style_guide, [style_input], [style_guide])

    # Tab 1: 스크립트 생성
    generate_btn.click(
        generate_script_and_images,
        [topic_input, duration_input, style_input],
        [status, script_preview, image_prompts]
    )

    # 이미지 프롬프트 자동 복사
    image_prompts.change(lambda x: x, [image_prompts], [final_prompts])

    # Tab 2: TTS
    tts_btn.click(generate_tts, [tts_engine], [status, audio_preview])

    # Tab 3: 이미지 생성
    gen_images_btn.click(
        generate_images_from_text,
        [final_prompts, image_engine],
        [status, images_gallery]
    )

    # Tab 4: 영상
    subtitle_btn.click(generate_subtitles, [use_whisper], [status, subtitle_preview])
    render_btn.click(render_video, [use_ken_burns, use_bgm], [status, video_preview])
    final_btn.click(finalize_video, [], [status, final_video])

    # Tab 5: 트렌드
    trend_btn.click(analyze_trend, [trend_keyword], [status, trend_result, video_selector])
    extract_btn.click(extract_transcript_and_comments, [video_selector], [status, transcript_result, comments_result])


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
