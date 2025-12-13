from dataclasses import dataclass, field
from typing import List, Dict, Any

# 1) 주제 스코어링 결과
@dataclass
class TopicScore:
    main_keyword: str
    related_keywords: List[str]
    search_volume_score: float   # 0~1
    competition_score: float     # 0~1 (높을수록 경쟁 치열)
    senior_fit_score: float      # 0~1
    final_score: float           # 0~1


# 2) 제목 + 썸네일 엔진 결과
@dataclass
class TitleThumbnailResult:
    final_title: str
    candidates: List[str]
    thumbnail_text: str
    thumbnail_image_prompt: str
    main_keyword: str
    sub_keywords: List[str]
    topic_score: TopicScore


# 3) 컨텐츠 프로필 (시니어 모드용)
@dataclass
class ContentProfile:
    mode_id: str                 # "senior_kr_v1"
    category: str                # "health", "money", "emotion", "memory", "general" ...
    template_id: str             # "senior_info_4points", "senior_story_reminiscence" ...
    duration_sec: int            # 전체 영상 길이
    language: str                # "ko-KR"
    voice_tone: str              # "warm_slow"
    speech_speed: float          # 0.9~1.0
    # 시니어 모드 전용: 하이라이트 감성 자막 설정
    highlight_subtitles: bool = True    # 감성 자막 on/off
    subtitle_font_size: int = 72        # 기본 폰트 크기 (60~90)
    subtitle_position: str = "center"   # "center" or "top"
    extra: Dict[str, Any] = field(default_factory=dict)


# 4) 캐릭터 프로파일 (이미지 일관성을 위한 주인공 정보)
@dataclass
class CharacterProfile:
    name: str = ""                    # 주인공 이름/호칭 (예: 순자 할머니)
    age: str = ""                     # 나이대 (예: 60대 후반)
    gender: str = ""                  # 성별 (예: 여성)
    appearance: str = ""              # 외모 특징 (예: 흰 머리, 단정한 파마)
    clothing: str = ""                # 복장 (예: 베이지색 니트)
    distinctive_features: str = ""    # 특징적 요소 (예: 돋보기 안경)

    def to_prompt_string(self) -> str:
        """이미지 프롬프트용 캐릭터 설명 문자열 생성"""
        parts = []
        if self.age:
            parts.append(self.age)
        if self.gender:
            parts.append(self.gender)
        if self.appearance:
            parts.append(self.appearance)
        if self.clothing:
            parts.append(self.clothing)
        if self.distinctive_features:
            parts.append(self.distinctive_features)
        return ", ".join(parts) if parts else "인물"


# 5) ScriptEngine이 만들어낼 scene 단위 구조 예시
@dataclass
class Scene:
    scene_id: str                # "hook", "point1", "summary" 등
    title: str                   # 해당 장면의 내부 소제목
    narration: str               # TTS용 멘트
    image_prompt: str            # Gemini용 프롬프트
    duration_sec: int            # 이 장면 유지 시간
    broll_query: str = ""        # 스톡 비디오 검색 키워드 (Pexels/Pixabay)
    use_video: bool = False      # True면 이미지 대신 비디오 클립 사용
    highlight_keywords: List[str] = field(default_factory=list)  # 감성 자막용 키워드

    # ★ Shot Planner 메타데이터 (v0.1)
    shot_type: str = "medium"           # close_up, medium, wide, over_shoulder, establishing
    camera_motion: str = "slow_zoom_in" # static, slow_pan_left/right, slow_zoom_in/out, parallax_subtle
    emotion_tag: str = "warm"           # warm, serious, excited, sad, calm
    model_hint: str = "auto"            # auto, imagen3, dalle3, gpt_image (자동 선택 또는 지정)

    @property
    def safe_filename_id(self) -> str:
        """파일명에 안전하게 사용할 수 있는 scene_id 반환"""
        import re
        # scene_id가 너무 길거나 특수문자가 포함된 경우 정리
        sid = self.scene_id or "unknown"
        # 20자 초과 시 잘라내기 (JSON 파싱 오류로 인한 긴 문자열 방지)
        if len(sid) > 20:
            sid = "unknown"
        # 파일명에 안전한 문자만 허용 (영문, 숫자, 언더스코어, 하이픈)
        sid = re.sub(r'[^a-zA-Z0-9_\-]', '', sid)
        return sid if sid else "unknown"


@dataclass
class ScriptResult:
    profile: ContentProfile
    final_title: str
    scenes: List[Scene]
    character_profile: CharacterProfile = field(default_factory=CharacterProfile)  # 주인공 프로파일
