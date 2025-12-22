"""
Gradio UI - 단계별 영상 생성 인터페이스
FFmpeg 자동화 파이프라인 (Ken Burns + BGM 믹싱)
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
    spec = DURATION_SPECS[duration]

    info = f"""✅ 프로젝트 생성 완료

📁 ID: {project.project_id}
⏱️ 길이: {duration}분
🎬 씬 수: {spec['scenes']}개
🖼️ 컷 수: {spec['panels']}개 ({spec['rows']}x{spec['cols']} 그리드)
"""
    return info, None, None


def generate_script():
    """대본 생성"""
    if not pipeline.project:
        return "❌ 먼저 프로젝트를 생성해주세요", None

    try:
        script = pipeline.step1_generate_script()

        # 대본 미리보기 텍스트
        preview = f"# {script.title}\n\n"
        for scene in script.scenes:
            preview += f"## 씬 {scene.scene_id}: {scene.title}\n"
            preview += f"{scene.text}\n\n"

        return "✅ 대본 생성 완료", preview

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


def generate_tts(engine: str):
    """TTS 생성"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 먼저 대본을 생성해주세요", None

    try:
        audio_path = pipeline.step2_generate_tts(engine)
        total_duration = sum(s.duration for s in pipeline.project.audio_segments)

        return f"✅ TTS 생성 완료 ({total_duration:.1f}초) - 엔진: {engine}", audio_path

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


def generate_images(style: str):
    """이미지 생성"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 먼저 대본을 생성해주세요", None

    try:
        sheet_path = pipeline.step3_generate_images(style)
        return "✅ 스토리보드 이미지 생성 완료", sheet_path

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


def split_images():
    """이미지 분할"""
    if not pipeline.project or not pipeline.project.sheet_image_path:
        return "❌ 먼저 이미지를 생성해주세요", None

    try:
        cut_paths = pipeline.step4_split_images()
        pipeline.step5_assign_scenes()

        # 분할된 이미지들 미리보기
        images = [Image.open(p) for p in cut_paths[:8]]  # 최대 8개만 표시

        return f"✅ 이미지 분할 완료 ({len(cut_paths)}개 컷)", images

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


def generate_subtitles(use_whisper: bool):
    """자막 생성"""
    if not pipeline.project or not pipeline.project.audio_segments:
        return "❌ 먼저 TTS를 생성해주세요", None

    try:
        subtitle_path = pipeline.step6_generate_subtitles(use_whisper=use_whisper)

        # SRT 내용 미리보기
        with open(subtitle_path, "r", encoding="utf-8") as f:
            srt_content = f.read()

        method = "Whisper" if use_whisper else "대본 기반"
        return f"✅ 자막 생성 완료 ({method})", srt_content[:2000]

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


def render_video(use_ken_burns: bool, use_bgm: bool):
    """영상 렌더링"""
    if not pipeline.project or not pipeline.project.cut_paths:
        return "❌ 먼저 이미지를 분할해주세요", None

    try:
        video_path = pipeline.step7_render_video(
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
        final_path = pipeline.step8_burn_subtitles()
        return "✅ 최종 영상 생성 완료!", final_path

    except Exception as e:
        return f"❌ 오류: {str(e)}", None


# Gradio 인터페이스
with gr.Blocks(title="스토리 영상 생성기", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🎬 자동 스토리 영상 생성기")
    gr.Markdown("FFmpeg 기반 AI 영상 자동화 파이프라인 (Ken Burns Effect + BGM 믹싱)")

    with gr.Row():
        # 왼쪽: 컨트롤 패널
        with gr.Column(scale=1):
            gr.Markdown("## 📋 설정")

            topic_input = gr.Textbox(
                label="주제",
                placeholder="예: 토끼와 거북이",
                lines=2
            )

            duration_input = gr.Radio(
                choices=[5, 10, 15, 20],
                value=10,
                label="영상 길이 (분)"
            )

            create_btn = gr.Button("1️⃣ 프로젝트 생성", variant="primary")

            gr.Markdown("---")
            gr.Markdown("### 대본 & TTS")

            script_btn = gr.Button("2️⃣ 대본 생성")

            tts_engine = gr.Radio(
                choices=["wavenet", "elevenlabs", "openai"],
                value="wavenet",
                label="TTS 엔진",
                info="WaveNet(기본), ElevenLabs, OpenAI TTS"
            )
            tts_btn = gr.Button("3️⃣ TTS 생성")

            gr.Markdown("---")
            gr.Markdown("### 이미지")

            image_style = gr.Textbox(
                label="이미지 스타일",
                value="korean webtoon, colorful, expressive",
                lines=1
            )
            image_btn = gr.Button("4️⃣ 이미지 생성 (DALL·E)")

            split_btn = gr.Button("5️⃣ 이미지 분할")

            gr.Markdown("---")
            gr.Markdown("### 자막 & 영상")

            use_whisper = gr.Checkbox(
                label="Whisper 타임스탬프 사용",
                value=False,
                info="체크 해제 시 대본 기반 계산"
            )
            subtitle_btn = gr.Button("6️⃣ 자막 생성")

            with gr.Row():
                use_ken_burns = gr.Checkbox(
                    label="Ken Burns Effect",
                    value=True,
                    info="줌인/줌아웃 효과"
                )
                use_bgm = gr.Checkbox(
                    label="BGM 믹싱",
                    value=False,
                    info="배경음악 추가"
                )

            render_btn = gr.Button("7️⃣ 영상 렌더링")

            final_btn = gr.Button("8️⃣ 최종 영상 (자막 번인)", variant="primary")

        # 오른쪽: 미리보기 패널
        with gr.Column(scale=2):
            gr.Markdown("## 👁️ 미리보기")

            status_output = gr.Textbox(
                label="상태",
                lines=6,
                interactive=False
            )

            with gr.Tabs():
                with gr.Tab("📝 대본"):
                    script_preview = gr.Markdown()

                with gr.Tab("🔊 오디오"):
                    audio_preview = gr.Audio(label="TTS 미리듣기")

                with gr.Tab("🎨 스토리보드"):
                    sheet_preview = gr.Image(label="합본 이미지")

                with gr.Tab("✂️ 컷 분할"):
                    cuts_preview = gr.Gallery(
                        label="분할된 컷",
                        columns=4,
                        height="auto"
                    )

                with gr.Tab("📄 자막"):
                    subtitle_preview = gr.Textbox(
                        label="SRT 미리보기",
                        lines=15,
                        interactive=False
                    )

                with gr.Tab("🎥 영상"):
                    video_preview = gr.Video(label="렌더링된 영상")

                with gr.Tab("✅ 최종"):
                    final_preview = gr.Video(label="최종 영상 (자막 포함)")

    # 이벤트 연결
    create_btn.click(
        create_project,
        inputs=[topic_input, duration_input],
        outputs=[status_output, script_preview, audio_preview]
    )

    script_btn.click(
        generate_script,
        outputs=[status_output, script_preview]
    )

    tts_btn.click(
        generate_tts,
        inputs=[tts_engine],
        outputs=[status_output, audio_preview]
    )

    image_btn.click(
        generate_images,
        inputs=[image_style],
        outputs=[status_output, sheet_preview]
    )

    split_btn.click(
        split_images,
        outputs=[status_output, cuts_preview]
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
