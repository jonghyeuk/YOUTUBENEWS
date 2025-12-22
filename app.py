"""
Gradio UI - 인기 영상 분석 기반 콘텐츠 생성
개별 이미지 생성 (fal.ai/DALL-E/Imagen)
"""
import gradio as gr
from PIL import Image
import os

from pipeline import Pipeline
from config import DURATION_SPECS


# 전역 파이프라인 인스턴스
pipeline = Pipeline()


def create_project(topic: str, duration: int):
    """프로젝트 생성"""
    if not topic.strip():
        return "❌ 주제를 입력해주세요", None, None

    project = pipeline.create_project(topic, duration)

    info = f"""✅ 프로젝트 생성 완료

📁 ID: {project.project_id}
⏱️ 길이: {duration}분
"""
    return info, None, None


def analyze_trend(keyword: str):
    """트렌드 분석"""
    if not keyword.strip():
        return "❌ 키워드를 입력해주세요", None

    try:
        videos = pipeline.step1_analyze_trend(keyword)

        result = "## 🔥 인기 영상\n\n"
        for i, v in enumerate(videos[:5], 1):
            result += f"{i}. **{v.title}**\n"
            result += f"   - 조회수: {v.view_count:,}\n"
            result += f"   - ID: `{v.video_id}`\n\n"

        return "✅ 트렌드 분석 완료", result

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


def extract_transcript(video_id: str):
    """자막 추출"""
    if not video_id.strip():
        return "❌ 영상 ID를 입력해주세요", None

    try:
        data = pipeline.step1b_extract_transcript(video_id)
        transcript = data["transcript"]

        return f"✅ 자막 추출 완료 ({len(transcript.text)}자)", transcript.text[:2000]

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


def generate_script(source_text: str = None):
    """스크립트 생성"""
    if not pipeline.project:
        return "❌ 먼저 프로젝트를 생성해주세요", None

    try:
        script = pipeline.step2_generate_script(source_text if source_text else None)

        preview = f"# {script.title}\n\n"
        for scene in script.scenes:
            preview += f"## 씬 {scene.scene_id}: {scene.title}\n"
            preview += f"{scene.text}\n\n"

        return "✅ 스크립트 생성 완료", preview

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


def generate_tts(engine: str):
    """TTS 생성"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 먼저 스크립트를 생성해주세요", None

    try:
        audio_path = pipeline.step3_generate_tts(engine)
        total_duration = sum(s.duration for s in pipeline.project.audio_segments)

        return f"✅ TTS 생성 완료 ({total_duration:.1f}초)", audio_path

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


def generate_images(engine: str, style_prefix: str):
    """이미지 생성"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 먼저 스크립트를 생성해주세요", None

    try:
        image_paths = pipeline.step4_generate_images(
            engine=engine,
            style_prefix=style_prefix
        )

        # 이미지 갤러리용
        images = [Image.open(p) for p in image_paths[:8]]

        return f"✅ 이미지 생성 완료 ({len(image_paths)}장, 엔진: {engine})", images

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


def generate_subtitles(use_whisper: bool):
    """자막 생성"""
    if not pipeline.project or not pipeline.project.audio_segments:
        return "❌ 먼저 TTS를 생성해주세요", None

    try:
        subtitle_path = pipeline.step5_generate_subtitles(use_whisper=use_whisper)

        with open(subtitle_path, "r", encoding="utf-8") as f:
            srt_content = f.read()

        method = "Whisper" if use_whisper else "대본 기반"
        return f"✅ 자막 생성 완료 ({method})", srt_content[:2000]

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


def render_video(use_ken_burns: bool, use_bgm: bool):
    """영상 렌더링"""
    if not pipeline.project or not pipeline.project.cut_paths:
        return "❌ 먼저 이미지를 생성해주세요", None

    try:
        video_path = pipeline.step6_render_video(
            use_ken_burns=use_ken_burns,
            use_bgm=use_bgm
        )

        effects = []
        if use_ken_burns:
            effects.append("Ken Burns")
        if use_bgm:
            effects.append("BGM")
        effect_str = " + ".join(effects) if effects else "기본"

        return f"✅ 영상 렌더링 완료 ({effect_str})", video_path

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


def finalize_video():
    """최종 영상 (자막 번인)"""
    if not pipeline.project or not pipeline.project.video_path:
        return "❌ 먼저 영상을 렌더링해주세요", None

    try:
        final_path = pipeline.step7_burn_subtitles()
        return "✅ 최종 영상 생성 완료!", final_path

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


