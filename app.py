import gradio as gr
import os
import json
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


# UI 테마 및 스타일
CUSTOM_CSS = """
.main-container {
    max-width: 1400px;
    margin: 0 auto;
}
.header-text {
    text-align: center;
    margin-bottom: 1rem;
}
.preview-panel {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 1rem;
    background-color: #f9f9f9;
    max-height: 500px;
    overflow-y: auto;
}
.scene-card {
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 0.5rem;
    margin: 0.5rem 0;
    background-color: white;
}
.status-box {
    padding: 1rem;
    border-radius: 8px;
    margin: 1rem 0;
}
.confirm-btn {
    background-color: #28a745 !important;
    font-size: 1.2em !important;
}
.regenerate-btn {
    background-color: #ffc107 !important;
}
"""


# 전역 상태 저장 (세션별로 관리)
session_data = {
    "script": None,
    "profile": None,
    "image_paths": [],
    "audio_files": [],
    "thumbnail_path": None,
    "export_dir": None,
}


def check_api_keys():
    """API 키 설정 상태 확인"""
    required_keys = {
        "Anthropic (Claude)": os.getenv("ANTHROPIC_API_KEY"),
        "Google Gemini": os.getenv("GEMINI_API_KEY"),
    }

    status = []
    all_required_set = True

    status.append("📌 필수 API 키:")
    for name, key in required_keys.items():
        if key:
            status.append(f"  ✅ {name}: 설정됨")
        else:
            status.append(f"  ❌ {name}: 미설정")
            all_required_set = False

    return "\n".join(status), all_required_set


