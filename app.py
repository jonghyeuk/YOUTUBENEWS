import gradio as gr
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from main import run_pipeline
from engines.youtube_trend_engine import get_youtube_trend_engine

# .env 파일 로드
load_dotenv()


# UI 테마 및 스타일
CUSTOM_CSS = """
.main-container {
    max-width: 1200px;
    margin: 0 auto;
}
.header-text {
    text-align: center;
    margin-bottom: 2rem;
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
.trend-card {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 1rem;
    margin: 0.5rem 0;
}
"""


def check_api_keys():
    """API 키 설정 상태 확인"""
    required_keys = {
        "Anthropic (Claude)": os.getenv("ANTHROPIC_API_KEY"),
        "OpenAI (TTS)": os.getenv("OPENAI_API_KEY"),
    }
    optional_keys = {
        "Pexels (B-roll 비디오)": os.getenv("PEXELS_API_KEY"),
        "Gemini (이미지)": os.getenv("GEMINI_API_KEY"),
        "네이버 CLOVA Voice": os.getenv("NAVER_CLIENT_ID") and os.getenv("NAVER_CLIENT_SECRET"),
        "YouTube Data API (전광판)": os.getenv("YOUTUBE_API_KEY")
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

    status.append("\n📌 선택적 API 키:")
    for name, key in optional_keys.items():
        if key:
            status.append(f"  ✅ {name}: 설정됨")
        else:
            status.append(f"  ⚪ {name}: 미설정 (기능 제한)")

    return "\n".join(status), all_required_set


def get_available_tts_voices():
    """
    ★ 나레이션 음성 목록 반환 (Gemini 여성 음성!)
    - 나레이션은 처음부터 끝까지 1명으로 고정
    - 대사([DIALOGUE])만 캐릭터에 맞는 다른 음성 사용
    - GEMINI_API_KEY 사용 (Imagen과 동일)
    """
    voices = []

    # ★ 나레이션 음성 = Gemini 여성만 (GEMINI_API_KEY 사용)
    if os.getenv("GEMINI_API_KEY"):
        voices.extend([
            ("🎙️ [기본] Kore - 부드럽고 차분한 여성 (야담/드라마 추천)", "gemini_kore"),
            ("🎙️ Aoede - 밝고 활기찬 여성 (동화/교육 추천)", "gemini_aoede"),
        ])

    # Gemini 없으면 자동
    if not voices:
        voices.append(("🤖 자동 (GEMINI_API_KEY 미설정)", "auto"))

    return voices


def get_available_image_engines():
    """API 키 설정에 따라 사용 가능한 이미지 엔진 목록 반환"""
    engines = [("🤖 자동 (프롬프트에 맞는 엔진 자동 선택)", "auto")]

    if os.getenv("OPENAI_API_KEY"):
        engines.extend([
            ("🖼️ DALL-E 3 - 최고 품질 ($0.04/장)", "dalle3"),
            ("⚡ DALL-E 2 - 빠르고 저렴 ($0.02/장)", "dalle2"),
        ])

    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_CLOUD_PROJECT"):
        engines.extend([
            ("🚀 Imagen 4.0 Fast - 빠른 생성 ($0.02/장)", "gemini_flash"),
            ("💎 Imagen 4.0 - 표준 품질 ($0.04/장)", "gemini_pro"),
            ("✨ Imagen 4.0 Ultra - 최고 품질 ($0.06/장)", "gemini_ultra"),
        ])

    engines.append(("📋 Placeholder - 무료 (테스트용)", "placeholder"))
    return engines


def generate_video(keyword: str, mode_id: str, duration_minutes: int, outline_pattern: str,
                   video_ratio: int, image_engine: str, voice: str, subtitle_mode: str,
                   subtitle_size: str, parallax_enabled: bool, progress=gr.Progress()):
    """영상 생성 메인 함수"""
    if not keyword or not keyword.strip():
        return None, None, "❌ 주제어를 입력해주세요."

    _, all_keys_set = check_api_keys()
    if not all_keys_set:
        return None, None, "❌ API 키가 설정되지 않았습니다. README를 참고하여 .env 파일을 설정해주세요."

    try:
        progress(0, desc="시작 중...")

        os.environ["BROLL_VIDEO_RATIO"] = str(video_ratio)
        os.environ["IMAGE_ENGINE"] = image_engine
        os.environ["TTS_VOICE"] = voice
        os.environ["SUBTITLE_MODE"] = subtitle_mode
        os.environ["SUBTITLE_SIZE"] = subtitle_size
        os.environ["PARALLAX_ENABLED"] = "true" if parallax_enabled else "false"
        os.environ["OUTLINE_PATTERN"] = outline_pattern

        if duration_minutes < 1:
            os.environ["VIDEO_RESOLUTION"] = "1080x1920"
            video_type = "YouTube Shorts (9:16 세로)"
        else:
            os.environ["VIDEO_RESOLUTION"] = "1920x1080"
            video_type = "일반 영상 (16:9 가로)"

        if mode_id == "auto" or mode_id.startswith("separator"):
            from engines.profile_engine import ContentProfileEngine
            profile_engine = ContentProfileEngine()
            mode_id, mode_reason = profile_engine.detect_mode_from_keyword(keyword.strip())
            progress(0.05, desc=f"장르 자동 판별: {mode_reason}")

        progress(0.1, desc="제목 및 컨셉 생성 중...")

        result = run_pipeline(
            keyword=keyword.strip(),
            duration_minutes=duration_minutes,
            mode_id=mode_id
        )

        # ★ 파이프라인 실패 시 처리 (TTS 실패, API 할당량 초과 등)
        if result is None:
            error_msg = "❌ 영상 생성 실패\n\n**가능한 원인:**\n- API 할당량 초과 (RPM/RPD)\n- TTS 생성 오류\n- 네트워크 연결 문제\n\n내일 다시 시도하거나 API 키를 확인해주세요."
            return None, None, error_msg

        progress(1.0, desc="완료!")

        video_path = result.get('video_path')
        thumbnail_path = result.get('thumbnail_path')
        export_dir = result.get('export_dir')
        profile = result.get('profile')
        title_block = result.get('title_block')
        script = result.get('script')

        mode_names = {
            "yadam_kr_v1": "📜 야담형 (전통 이야기)"
        }

        resolution = os.getenv("VIDEO_RESOLUTION", "1920x1080")
        info_text = f"""
## 🎉 영상 생성 완료!

**📌 최종 제목**: {title_block.final_title}

**📊 프로젝트 정보**:
- 모드: {mode_names.get(mode_id, mode_id)}
- 카테고리: {profile.category}
- 영상 길이: {profile.duration_sec}초 ({duration_minutes}분)
- Scene 수: {len(script.scenes)}개

**📺 영상 형식**: {video_type} ({resolution})

**📂 출력 디렉토리**: `{export_dir}`
"""
        video_output = video_path if os.path.exists(video_path) else None
        thumbnail_output = thumbnail_path if os.path.exists(thumbnail_path) else None

        return video_output, thumbnail_output, info_text

    except Exception as e:
        error_msg = f"❌ 오류 발생: {str(e)}\n\n자세한 내용은 콘솔 로그를 확인해주세요."
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None, None, error_msg


# ========== 전광판 샘플 데이터 ==========
# 1. 뜨는 주제  2. 썸네일 패턴  3. 후킹 패턴  4. 영상 구조(플로우)
SAMPLE_TREND_DATA = {
    "radio_drama": [
        {
            "rank": 1, "title": "그날 밤, 아내의 전화가 왔다", "score": 92, "views": "127만", "length": "12분",
            "hook": "남편은 그 번호를 알고 있었다",
            "thumbnail": "어두운 배경 + 전화기 클로즈업 + 빨간 텍스트",
            "flow": "Hook(의문) → 회상 → 갈등 심화 → 반전 → 결말"
        },
        {
            "rank": 2, "title": "30년 만에 찾아온 첫사랑", "score": 89, "views": "98만", "length": "15분",
            "hook": "그녀는 아직도 그 카페에 있었다",
            "thumbnail": "옛날 사진 + 카페 배경 + 따뜻한 톤",
            "flow": "Hook(재회) → 과거 회상 → 현재 상황 → 감정 고조 → 여운"
        },
        {
            "rank": 3, "title": "며느리가 남긴 편지", "score": 87, "views": "85만", "length": "10분",
            "hook": "시어머니는 그제야 알았다",
            "thumbnail": "손편지 클로즈업 + 눈물 이미지 + 감성 폰트",
            "flow": "Hook(편지 발견) → 갈등 회상 → 진실 공개 → 화해 → 감동"
        },
        {
            "rank": 4, "title": "아버지의 마지막 선물", "score": 85, "views": "76만", "length": "8분",
            "hook": "유품 속에서 나온 오래된 사진",
            "thumbnail": "낡은 상자 + 사진 + 따뜻한 조명",
            "flow": "Hook(유품 정리) → 아버지 회상 → 선물의 의미 → 깨달음"
        },
        {
            "rank": 5, "title": "새벽 3시, 누군가 문을 두드렸다", "score": 83, "views": "71만", "length": "12분",
            "hook": "현관문 너머 익숙한 목소리",
            "thumbnail": "어두운 현관문 + 그림자 + 긴장감 텍스트",
            "flow": "Hook(공포) → 긴장 고조 → 정체 암시 → 반전 → 감동/충격"
        },
        {
            "rank": 6, "title": "엄마의 비밀 레시피", "score": 81, "views": "65만", "length": "10분",
            "hook": "40년 만에 열어본 낡은 수첩",
            "thumbnail": "낡은 레시피북 + 음식 이미지 + 따뜻한 톤",
            "flow": "Hook(수첩 발견) → 엄마 회상 → 레시피 속 사연 → 감동"
        },
        {
            "rank": 7, "title": "동창회에서 만난 그 사람", "score": 79, "views": "58만", "length": "15분",
            "hook": "그는 나를 기억하지 못했다",
            "thumbnail": "동창회 장면 + 두 사람 실루엣 + 물음표",
            "flow": "Hook(재회) → 과거 관계 → 기억 차이 → 진실 → 결말"
        },
        {
            "rank": 8, "title": "버스에서 들은 통화", "score": 77, "views": "52만", "length": "8분",
            "hook": "옆자리 여자가 우는 이유",
            "thumbnail": "버스 창문 + 눈물 흐르는 여자 + 비 오는 날",
            "flow": "Hook(목격) → 통화 내용 → 사연 추측 → 진실 → 여운"
        },
        {
            "rank": 9, "title": "할머니의 금반지", "score": 75, "views": "48만", "length": "12분",
            "hook": "손녀에게만 물려준 진짜 이유",
            "thumbnail": "금반지 클로즈업 + 할머니 손 + 따뜻한 조명",
            "flow": "Hook(유산) → 가족 갈등 → 할머니 사연 → 반지의 비밀 → 화해"
        },
        {
            "rank": 10, "title": "남편의 일기장을 발견했다", "score": 73, "views": "45만", "length": "10분",
            "hook": "마지막 페이지에 적힌 이름",
            "thumbnail": "일기장 + 충격받은 표정 + 빨간 밑줄",
            "flow": "Hook(발견) → 의심 → 일기 내용 → 반전 → 감동/충격"
        },
    ],
    "history": [
        {
            "rank": 1, "title": "임진왜란, 이순신이 숨긴 비밀 작전", "score": 95, "views": "156만", "length": "20분",
            "hook": "역사책에 없는 12척의 진실",
            "thumbnail": "이순신 초상 + 거북선 + 12척 강조 텍스트",
            "flow": "Hook(의문 제기) → 배경 설명 → 숨겨진 사실 → 분석 → 결론"
        },
        {
            "rank": 2, "title": "박정희 피살 그날 밤의 40분", "score": 91, "views": "132만", "length": "25분",
            "hook": "경호실장은 왜 총을 쐈나",
            "thumbnail": "10.26 현장 + 시계(40분) + 긴장감 연출",
            "flow": "Hook(그날 밤) → 인물 관계 → 40분 타임라인 → 분석 → 미스터리"
        },
        {
            "rank": 3, "title": "명성황후 시해, 일본이 숨긴 문서", "score": 88, "views": "98만", "length": "18분",
            "hook": "130년 만에 공개된 기밀",
            "thumbnail": "명성황후 사진 + 기밀 도장 + 일본 문서",
            "flow": "Hook(기밀 공개) → 사건 재구성 → 새로운 증거 → 분석 → 결론"
        },
        {
            "rank": 4, "title": "6.25 전쟁, 인천상륙작전의 도박", "score": 86, "views": "87만", "length": "22분",
            "hook": "맥아더가 5000:1 확률을 택한 이유",
            "thumbnail": "맥아더 + 인천 지도 + 5000:1 텍스트",
            "flow": "Hook(확률) → 전쟁 상황 → 작전 계획 → 실행 과정 → 결과/의미"
        },
        {
            "rank": 5, "title": "조선 최대 스캔들, 장희빈의 진실", "score": 84, "views": "76만", "length": "15분",
            "hook": "드라마가 말하지 않은 것",
            "thumbnail": "장희빈 이미지 + VS 드라마 vs 실제 + 물음표",
            "flow": "Hook(드라마 vs 실제) → 실제 기록 → 재해석 → 숨겨진 진실 → 결론"
        },
        {
            "rank": 6, "title": "세종대왕, 한글 창제의 숨은 목적", "score": 82, "views": "68만", "length": "18분",
            "hook": "신하들이 반대한 진짜 이유",
            "thumbnail": "세종대왕 + 훈민정음 + 반대하는 신하들",
            "flow": "Hook(반대 이유) → 시대 배경 → 정치적 맥락 → 숨은 목적 → 결론"
        },
        {
            "rank": 7, "title": "고종의 커피, 독살설의 진실", "score": 80, "views": "61만", "length": "15분",
            "hook": "덕수궁 그날의 검시 기록",
            "thumbnail": "고종 + 커피잔 + 독약 이미지",
            "flow": "Hook(독살설) → 당시 상황 → 증거 분석 → 검시 기록 → 결론"
        },
        {
            "rank": 8, "title": "광해군은 정말 폭군이었나", "score": 78, "views": "55만", "length": "20분",
            "hook": "역사가 숨긴 외교 천재의 면모",
            "thumbnail": "광해군 + 폭군? 천재? + 양면 이미지",
            "flow": "Hook(재평가) → 기존 평가 → 새로운 시각 → 업적 분석 → 결론"
        },
        {
            "rank": 9, "title": "삼국시대, 백제 멸망의 진짜 원인", "score": 76, "views": "49만", "length": "18분",
            "hook": "의자왕은 억울했다",
            "thumbnail": "의자왕 + 멸망 장면 + 억울함 표현",
            "flow": "Hook(억울함) → 통설 반박 → 새로운 증거 → 재해석 → 결론"
        },
        {
            "rank": 10, "title": "일제강점기, 독립군 밀정의 최후", "score": 74, "views": "45만", "length": "22분",
            "hook": "동료를 팔아넘긴 자의 말로",
            "thumbnail": "밀정 실루엣 + 독립군 + 배신 이미지",
            "flow": "Hook(밀정 정체) → 활동 내역 → 배신 과정 → 최후 → 교훈"
        },
    ],
    "updated_at": "2024-12-03 09:00"
}


# 캐시된 YouTube 데이터
_youtube_cache = {
    "radio_drama": {"videos": [], "updated_at": None, "source": "sample"},
    "history": {"videos": [], "updated_at": None, "source": "sample"}
}


def fetch_youtube_trends(category: str, force_refresh: bool = False) -> tuple:
    """
    YouTube API에서 트렌드 데이터 가져오기 (캐시 사용)

    Returns:
        (videos_list, updated_at, source, status_message)
    """
    global _youtube_cache

    engine = get_youtube_trend_engine()

    # API 키가 없으면 샘플 데이터 사용
    if not engine.is_available():
        return (
            SAMPLE_TREND_DATA.get(category, []),
            SAMPLE_TREND_DATA.get("updated_at", "샘플"),
            "sample",
            "⚠️ YOUTUBE_API_KEY 미설정 - 샘플 데이터 표시 중"
        )

    # 캐시 확인 (1시간 이내면 캐시 사용)
    cache = _youtube_cache.get(category, {})
    if not force_refresh and cache.get("videos") and cache.get("updated_at"):
        cache_time = datetime.strptime(cache["updated_at"], "%Y-%m-%d %H:%M")
        if (datetime.now() - cache_time).seconds < 3600:  # 1시간
            return (
                cache["videos"],
                cache["updated_at"],
                "youtube_api (캐시)",
                f"✅ YouTube API 데이터 (캐시: {cache['updated_at']})"
            )

    # YouTube API 호출
    try:
        result = engine.get_trend_data(category)

        if result["source"] == "youtube_api" and result["videos"]:
            # 캐시 업데이트
            _youtube_cache[category] = {
                "videos": result["videos"],
                "updated_at": result["updated_at"],
                "source": "youtube_api"
            }
            return (
                result["videos"],
                result["updated_at"],
                "youtube_api",
                f"✅ YouTube API 실시간 데이터 ({result['updated_at']})"
            )
        else:
            # API 호출 실패 시 샘플 데이터
            return (
                SAMPLE_TREND_DATA.get(category, []),
                SAMPLE_TREND_DATA.get("updated_at", "샘플"),
                "sample",
                f"⚠️ API 응답 없음 - 샘플 데이터 표시 중"
            )

    except Exception as e:
        print(f"[YouTube API Error] {e}")
        return (
            SAMPLE_TREND_DATA.get(category, []),
            SAMPLE_TREND_DATA.get("updated_at", "샘플"),
            "sample",
            f"❌ API 오류 - 샘플 데이터 표시 중: {str(e)[:50]}"
        )


def get_trend_display(category: str, force_refresh: bool = False) -> tuple:
    """전광판 데이터를 마크다운 형식으로 변환 (1.주제 2.썸네일 3.후킹 4.플로우)"""
    videos, updated_at, source, status = fetch_youtube_trends(category, force_refresh)

    if not videos:
        return "데이터가 없습니다.", status

    lines = []
    for item in videos:
        rank = item.get("rank", 0)
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."

        title = item.get("title", "제목 없음")
        score = item.get("score", 0)
        views = item.get("views", "0")
        length = item.get("length", "0분")
        hook = item.get("hook", "")

        lines.append(f"**{medal} {title}**")
        lines.append(f"   📊 점수: {score}점 | 👁️ {views} | ⏱️ {length}")
        lines.append(f"   💡 후킹: \"{hook}\"")

        # 샘플 데이터에만 있는 필드
        if "thumbnail" in item:
            lines.append(f"   🖼️ 썸네일: {item['thumbnail']}")
        if "flow" in item:
            lines.append(f"   🎬 플로우: {item['flow']}")

        # YouTube API 데이터에만 있는 필드
        if "channel_title" in item:
            lines.append(f"   📺 채널: {item['channel_title']}")

        lines.append("")

    return "\n".join(lines), status


def refresh_trends():
    """전광판 데이터 새로고침"""
    radio_display, radio_status = get_trend_display("radio_drama", force_refresh=True)
    history_display, history_status = get_trend_display("history", force_refresh=True)

    combined_status = f"🎭 라디오극장: {radio_status}\n📜 역사/사건: {history_status}"

    return radio_display, history_display, combined_status


def select_topic(category: str, rank: int):
    """선택한 주제 정보 반환 (캐시된 데이터에서)"""
    # 먼저 캐시된 YouTube 데이터 확인
    cache = _youtube_cache.get(category, {})
    if cache.get("videos"):
        for item in cache["videos"]:
            if item.get("rank") == rank:
                return item.get("title", "")

    # 캐시가 없으면 샘플 데이터에서
    data = SAMPLE_TREND_DATA.get(category, [])
    for item in data:
        if item["rank"] == rank:
            return item["title"]
    return ""


# ========== Gradio UI 구성 ==========
with gr.Blocks(title="SeniorVideoFactory", css=CUSTOM_CSS) as demo:

    # 헤더
    gr.Markdown("""
    # 🎥 SeniorVideoFactory
    ### 시니어 타깃 유튜브 영상 자동 생성 시스템
    """, elem_classes="header-text")

    # ========== 탭 구조 ==========
    with gr.Tabs():

        # ========== 탭 1: 영상 제작 ==========
        with gr.TabItem("📺 영상 제작"):
            gr.Markdown("주제어 하나만 입력하면 시니어 맞춤형 영상이 자동으로 생성됩니다.")

            with gr.Accordion("⚙️ API 키 설정 상태", open=False):
                api_status = gr.Textbox(
                    label="API 키 상태",
                    value=check_api_keys()[0],
                    interactive=False,
                    lines=3
                )

            with gr.Row():
                with gr.Column(scale=2):
                    keyword_input = gr.Textbox(
                        label="📝 주제어",
                        placeholder="예: 고혈압 관리, 이순신 장군, 사내연애...",
                        lines=2,
                        info="모드에 맞는 주제를 입력하세요"
                    )

                with gr.Column(scale=1):
                    mode_input = gr.Dropdown(
                        label="🎬 콘텐츠 장르 선택",
                        choices=[
                            ("📜 야담형 (전통 이야기)", "yadam_kr_v1"),
                        ],
                        value="yadam_kr_v1"
                    )

                    duration_input = gr.Dropdown(
                        label="⏱️ 영상 길이",
                        choices=[
                            ("15초 (Shorts)", 0.25),
                            ("30초 (Shorts)", 0.5),
                            ("1분 (Shorts)", 1),
                            ("3분", 3),
                            ("5분", 5),
                            ("10분", 10),
                            ("15분", 15),
                            ("30분 (야담/긴 서사)", 30),
                            ("50분 (야담/풀버전)", 50)
                        ],
                        value=5
                    )

                    outline_pattern_input = gr.Dropdown(
                        label="📖 이야기 패턴 선택",
                        choices=[
                            ("🎭 정체공개형 - 평범한 주인공의 정체가 드러남", "reveal"),
                            ("📈 성장형 - 시련을 겪으며 성장", "growth"),
                            ("⚔️ 복수/통쾌형 - 권선징악 이야기", "revenge"),
                            ("🔄 반전형 - 예상치 못한 반전", "twist"),
                            ("🥊 대결형 - 선과 악의 정면 대결", "showdown"),
                            ("🎮 롤플레잉형 - 점점 강해지는 주인공", "levelup"),
                        ],
                        value="reveal"
                    )

            with gr.Accordion("⚙️ 고급 설정", open=False):
                available_voices = get_available_tts_voices()
                default_voice = available_voices[0][1] if available_voices else "auto"

                voice_input = gr.Dropdown(
                    label="🗣️ TTS 음성 선택",
                    choices=available_voices,
                    value=default_voice
                )

                subtitle_input = gr.Radio(
                    label="자막 모드",
                    choices=[
                        ("없음", "none"),
                        ("하이라이트 감성 자막 (권장)", "highlight"),
                        ("전체 자막", "full"),
                        ("전체 + 하이라이트", "full_highlight"),
                    ],
                    value="full_highlight"
                )

                subtitle_size_input = gr.Dropdown(
                    label="자막 크기",
                    choices=[
                        ("자동", "auto"),
                        ("작게 (48px)", "small"),
                        ("보통 (60px)", "medium"),
                        ("크게 (72px)", "large"),
                        ("매우 크게 (90px)", "xlarge"),
                    ],
                    value="medium"
                )

                video_ratio_input = gr.Slider(
                    minimum=0,
                    maximum=100,
                    value=0,
                    step=10,
                    label="B-roll 비디오 비율"
                )

                parallax_input = gr.Checkbox(
                    label="✨ Parallax 모션 효과",
                    value=True
                )

                available_engines = get_available_image_engines()
                default_engine = available_engines[0][1] if available_engines else "auto"

                image_engine_input = gr.Dropdown(
                    label="🎨 이미지 생성 엔진",
                    choices=available_engines,
                    value=default_engine
                )

            generate_btn = gr.Button("🎬 영상 생성하기", variant="primary", size="lg")

            gr.Markdown("---")
            gr.Markdown("## 📤 결과")

            with gr.Row():
                video_output = gr.Video(label="생성된 영상", interactive=False)
                thumbnail_output = gr.Image(label="썸네일", type="filepath")

            info_output = gr.Markdown(label="상세 정보")

            gr.Markdown("---")
            gr.Markdown("### 💡 예시 주제어")

            with gr.Row():
                example_btns = [
                    gr.Button("고혈압 관리", size="sm"),
                    gr.Button("무릎 통증 예방", size="sm"),
                    gr.Button("이순신 장군", size="sm"),
                    gr.Button("사내연애 비밀", size="sm"),
                    gr.Button("토끼와 무지개", size="sm"),
                ]

            generate_btn.click(
                fn=generate_video,
                inputs=[keyword_input, mode_input, duration_input, outline_pattern_input,
                        video_ratio_input, image_engine_input, voice_input, subtitle_input,
                        subtitle_size_input, parallax_input],
                outputs=[video_output, thumbnail_output, info_output]
            )

            for btn in example_btns:
                btn.click(fn=lambda text: text, inputs=[btn], outputs=[keyword_input])

        # ========== 탭 2: 전광판 ==========
        with gr.TabItem("🔥 전광판"):
            gr.Markdown("""
            ## 🔥 유튜브 떡상 예측 전광판

            **YouTube 트렌드 분석 기반 추천 주제**
            조회수가 높을 것으로 예측되는 주제들을 보여줍니다.
            """)

            with gr.Row():
                refresh_btn = gr.Button("🔄 데이터 새로고침", variant="secondary")
                trend_status = gr.Textbox(
                    label="",
                    value="⏳ 새로고침 버튼을 눌러 YouTube 데이터를 가져오세요",
                    interactive=False,
                    lines=2
                )

            with gr.Row():
                # 라디오극장 TOP 10
                with gr.Column():
                    gr.Markdown("### 🎭 라디오극장 TOP 10")
                    gr.Markdown("*감동, 가족, 첫사랑, 미스터리...*")

                    # ★ 시작 시 API 호출 안 함 - 새로고침 버튼 클릭 시에만
                    initial_radio = "🔄 **'새로고침' 버튼을 눌러 트렌드를 불러오세요**"
                    radio_display = gr.Markdown(value=initial_radio)

                    with gr.Row():
                        radio_rank_input = gr.Dropdown(
                            label="순위 선택",
                            choices=[(f"{i}위", i) for i in range(1, 11)],
                            value=1
                        )
                        radio_select_btn = gr.Button("📺 이 주제로 제작하기", variant="primary")

                # 역사/사건 TOP 10
                with gr.Column():
                    gr.Markdown("### 📜 역사/사건 TOP 10")
                    gr.Markdown("*실화, 역사, 인물, 전쟁, 스캔들...*")

                    # ★ 시작 시 API 호출 안 함 - 새로고침 버튼 클릭 시에만
                    initial_history = "🔄 **'새로고침' 버튼을 눌러 트렌드를 불러오세요**"
                    history_display = gr.Markdown(value=initial_history)

                    with gr.Row():
                        history_rank_input = gr.Dropdown(
                            label="순위 선택",
                            choices=[(f"{i}위", i) for i in range(1, 11)],
                            value=1
                        )
                        history_select_btn = gr.Button("📺 이 주제로 제작하기", variant="primary")

            gr.Markdown("---")

            gr.Markdown("""
            ### 📊 점수 산정 기준

            | 지표 | 설명 | 가중치 |
            |------|------|--------|
            | 조회수/일 | 하루 평균 조회수 | 30% |
            | 참여도 | (좋아요+댓글)/조회수 | 25% |
            | 영상 길이 | 최적 길이 가산점 | 20% |
            | 신선도 | 최근 영상 가산점 | 15% |
            | 후킹 점수 | 제목 클릭 유도력 | 10% |

            ---

            ### 📡 데이터 소스
            - **YouTube Data API v3** - 실시간 인기 영상 데이터
            - 검색 범위: 최근 30일 이내 업로드된 영상
            - 캐시: 1시간 (API 할당량 절약)

            ### 🔮 향후 업데이트 예정
            - Google Trends 연동 (트렌드 반영)
            - 댓글 감정 분석
            - AI 후킹 문구 자동 생성
            """)

            # 전광판에서 주제 선택 시 영상 제작 탭의 keyword_input에 전달
            def select_and_notify(category, rank):
                title = select_topic(category, rank)
                return title, f"✅ 선택됨: **{title}**\n\n👆 '영상 제작' 탭으로 이동하여 영상을 생성하세요."

            selected_topic_display = gr.Markdown("")

            radio_select_btn.click(
                fn=lambda rank: select_and_notify("radio_drama", rank),
                inputs=[radio_rank_input],
                outputs=[keyword_input, selected_topic_display]
            )

            history_select_btn.click(
                fn=lambda rank: select_and_notify("history", rank),
                inputs=[history_rank_input],
                outputs=[keyword_input, selected_topic_display]
            )

            # 새로고침 버튼 클릭 핸들러
            refresh_btn.click(
                fn=refresh_trends,
                inputs=[],
                outputs=[radio_display, history_display, trend_status]
            )

    # 푸터
    gr.Markdown("""
    ---
    <div style="text-align: center; color: #666; font-size: 0.9em;">
    Made with ❤️ by SeniorVideoFactory | Powered by Claude, OpenAI, Gemini, FFmpeg
    </div>
    """)


if __name__ == "__main__":
    print("=" * 60)
    print("SeniorVideoFactory UI Starting...")
    print("=" * 60)

    status, all_set = check_api_keys()
    print("\n[API Key Status]")
    print(status)

    if not all_set:
        print("\n⚠️  Warning: Some API keys are not set.")

    print("\n" + "=" * 60)
    print("Opening browser...")
    print("=" * 60 + "\n")

    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True
    )
