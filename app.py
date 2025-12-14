import gradio as gr
import os
import json
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
    max-height: 600px;
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
.success-box {
    background-color: #d4edda;
    border-color: #c3e6cb;
    color: #155724;
}
.error-box {
    background-color: #f8d7da;
    border-color: #f5c6cb;
    color: #721c24;
}
"""


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


def generate_news_video(
    news_mode: str,
    news_content: str,
    image_style: str,
    duration_minutes: float,
    subtitle_mode: str,
    subtitle_size: str,
    parallax_enabled: bool,
    progress=gr.Progress()
):
    """뉴스 영상 생성 메인 함수"""

    if not news_content or not news_content.strip():
        return None, None, "❌ 뉴스 내용을 입력해주세요.", None, ""

    _, all_keys_set = check_api_keys()
    if not all_keys_set:
        return None, None, "❌ API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.", None, ""

    try:
        progress(0, desc="시작 중...")

        # 환경변수 설정
        os.environ["NEWS_MODE"] = news_mode
        os.environ["IMAGE_STYLE"] = image_style
        os.environ["IMAGE_ENGINE"] = "gemini"  # Gemini만 사용
        os.environ["TTS_ENGINE"] = "google"    # Google TTS만 사용
        os.environ["SUBTITLE_MODE"] = subtitle_mode
        os.environ["SUBTITLE_SIZE"] = subtitle_size
        os.environ["PARALLAX_ENABLED"] = "true" if parallax_enabled else "false"

        # 해상도 설정
        if duration_minutes < 1:
            os.environ["VIDEO_RESOLUTION"] = "1080x1920"
            video_type = "YouTube Shorts (9:16 세로)"
        else:
            os.environ["VIDEO_RESOLUTION"] = "1920x1080"
            video_type = "일반 영상 (16:9 가로)"

        progress(0.1, desc="뉴스 내용 분석 중...")

        # 파이프라인 실행
        from main import run_news_pipeline
        result = run_news_pipeline(
            news_content=news_content.strip(),
            news_mode=news_mode,
            image_style=image_style,
            duration_minutes=duration_minutes
        )

        if result is None:
            error_msg = "❌ 영상 생성 실패\n\n**가능한 원인:**\n- API 할당량 초과\n- TTS 생성 오류\n- 네트워크 연결 문제"
            return None, None, error_msg, None, ""

        progress(1.0, desc="완료!")

        video_path = result.get('video_path')
        thumbnail_path = result.get('thumbnail_path')
        export_dir = result.get('export_dir')
        script = result.get('script')
        image_paths = result.get('image_paths', [])

        # 검수용 씬 정보 생성
        scene_preview = generate_scene_preview(script.scenes if script else [], image_paths)

        mode_names = {
            "accident_news": "🚨 사건사고 뉴스",
            "rumor_news": "💬 카더라 뉴스"
        }

        style_names = {
            "anime": "🎨 애니 스타일",
            "realistic": "📷 실사 스타일"
        }

        resolution = os.getenv("VIDEO_RESOLUTION", "1920x1080")
        info_text = f"""
## 🎉 영상 생성 완료!

**📌 프로젝트 정보**:
- 모드: {mode_names.get(news_mode, news_mode)}
- 이미지 스타일: {style_names.get(image_style, image_style)}
- 영상 길이: {int(duration_minutes)}분
- Scene 수: {len(script.scenes) if script else 0}개

**📺 영상 형식**: {video_type} ({resolution})

**📂 출력 디렉토리**: `{export_dir}`
"""

        video_output = video_path if video_path and os.path.exists(video_path) else None
        thumbnail_output = thumbnail_path if thumbnail_path and os.path.exists(thumbnail_path) else None

        # 이미지 갤러리용 데이터
        gallery_images = [(img, f"Scene {i+1}") for i, img in enumerate(image_paths) if os.path.exists(img)]

        return video_output, thumbnail_output, info_text, gallery_images, scene_preview

    except Exception as e:
        error_msg = f"❌ 오류 발생: {str(e)}\n\n자세한 내용은 콘솔 로그를 확인해주세요."
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None, None, error_msg, None, ""


def generate_scene_preview(scenes, image_paths):
    """씬별 대본 미리보기 생성"""
    if not scenes:
        return "아직 생성된 씬이 없습니다."

    preview_lines = []
    for i, scene in enumerate(scenes):
        scene_id = getattr(scene, 'scene_id', f'scene_{i+1}')
        narration = getattr(scene, 'narration', '')
        duration = getattr(scene, 'duration_sec', 0)

        # 나레이션 미리보기 (최대 200자)
        narration_preview = narration[:200] + "..." if len(narration) > 200 else narration

        preview_lines.append(f"""
### 🎬 Scene {i+1} ({scene_id})
**⏱️ 길이**: {duration}초

**📝 나레이션**:
> {narration_preview}