def step1_generate_script(
    news_mode: str,
    news_content: str,
    image_style: str,
    duration_minutes: float,
    progress=gr.Progress()
):
    """1단계: 대본 생성"""
    global session_data

    if not news_content or not news_content.strip():
        return "❌ 뉴스 내용을 입력해주세요.", ""

    _, all_keys_set = check_api_keys()
    if not all_keys_set:
        return "❌ API 키가 설정되지 않았습니다.", ""

    try:
        progress(0.1, desc="대본 생성 중...")

        from engines.script_engine import ScriptEngine
        from engines.profile_engine import ContentProfileEngine
        from models.types import TitleThumbnailResult, TopicScore

        # 출력 디렉토리 설정
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_name = f"news_{news_mode}_{timestamp}"
        export_dir = os.path.join("export", project_name)
        os.makedirs(export_dir, exist_ok=True)
        os.makedirs(os.path.join(export_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(export_dir, "audio"), exist_ok=True)

        # 환경변수 설정
        os.environ["NEWS_MODE"] = news_mode
        os.environ["IMAGE_STYLE"] = image_style

        # 프로필 생성
        profile_engine = ContentProfileEngine()
        profile = profile_engine.build_news_profile(
            news_mode=news_mode,
            duration_minutes=duration_minutes
        )

        # 더미 타이틀 블록
        title_block = TitleThumbnailResult(
            topic_score=TopicScore(0, 0, 0, 0),
            final_title="뉴스 영상",
            main_keyword="뉴스",
            sub_keywords=[],
            thumbnail_text="",
            thumbnail_image_prompt=""
        )

        progress(0.3, desc="AI가 대본을 분석하고 있습니다...")

        # 스크립트 생성
        script_engine = ScriptEngine()
        script = script_engine.generate_news_script(
            news_content=news_content.strip(),
            news_mode=news_mode,
            profile=profile,
            title_block=title_block
        )

        progress(1.0, desc="대본 생성 완료!")

        # 세션 데이터 저장
        session_data["script"] = script
        session_data["profile"] = profile
        session_data["export_dir"] = export_dir
        session_data["image_paths"] = []
        session_data["audio_files"] = []

        # 대본 미리보기 생성
        preview_lines = []
        for i, scene in enumerate(script.scenes):
            scene_id = getattr(scene, 'scene_id', f'scene_{i+1}')
            narration = getattr(scene, 'narration', '')
            image_prompt = getattr(scene, 'image_prompt', '')
            duration = getattr(scene, 'duration_sec', 0)

            preview_lines.append(f"""
### 🎬 Scene {i+1} ({scene_id})
**⏱️ 길이**: {duration}초

**🖼️ 이미지 프롬프트**:
> {image_prompt[:100]}{'...' if len(image_prompt) > 100 else ''}

**📝 나레이션**:
> {narration[:200]}{'...' if len(narration) > 200 else ''}

---
""")

        preview = "\n".join(preview_lines)

        status_msg = f"""
## ✅ 대본 생성 완료!

- **씬 개수**: {len(script.scenes)}개
- **예상 길이**: {int(duration_minutes)}분
- **출력 디렉토리**: `{export_dir}`

👉 **다음 단계**: "이미지 생성" 버튼을 눌러주세요.
"""

        return status_msg, preview

    except Exception as e:
        error_msg = f"❌ 대본 생성 오류: {str(e)}"
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return error_msg, ""


def step2_generate_images(progress=gr.Progress()):
    """2단계: 이미지 생성 (실시간 업데이트)"""
    global session_data

    if session_data["script"] is None:
        return "❌ 먼저 대본을 생성해주세요.", []

    try:
        from engines.image_engine import ImageEngine

        script = session_data["script"]
        profile = session_data["profile"]
        export_dir = session_data["export_dir"]
        image_style = os.getenv("IMAGE_STYLE", "realistic")

        image_engine = ImageEngine()
        image_paths = []
        gallery_data = []

        total_scenes = len(script.scenes)

        for idx, scene in enumerate(script.scenes):
            progress((idx + 1) / total_scenes, desc=f"이미지 생성 중... ({idx+1}/{total_scenes})")

            output_path = os.path.join(export_dir, "images", f"scene_{idx:03d}.png")

            try:
                image_engine._generate_image(
                    prompt=scene.image_prompt,
                    output_path=output_path,
                    image_style=image_style
                )
                image_paths.append(output_path)
                gallery_data.append((output_path, f"Scene {idx+1}"))
                print(f"[ImageEngine] Scene {idx}: Generated")

            except Exception as e:
                print(f"[ImageEngine] Scene {idx} Error: {e}")
                # 플레이스홀더 생성
                placeholder = image_engine._create_placeholder(
                    output_path=output_path,
                    scene_id=scene.scene_id,
                    text=f"Scene {idx + 1}"
                )
                image_paths.append(placeholder)
                gallery_data.append((placeholder, f"Scene {idx+1} (오류)"))

            # API 레이트 리밋 방지
            time.sleep(1)

        session_data["image_paths"] = image_paths

        status_msg = f"""
## ✅ 이미지 생성 완료!

- **생성된 이미지**: {len(image_paths)}개

👉 이미지를 검토하고, 필요하면 개별 이미지를 재생성하세요.
👉 **다음 단계**: "TTS 생성" 버튼을 눌러주세요.
"""

        return status_msg, gallery_data

    except Exception as e:
        error_msg = f"❌ 이미지 생성 오류: {str(e)}"
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return error_msg, []


def regenerate_single_image(scene_index: int, custom_prompt: str = None):
    """개별 이미지 재생성"""
    global session_data

    if session_data["script"] is None:
        return "❌ 먼저 대본을 생성해주세요.", []

    try:
        from engines.image_engine import ImageEngine

        script = session_data["script"]
        export_dir = session_data["export_dir"]
        image_style = os.getenv("IMAGE_STYLE", "realistic")

        if scene_index < 0 or scene_index >= len(script.scenes):
            return "❌ 잘못된 씬 번호입니다.", []

        scene = script.scenes[scene_index]
        prompt = custom_prompt if custom_prompt else scene.image_prompt

        image_engine = ImageEngine()
        output_path = os.path.join(export_dir, "images", f"scene_{scene_index:03d}.png")

        image_engine._generate_image(
            prompt=prompt,
            output_path=output_path,
            image_style=image_style
        )

        # 세션 데이터 업데이트
        if scene_index < len(session_data["image_paths"]):
            session_data["image_paths"][scene_index] = output_path

        # 갤러리 데이터 재구성
        gallery_data = [
            (path, f"Scene {i+1}")
            for i, path in enumerate(session_data["image_paths"])
            if os.path.exists(path)
        ]

        return f"✅ Scene {scene_index + 1} 이미지 재생성 완료!", gallery_data

    except Exception as e:
        error_msg = f"❌ 이미지 재생성 오류: {str(e)}"
        print(f"[ERROR] {e}")
        return error_msg, []


def step3_generate_audio(progress=gr.Progress()):
    """3단계: TTS 음성 생성"""
    global session_data

    if session_data["script"] is None:
        return "❌ 먼저 대본을 생성해주세요."

    try:
        from engines.tts_engine import TTSEngine

        script = session_data["script"]
        profile = session_data["profile"]
        export_dir = session_data["export_dir"]

        progress(0.1, desc="TTS 음성 생성 중...")

        tts_engine = TTSEngine()
        audio_files = tts_engine.generate_audio(
            script.scenes,
            profile,
            os.path.join(export_dir, "audio")
        )

        session_data["audio_files"] = audio_files

        progress(1.0, desc="TTS 생성 완료!")

        total_duration = sum(af.get("duration", 0) for af in audio_files)

        status_msg = f"""
## ✅ TTS 음성 생성 완료!

- **생성된 오디오**: {len(audio_files)}개
- **총 길이**: {total_duration:.1f}초 ({total_duration/60:.1f}분)

👉 **다음 단계**: "썸네일 생성" 버튼을 눌러주세요.
"""

        return status_msg

    except Exception as e:
        error_msg = f"❌ TTS 생성 오류: {str(e)}"
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return error_msg


def step4_generate_thumbnail(progress=gr.Progress()):
    """4단계: 썸네일 생성"""
    global session_data

    if session_data["script"] is None:
        return "❌ 먼저 대본을 생성해주세요.", None

    try:
        from engines.image_engine import ImageEngine

        script = session_data["script"]
        profile = session_data["profile"]
        export_dir = session_data["export_dir"]

        progress(0.5, desc="썸네일 생성 중...")

        image_engine = ImageEngine()
        thumbnail_path = os.path.join(export_dir, "thumbnail.png")

        if script.scenes:
            first_scene = script.scenes[0]
            image_engine.generate_thumbnail(
                prompt=first_scene.image_prompt,
                text="뉴스",
                output_path=thumbnail_path,
                category=profile.category
            )

        session_data["thumbnail_path"] = thumbnail_path

        progress(1.0, desc="썸네일 생성 완료!")

        status_msg = f"""
## ✅ 썸네일 생성 완료!

👉 모든 준비가 완료되었습니다!
👉 **최종 단계**: 모든 내용을 확인하고 "🎬 영상 생성 확정" 버튼을 눌러주세요.
"""

        return status_msg, thumbnail_path

    except Exception as e:
        error_msg = f"❌ 썸네일 생성 오류: {str(e)}"
        print(f"[ERROR] {e}")
        return error_msg, None


def step5_confirm_and_render(
    subtitle_mode: str,
    subtitle_size: str,
    parallax_enabled: bool,
    progress=gr.Progress()
):
    """5단계: 확정 후 자막 생성 및 영상 렌더링"""
    global session_data

    if session_data["script"] is None:
        return None, "❌ 먼저 모든 단계를 완료해주세요."

    if not session_data["audio_files"]:
        return None, "❌ TTS 음성이 생성되지 않았습니다."

    try:
        from engines.stt_subtitle_engine import STTSubtitleEngine
        from engines.video_engine import VideoRenderEngine

        script = session_data["script"]
        export_dir = session_data["export_dir"]
        image_paths = session_data["image_paths"]
        audio_files = session_data["audio_files"]

        # 환경변수 설정
        os.environ["SUBTITLE_MODE"] = subtitle_mode
        os.environ["SUBTITLE_SIZE"] = subtitle_size
        os.environ["PARALLAX_ENABLED"] = "true" if parallax_enabled else "false"

        resolution = os.getenv("VIDEO_RESOLUTION", "1920x1080")
        width, height = map(int, resolution.split("x"))

        # 1) 자막 생성 (STT 기반)
        subtitle_path = None
        if subtitle_mode != "none":
            progress(0.2, desc="자막 생성 중 (음성 분석)...")

            stt_engine = STTSubtitleEngine(font_size_preset=subtitle_size)
            subtitle_path = os.path.join(export_dir, "subtitles.ass")

            stt_engine.generate_subtitles_from_audio(
                audio_files=audio_files,
                output_path=subtitle_path,
                video_width=width,
                video_height=height,
                subtitle_mode=subtitle_mode
            )

        # 2) 영상 렌더링
        progress(0.5, desc="영상 렌더링 중...")

        video_engine = VideoRenderEngine()
        video_path = video_engine.render_video(
            image_paths,
            audio_files,
            script,
            os.path.join(export_dir, "video.mp4"),
            resolution=resolution,
            video_paths={},
            subtitle_path=subtitle_path,
            subtitle_engine=None,
            per_scene_subtitle=False,
            subtitle_mode=subtitle_mode
        )

        progress(1.0, desc="완료!")

        # 메타데이터 저장
        meta = {
            "news_mode": os.getenv("NEWS_MODE", "accident_news"),
            "image_style": os.getenv("IMAGE_STYLE", "realistic"),
            "scene_count": len(script.scenes),
            "subtitle_mode": subtitle_mode,
            "created_at": datetime.now().strftime("%Y%m%d_%H%M%S")
        }

        meta_path = os.path.join(export_dir, "meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        status_msg = f"""
## 🎉 영상 생성 완료!

**📂 출력 위치**: `{export_dir}`
**🎬 영상 파일**: `video.mp4`

모든 작업이 완료되었습니다!
"""

        return video_path, status_msg

    except Exception as e:
        error_msg = f"❌ 영상 렌더링 오류: {str(e)}"
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None, error_msg


# ========== Gradio UI 구성 ==========
with gr.Blocks(title="NewsVideoFactory", css=CUSTOM_CSS) as demo:

    # 헤더
    gr.Markdown("""
    # 📺 NewsVideoFactory
    ### 뉴스/사건사고 영상 자동 생성 시스템
    """, elem_classes="header-text")

    # API 키 상태
    with gr.Accordion("⚙️ API 키 설정 상태", open=False):
        api_status = gr.Textbox(
            label="API 키 상태",
            value=check_api_keys()[0],
            interactive=False,
            lines=3
        )

    # ========== 메인 레이아웃 (2컬럼) ==========
    with gr.Row():

        # ========== 왼쪽: 입력 및 제어 ==========
        with gr.Column(scale=1):
            gr.Markdown("## 📝 입력 및 제어")

            # 모드 선택
            news_mode_input = gr.Radio(
                label="🎬 콘텐츠 모드",
                choices=[
                    ("🚨 사건사고 뉴스", "accident_news"),
                    ("💬 카더라 뉴스", "rumor_news"),
                ],
                value="accident_news"
            )

            # 뉴스 내용 입력
            news_content_input = gr.Textbox(
                label="📰 뉴스 내용 붙여넣기",
                placeholder="여기에 뉴스 기사 내용을 붙여넣으세요...",
                lines=10,
                max_lines=15
            )

            with gr.Row():
                image_style_input = gr.Radio(
                    label="🎨 이미지 스타일",
                    choices=[
                        ("🎨 애니", "anime"),
                        ("📷 실사", "realistic"),
                    ],
                    value="realistic"
                )

                duration_input = gr.Dropdown(
                    label="⏱️ 영상 길이",
                    choices=[("1분", 1), ("3분", 3), ("5분", 5), ("10분", 10), ("15분", 15)],
                    value=5
                )

            # 단계별 버튼들
            gr.Markdown("### 📋 단계별 진행")

            with gr.Row():
                step1_btn = gr.Button("1️⃣ 대본 생성", variant="primary")
                step2_btn = gr.Button("2️⃣ 이미지 생성", variant="secondary")

            with gr.Row():
                step3_btn = gr.Button("3️⃣ TTS 생성", variant="secondary")
                step4_btn = gr.Button("4️⃣ 썸네일 생성", variant="secondary")

            # 이미지 재생성
            with gr.Accordion("🔄 이미지 재생성", open=False):
                regen_scene_idx = gr.Number(label="씬 번호 (1부터 시작)", value=1, precision=0)
                regen_prompt = gr.Textbox(label="커스텀 프롬프트 (선택)", placeholder="비워두면 원래 프롬프트 사용", lines=2)
                regen_btn = gr.Button("🔄 해당 씬 이미지 재생성", variant="secondary")

            # 고급 설정
            with gr.Accordion("⚙️ 자막 및 영상 설정", open=True):
                subtitle_input = gr.Radio(
                    label="자막 모드",
                    choices=[
                        ("없음", "none"),
                        ("전체 자막", "full"),
                        ("하이라이트", "highlight"),
                        ("전체 + 하이라이트", "full_highlight"),
                    ],
                    value="full"
                )

                subtitle_size_input = gr.Dropdown(
                    label="자막 크기",
                    choices=[
                        ("자동", "auto"),
                        ("작게 (60px)", "small"),
                        ("보통 (80px)", "medium"),
                        ("크게 (100px)", "large"),
                        ("아주 크게 (120px)", "xlarge"),
                    ],
                    value="medium"
                )

                parallax_input = gr.Checkbox(
                    label="✨ Parallax 모션 효과",
                    value=True
                )

            # 최종 확정 버튼
            gr.Markdown("---")
            confirm_btn = gr.Button(
                "🎬 영상 생성 확정",
                variant="primary",
                size="lg",
                elem_classes="confirm-btn"
            )

        # ========== 오른쪽: 실시간 미리보기 ==========
        with gr.Column(scale=1):
            gr.Markdown("## 🔍 실시간 미리보기")

            # 상태 표시
            status_output = gr.Markdown(
                value="👈 왼쪽에서 뉴스 내용을 입력하고 '대본 생성' 버튼을 눌러주세요.",
                elem_classes="status-box"
            )

            # 이미지 갤러리
            with gr.Accordion("🖼️ 생성된 이미지", open=True):
                image_gallery = gr.Gallery(
                    label="씬별 이미지 (클릭하여 확대)",
                    columns=3,
                    rows=2,
                    height="250px",
                    object_fit="contain"
                )

            # 썸네일
            with gr.Accordion("🎨 썸네일", open=True):
                thumbnail_output = gr.Image(
                    label="썸네일 미리보기",
                    type="filepath",
                    height=200
                )

            # 대본 미리보기
            with gr.Accordion("📝 대본 미리보기", open=True):
                script_preview = gr.Markdown(
                    value="대본이 생성되면 여기에 표시됩니다.",
                    elem_classes="preview-panel"
                )

    # ========== 하단: 최종 영상 ==========
    gr.Markdown("---")
    gr.Markdown("## 🎬 최종 영상")

    final_status = gr.Markdown("")

    video_output = gr.Video(
        label="생성된 영상",
        interactive=False,
        height=400
    )

    # ========== 이벤트 핸들러 ==========

    # 1단계: 대본 생성
    step1_btn.click(
        fn=step1_generate_script,
        inputs=[news_mode_input, news_content_input, image_style_input, duration_input],
        outputs=[status_output, script_preview]
    )

    # 2단계: 이미지 생성
    step2_btn.click(
        fn=step2_generate_images,
        inputs=[],
        outputs=[status_output, image_gallery]
    )

    # 이미지 재생성
    regen_btn.click(
        fn=lambda idx, prompt: regenerate_single_image(int(idx) - 1, prompt if prompt else None),
        inputs=[regen_scene_idx, regen_prompt],
        outputs=[status_output, image_gallery]
    )

    # 3단계: TTS 생성
    step3_btn.click(
        fn=step3_generate_audio,
        inputs=[],
        outputs=[status_output]
    )

    # 4단계: 썸네일 생성
    step4_btn.click(
        fn=step4_generate_thumbnail,
        inputs=[],
        outputs=[status_output, thumbnail_output]
    )

    # 5단계: 확정 및 영상 생성
    confirm_btn.click(
        fn=step5_confirm_and_render,
        inputs=[subtitle_input, subtitle_size_input, parallax_input],
        outputs=[video_output, final_status]
    )

    # 푸터
    gr.Markdown("""
    ---
    <div style="text-align: center; color: #666; font-size: 0.9em;">
    NewsVideoFactory | Powered by Claude, Google Gemini, Google TTS, Google STT, FFmpeg
    </div>
    """)


if __name__ == "__main__":
    print("=" * 60)
    print("NewsVideoFactory UI Starting...")
    print("=" * 60)

    status, all_set = check_api_keys()
    print("\n[API Key Status]")
    print(status)

    if not all_set:
        print("\n⚠️  Warning: Some API keys are not set.")

    print("\n" + "=" * 60)
    print("Opening browser at http://127.0.0.1:7860")
    print("=" * 60 + "\n")

    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True
    )