# Gradio 인터페이스
with gr.Blocks(title="인기 영상 분석 콘텐츠 생성기", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🎬 인기 영상 분석 콘텐츠 생성기")
    gr.Markdown("YouTube 트렌드 분석 → 스크립트 리라이트 → 이미지 생성 → 영상 제작")

    with gr.Row():
        # 왼쪽: 컨트롤 패널
        with gr.Column(scale=1):
            gr.Markdown("## 📋 설정")

            topic_input = gr.Textbox(
                label="주제 / 키워드",
                placeholder="예: 조선시대 이야기",
                lines=2
            )

            duration_input = gr.Radio(
                choices=[5, 10, 15, 20],
                value=10,
                label="영상 길이 (분)"
            )

            create_btn = gr.Button("1️⃣ 프로젝트 생성", variant="primary")

            gr.Markdown("---")
            gr.Markdown("### 🔍 트렌드 분석 (선택)")

            trend_btn = gr.Button("트렌드 분석")

            video_id_input = gr.Textbox(
                label="참조 영상 ID",
                placeholder="예: dQw4w9WgXcQ",
                lines=1
            )

            extract_btn = gr.Button("자막 추출")

            gr.Markdown("---")
            gr.Markdown("### 📝 스크립트 & TTS")

            script_btn = gr.Button("2️⃣ 스크립트 생성")

            tts_engine = gr.Radio(
                choices=["wavenet", "elevenlabs", "openai"],
                value="wavenet",
                label="TTS 엔진"
            )
            tts_btn = gr.Button("3️⃣ TTS 생성")

            gr.Markdown("---")
            gr.Markdown("### 🎨 이미지 생성")

            image_engine = gr.Radio(
                choices=["fal", "dalle", "imagen"],
                value="fal",
                label="이미지 엔진",
                info="fal.ai(빠름), DALL-E(고품질), Imagen"
            )

            style_prefix = gr.Textbox(
                label="스타일 프리픽스 (선택)",
                placeholder="예: Cinematic, warm lighting, Korean traditional style",
                lines=2
            )

            image_btn = gr.Button("4️⃣ 이미지 생성")

            gr.Markdown("---")
            gr.Markdown("### 📄 자막 & 영상")

            use_whisper = gr.Checkbox(
                label="Whisper 타임스탬프",
                value=False
            )
            subtitle_btn = gr.Button("5️⃣ 자막 생성")

            with gr.Row():
                use_ken_burns = gr.Checkbox(label="Ken Burns", value=True)
                use_bgm = gr.Checkbox(label="BGM", value=False)

            render_btn = gr.Button("6️⃣ 영상 렌더링")

            final_btn = gr.Button("7️⃣ 최종 영상", variant="primary")

        # 오른쪽: 미리보기 패널
        with gr.Column(scale=2):
            gr.Markdown("## 👁️ 미리보기")

            status_output = gr.Textbox(
                label="상태",
                lines=4,
                interactive=False
            )

            with gr.Tabs():
                with gr.Tab("🔥 트렌드"):
                    trend_preview = gr.Markdown()

                with gr.Tab("📜 원본 자막"):
                    transcript_preview = gr.Textbox(
                        label="추출된 자막",
                        lines=10,
                        interactive=False
                    )

                with gr.Tab("📝 스크립트"):
                    script_preview = gr.Markdown()

                with gr.Tab("🔊 오디오"):
                    audio_preview = gr.Audio(label="TTS 미리듣기")

                with gr.Tab("🎨 이미지"):
                    images_preview = gr.Gallery(
                        label="생성된 이미지",
                        columns=4,
                        height="auto"
                    )

                with gr.Tab("📄 자막"):
                    subtitle_preview = gr.Textbox(
                        label="SRT",
                        lines=15,
                        interactive=False
                    )

                with gr.Tab("🎥 영상"):
                    video_preview = gr.Video(label="렌더링된 영상")

                with gr.Tab("✅ 최종"):
                    final_preview = gr.Video(label="최종 영상")

    # 이벤트 연결
    create_btn.click(
        create_project,
        inputs=[topic_input, duration_input],
        outputs=[status_output, script_preview, audio_preview]
    )

    trend_btn.click(
        analyze_trend,
        inputs=[topic_input],
        outputs=[status_output, trend_preview]
    )

    extract_btn.click(
        extract_transcript,
        inputs=[video_id_input],
        outputs=[status_output, transcript_preview]
    )

    script_btn.click(
        generate_script,
        inputs=[transcript_preview],
        outputs=[status_output, script_preview]
    )

    tts_btn.click(
        generate_tts,
        inputs=[tts_engine],
        outputs=[status_output, audio_preview]
    )

    image_btn.click(
        generate_images,
        inputs=[image_engine, style_prefix],
        outputs=[status_output, images_preview]
    )

    subtitle_btn.click(
        generate_subtitles,
        inputs=[use_whisper],
        outputs=[status_output, subtitle_preview]
    )

    render_btn.click(
        render_video,
        inputs=[use_ken_burns, use_bgm],
        outputs=[status_output, video_preview]
    )

    final_btn.click(
        finalize_video,
        outputs=[status_output, final_preview]
    )


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)