---
""")

    return "\n".join(preview_lines)


def preview_script_only(
    news_mode: str,
    news_content: str,
    image_style: str,
    duration_minutes: float,
    progress=gr.Progress()
):
    """대본만 미리 생성 (이미지/영상 생성 없이)"""

    if not news_content or not news_content.strip():
        return "❌ 뉴스 내용을 입력해주세요.", None

    try:
        progress(0, desc="대본 생성 중...")

        from engines.script_engine import ScriptEngine
        from engines.profile_engine import ContentProfileEngine
        from models.types import TitleThumbnailResult, TopicScore

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

        progress(1.0, desc="완료!")

        # 미리보기 생성
        preview = generate_scene_preview(script.scenes, [])

        # 전체 대본 텍스트
        full_script = ""
        for i, scene in enumerate(script.scenes):
            full_script += f"\n\n=== Scene {i+1} ===\n"
            full_script += f"[이미지 프롬프트]: {getattr(scene, 'image_prompt', '')}\n\n"
            full_script += f"[나레이션]:\n{getattr(scene, 'narration', '')}\n"

        return preview, full_script

    except Exception as e:
        error_msg = f"❌ 대본 생성 오류: {str(e)}"
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return error_msg, None


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

        # ========== 왼쪽: 입력 영역 ==========
        with gr.Column(scale=1):
            gr.Markdown("## 📝 입력")

            # 모드 선택
            news_mode_input = gr.Radio(
                label="🎬 콘텐츠 모드",
                choices=[
                    ("🚨 사건사고 뉴스 - 실제 뉴스 기반 재구성", "accident_news"),
                    ("💬 카더라 뉴스 - 소문/풍문 기반 각색", "rumor_news"),
                ],
                value="accident_news"
            )

            # 뉴스 내용 입력
            news_content_input = gr.Textbox(
                label="📰 뉴스 내용 붙여넣기",
                placeholder="여기에 뉴스 기사 내용을 붙여넣으세요...\n\n예시:\n서울 강남구에서 발생한 교통사고로 인해...",
                lines=12,
                max_lines=20
            )

            with gr.Row():
                # 이미지 스타일
                image_style_input = gr.Radio(
                    label="🎨 이미지 스타일",
                    choices=[
                        ("🎨 애니 스타일", "anime"),
                        ("📷 실사 스타일", "realistic"),
                    ],
                    value="realistic"
                )

                # 영상 길이
                duration_input = gr.Dropdown(
                    label="⏱️ 영상 길이",
                    choices=[
                        ("1분", 1),
                        ("3분", 3),
                        ("5분", 5),
                        ("10분", 10),
                        ("15분", 15),
                    ],
                    value=5
                )

            # 고급 설정
            with gr.Accordion("⚙️ 고급 설정", open=False):
                subtitle_input = gr.Radio(
                    label="자막 모드",
                    choices=[
                        ("없음", "none"),
                        ("하이라이트 자막", "highlight"),
                        ("전체 자막", "full"),
                        ("전체 + 하이라이트", "full_highlight"),
                    ],
                    value="full_highlight"
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

            # 버튼들
            with gr.Row():
                preview_btn = gr.Button("👁️ 대본 미리보기", variant="secondary")
                generate_btn = gr.Button("🎬 영상 생성하기", variant="primary", size="lg")

        # ========== 오른쪽: 검수 영역 ==========
        with gr.Column(scale=1):
            gr.Markdown("## 🔍 검수 패널")

            # 씬별 이미지 갤러리
            with gr.Accordion("🖼️ 생성된 이미지", open=True):
                image_gallery = gr.Gallery(
                    label="씬별 이미지",
                    columns=3,
                    rows=2,
                    height="300px",
                    object_fit="contain"
                )

            # 씬별 대본 미리보기
            with gr.Accordion("📝 씬별 대본", open=True):
                scene_preview_output = gr.Markdown(
                    value="영상을 생성하면 여기에 씬별 대본이 표시됩니다.",
                    elem_classes="preview-panel"
                )

            # 전체 대본 (편집 가능)
            with gr.Accordion("📄 전체 대본 (편집용)", open=False):
                full_script_output = gr.Textbox(
                    label="전체 대본",
                    lines=15,
                    interactive=True,
                    placeholder="대본 미리보기 버튼을 누르면 여기에 전체 대본이 표시됩니다."
                )

    # ========== 하단: 결과 및 미리보기 ==========
    gr.Markdown("---")
    gr.Markdown("## 📤 결과")

    info_output = gr.Markdown(label="상태")

    with gr.Row():
        video_output = gr.Video(
            label="🎬 생성된 영상 (미리보기)",
            interactive=False,
            height=400
        )
        thumbnail_output = gr.Image(
            label="🖼️ 썸네일",
            type="filepath",
            height=400
        )

    # ========== 이벤트 핸들러 ==========

    # 대본 미리보기
    preview_btn.click(
        fn=preview_script_only,
        inputs=[news_mode_input, news_content_input, image_style_input, duration_input],
        outputs=[scene_preview_output, full_script_output]
    )

    # 영상 생성
    generate_btn.click(
        fn=generate_news_video,
        inputs=[
            news_mode_input, news_content_input, image_style_input, duration_input,
            subtitle_input, subtitle_size_input, parallax_input
        ],
        outputs=[video_output, thumbnail_output, info_output, image_gallery, scene_preview_output]
    )

    # 푸터
    gr.Markdown("""
    ---
    <div style="text-align: center; color: #666; font-size: 0.9em;">
    NewsVideoFactory | Powered by Claude, Google Gemini, Google TTS, FFmpeg
    </div>
    """)


# 변수명 수정 (subtitle_input → subtitle_mode_input)
# Gradio 블록 외부에서 참조하기 위해 이름 변경 필요
demo.launch_kwargs = {}

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
