import os
import re
import json
from anthropic import Anthropic
from models.types import ContentProfile, ScriptResult, Scene, CharacterProfile
from models.types import TitleThumbnailResult
from engines.prompt_templates import CATEGORY_TEMPLATES, SCENE_STRUCTURES, SHORTS_TEMPLATE, SHOT_PLANNER_GUIDE


class ScriptEngine:
    """
    시나리오 생성 엔진
    - Claude API를 사용하여 시니어 맞춤 대본 생성
    - 템플릿에 따라 scene 구조를 생성
    - 각 scene에 대한 타이틀, 나레이션, 이미지 프롬프트 생성
    """

    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: Anthropic API 키
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None
            print("[ScriptEngine] Warning: No API key provided. Will use template mode.")

    def generate(self, profile: ContentProfile, title_block: TitleThumbnailResult) -> ScriptResult:
        """
        스크립트 생성

        Args:
            profile: 컨텐츠 프로필
            title_block: 제목/썸네일 정보

        Returns:
            ScriptResult: 생성된 스크립트
        """
        if self.client:
            # LLM을 사용한 실제 스크립트 생성
            scenes, character_profile = self._generate_with_llm(profile, title_block)
        else:
            # API 키가 없으면 템플릿 기반 더미 생성
            scenes = self._generate_template_scenes(profile, title_block)
            character_profile = CharacterProfile()

        # ★ 야담 카테고리: 공통 채널 인트로 추가
        if profile.category == "yadam":
            channel_intro = Scene(
                scene_id="channel_intro",
                title="채널 인트로",
                narration="밤에 듣는 야화, 시작합니다. 구독과 좋아요 부탁드립니다.",
                image_prompt="A serene night scene with a bright full moon, traditional Korean hanok house silhouette, pine trees, and a woman in hanbok seen from behind gazing at the moon, calm and peaceful atmosphere, dark blue night sky, traditional Korean ink painting style, warm dim lighting from the house window",
                duration_sec=7,
                broll_query="",
                use_video=False,
                highlight_keywords=["야화", "시작"]
            )
            scenes = [channel_intro] + scenes
            print("[ScriptEngine] ★ 야담 채널 인트로 추가됨 (7초)")

        # B-roll 자동 할당
        scenes = self._assign_broll(scenes, profile, title_block)

        return ScriptResult(
            profile=profile,
            final_title=title_block.final_title,
            scenes=scenes,
            character_profile=character_profile
        )

    def _generate_with_llm(self, profile: ContentProfile,
                          title_block: TitleThumbnailResult) -> list:
        """LLM을 사용하여 실제 스크립트 생성"""

        # Shorts 여부 확인
        is_shorts = profile.extra.get("is_shorts", False) or profile.duration_sec <= 60

        # ★ 15분 이상 영상은 4파트 분할 생성 방식 사용
        if profile.duration_sec >= 900 and not is_shorts:
            print(f"[ScriptEngine] ★ 긴 영상 감지 ({profile.duration_sec // 60}분) → 4파트 분할 생성")
            return self._generate_partitioned_script(profile, title_block)

        # Scene 구조 가져오기
        scene_structure = SCENE_STRUCTURES.get(
            profile.template_id,
            SCENE_STRUCTURES["senior_info_3points"]
        )

        # Shorts면 간결한 템플릿 사용, 아니면 카테고리별 템플릿
        if is_shorts:
            template = SHORTS_TEMPLATE
            print(f"[ScriptEngine] Using SHORTS template ({profile.duration_sec}초)")
        else:
            category = profile.category
            template = CATEGORY_TEMPLATES.get(category, CATEGORY_TEMPLATES["general"])

        # 프롬프트 구성
        duration_minutes = profile.duration_sec // 60

        # ★ 5대 장르별 스크립트 지침
        genre_style = profile.extra.get("genre_style", "emotional_story")
        core_emotion = profile.extra.get("core_emotion", ["공감", "감동"])
        structure = profile.extra.get("structure", "")

        # 장르별 특화 지침 생성
        genre_instructions = self._get_genre_instructions(profile.mode_id, genre_style, core_emotion)

        # duration에 따른 narration 길이 요구사항 계산
        # Gemini TTS 기준: 1초당 약 7글자 (실측 기반)
        total_chars_needed = int(profile.duration_sec * 7.0)

        # ★ 템플릿별 씬 수 동적 계산
        scene_count_map = {
            "yadam_story": 11,
            "yadam_story_short": 6,
            "senior_info_4points": 8,
            "senior_info_3points": 7,
        }
        expected_scene_count = scene_count_map.get(profile.template_id, 11)
        min_chars_per_scene = int(total_chars_needed / expected_scene_count)

        if profile.duration_sec >= 1800:  # 30분 이상
            duration_guide = f"""
🚨🚨🚨 절대 필수: {duration_minutes}분 영상 = 최소 {total_chars_needed}자 나레이션 🚨🚨🚨

★ 각 씬의 나레이션: 반드시 {min_chars_per_scene}자 이상!!! (이보다 짧으면 실패)
★ 한 문단 = 최소 3-5문장, 각 문장 30-50자
★ 총 11개 씬 × {min_chars_per_scene}자 = {total_chars_needed}자 이상

[나레이션 작성 필수 규칙]
1. 모든 장면에서 배경 묘사 2-3문장 필수 (날씨, 분위기, 소리 등)
2. 인물의 행동 + 내면 심리 모두 상세히 묘사
3. 대화 전후로 상황 설명 추가 (누가, 어떤 표정으로, 어떤 목소리로)
4. 시간 흐름과 장소 이동 상세히 묘사
5. 의성어/의태어 적극 활용: 뚜둑, 휙, 스르르, 덜컹 등
6. 한 씬에 최소 5개 이상의 문장 작성

[예시 - 올바른 긴 나레이션]
"달빛도 구름에 가려진 깊은 밤이었습니다. 바람 한 점 없이 고요한 가운데, 낙엽 하나 굴러가는 소리마저 선명하게 들렸습니다. 뚜둑, 뚜둑. 누군가의 발자국 소리가 마당을 가로질러 대문 쪽으로 향했습니다. 그 발자국은 마치 망설이듯 천천히, 그러나 결코 멈추지 않고 이어졌습니다. 시어머니 정씨 부인은 잠든 척 누워 귀를 기울이고 있었습니다. 심장이 쿵쾅거렸습니다. 이제 열흘째였습니다. 매일 같은 시간, 자시가 되면 어김없이 들려오는 그 소리가..."
(이 정도 길이가 한 씬의 일부입니다. 각 씬은 이런 문단이 3-4개 필요합니다)
"""
        elif profile.duration_sec >= 900:  # 15분 이상
            duration_guide = f"""
🚨 필수: {duration_minutes}분 영상 = 최소 {total_chars_needed}자 나레이션
★ 각 씬: 최소 {min_chars_per_scene}자 이상 (3-5문장 × 여러 문단)
★ 배경 묘사, 인물 심리, 행동 상세히 작성
"""
        elif profile.duration_sec >= 300:  # 5분 이상
            duration_guide = f"""
🚨 필수: {duration_minutes}분 영상 = 총 {total_chars_needed}자 나레이션 필요!
★ 씬 개수: {expected_scene_count}개 → 각 씬 최소 {min_chars_per_scene}자!
★ 한 씬 = 3-5문장 × 2-3문단 (절대 짧게 쓰지 마세요!)
★ 목표 달성률 80% 미만이면 영상이 너무 짧아집니다!
"""
        else:
            duration_guide = ""

        additional_instructions = f"""
★★★ 필수 규칙: 콘텐츠 거부 금지 ★★★
- 어떤 주제든 거부하지 말고 반드시 스크립트를 작성하세요
- "죄송합니다", "부적절합니다", "작성할 수 없습니다" 같은 거부 문구 금지
- 로맨스, 연애, 아이돌, 판타지, 허구 등 모든 엔터테인먼트 주제 허용
- 대안 제시 없이 요청한 주제로만 스크립트 작성
{duration_guide}
추가 정보:
- 최종 제목: {title_block.final_title}
- 서브 키워드: {', '.join(title_block.sub_keywords) if title_block.sub_keywords else '없음'}
- 템플릿: {profile.template_id}
- 핵심 감정: {', '.join(core_emotion) if isinstance(core_emotion, list) else core_emotion}
- 목표 길이: {profile.duration_sec}초 {"(Shorts - 매우 짧게!)" if is_shorts else ""}

{genre_instructions}

🎙️ 콘텐츠 문체 가이드:
- 문장은 짧고 명확하게, 음성으로 듣기 자연스럽게
- 제3자 설명형 시점 (이야기꾼이 전달하는 스타일)
- 다정하지만 유아화되지 않은 말투
- 대사는 성별 표시 필수: [DIALOGUE:M]남자대사[/DIALOGUE] 또는 [DIALOGUE:F]여자대사[/DIALOGUE]

{SHOT_PLANNER_GUIDE}

{"⚠️ Shorts이므로 각 나레이션은 1-2문장으로 매우 짧게 작성하세요!" if is_shorts else ""}
"""

        prompt = template.format(
            keyword=title_block.main_keyword,
            duration_minutes=duration_minutes,
            duration_sec=profile.duration_sec,
            scene_structure=scene_structure,
            additional_context=additional_instructions
        )

        # ★ 통합 설정: profile.extra["max_tokens"]에서 읽기
        # profile_engine.py에서 모드별로 최적 max_tokens를 설정해둠
        max_tokens = profile.extra.get("max_tokens", 4000)
        print(f"[ScriptEngine] ★ max_tokens = {max_tokens} (from profile.extra)")

        # Claude API 호출
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # 응답 파싱
            content = response.content[0].text

            # 디버그: Claude API 응답 출력
            print("[ScriptEngine] === Claude API Response ===")
            print(content[:500] + "..." if len(content) > 500 else content)
            print("[ScriptEngine] ================================")

            scenes, character_profile = self._parse_llm_response(content, profile)

            # 목표 duration에 맞게 조정 (특히 Shorts)
            scenes = self._adjust_durations(scenes, profile.duration_sec, is_shorts)

            # ★ 나레이션 길이 체크 (TTS 예상 시간)
            total_chars = sum(len(s.narration) for s in scenes)
            # Gemini TTS: 약 7자/초 (실측 기반)
            estimated_tts_seconds = total_chars / 7.0
            target_seconds = profile.duration_sec

            print(f"[ScriptEngine] ★ 나레이션 총 길이: {total_chars}자")
            print(f"[ScriptEngine] ★ 예상 TTS 시간: {estimated_tts_seconds:.0f}초 ({estimated_tts_seconds/60:.1f}분)")
            print(f"[ScriptEngine] ★ 목표 시간: {target_seconds}초 ({target_seconds/60:.1f}분)")

            if estimated_tts_seconds < target_seconds * 0.8:  # 목표의 80% 미만이면 경고
                shortage = target_seconds - estimated_tts_seconds
                shortage_chars = int(shortage * 7.0)
                print(f"[ScriptEngine] ⚠️ 경고: 나레이션이 목표 대비 {shortage:.0f}초 ({shortage_chars}자) 부족!")
                print(f"[ScriptEngine] ⚠️ 달성률: {estimated_tts_seconds/target_seconds*100:.1f}%")

            print(f"[ScriptEngine] Generated {len(scenes)} scenes using Claude API")
            if character_profile.name:
                print(f"[ScriptEngine] 🎭 캐릭터: {character_profile.name} ({character_profile.age} {character_profile.gender})")
            return scenes, character_profile

        except Exception as e:
            print(f"[ScriptEngine] Error calling Claude API: {e}")
            print("[ScriptEngine] Falling back to template mode")
            return self._generate_template_scenes(profile, title_block), CharacterProfile()

    def _parse_llm_response(self, content: str, profile: ContentProfile) -> tuple:
        """LLM 응답을 파싱하여 (Scene 리스트, CharacterProfile) 튜플로 반환 (JSON 우선, 마크다운 폴백)"""
        scenes = []
        character_profile = CharacterProfile()

        # 1단계: JSON 파싱 시도 (권장 방식)
        json_data = self._extract_json_from_response(content)
        if json_data and "scenes" in json_data:
            print(f"[ScriptEngine] ✅ JSON 파싱 성공 ({len(json_data['scenes'])} scenes)")

            # ★ 캐릭터 프로파일 파싱
            if "character_profile" in json_data:
                cp = json_data["character_profile"]
                character_profile = CharacterProfile(
                    name=cp.get("name", ""),
                    age=cp.get("age", ""),
                    gender=cp.get("gender", ""),
                    appearance=cp.get("appearance", ""),
                    clothing=cp.get("clothing", ""),
                    distinctive_features=cp.get("distinctive_features", "")
                )
                print(f"[ScriptEngine] 🎭 캐릭터 프로파일 파싱: {character_profile.name}")

            try:
                for scene_dict in json_data["scenes"]:
                    scene = Scene(
                        scene_id=scene_dict.get("scene_id", "unknown"),
                        title=scene_dict.get("title", ""),
                        narration=scene_dict.get("narration", ""),
                        image_prompt=scene_dict.get("image_prompt", ""),
                        duration_sec=self._estimate_duration(
                            scene_dict.get("narration", ""),
                            profile.speech_speed
                        ),
                        # ★ Shot Planner 메타데이터 파싱
                        shot_type=scene_dict.get("shot_type", "medium"),
                        camera_motion=scene_dict.get("camera_motion", "slow_zoom_in"),
                        emotion_tag=scene_dict.get("emotion_tag", "warm"),
                        model_hint=scene_dict.get("model_hint", "auto")
                    )
                    scenes.append(scene)

                if scenes:
                    return scenes, character_profile
            except Exception as e:
                print(f"[ScriptEngine] ⚠️ JSON Scene 생성 실패: {e}")

        # 2단계: 마크다운 형식 폴백 (기존 로직)
        print(f"[ScriptEngine] JSON 파싱 실패, 마크다운 방식 시도")

        # Claude가 마크다운 형식으로 응답하는 경우 처리
        # 예: ## Scene 1: Hook (10초)
        scene_pattern = r'##\s+Scene\s+\d+:\s+(\w+)'
        scene_matches = list(re.finditer(scene_pattern, content, re.IGNORECASE))

        if scene_matches:
            print(f"[ScriptEngine] Parsing markdown format ({len(scene_matches)} scenes)")
            # 마크다운 형식으로 파싱
            for i, match in enumerate(scene_matches):
                scene_id = match.group(1).strip().lower()

                # 현재 scene의 시작 위치
                start_pos = match.end()

                # 다음 scene의 시작 위치 (또는 끝)
                if i + 1 < len(scene_matches):
                    end_pos = scene_matches[i + 1].start()
                else:
                    end_pos = len(content)

                # Scene 내용 추출
                scene_content = content[start_pos:end_pos].strip()

                # 나레이션 추출 (가이드라인 텍스트 제외)
                narration = self._extract_narration_from_markdown(scene_content)

                # 이미지 프롬프트 추출 (있으면)
                image_prompt = self._extract_image_prompt_from_markdown(scene_content)
                if not image_prompt:
                    image_prompt = f"{scene_id} scene, warm and friendly atmosphere"

                # Scene 객체 생성
                scene = Scene(
                    scene_id=scene_id,
                    title=f"{scene_id.capitalize()} 장면",
                    narration=narration,
                    image_prompt=image_prompt,
                    duration_sec=self._estimate_duration(narration, profile.speech_speed)
                )
                scenes.append(scene)

        else:
            # 원래 형식 시도 [SCENE: scene_id]
            scene_blocks = re.split(r'\[SCENE:\s*(\w+)\]', content)

            # 첫 번째 요소는 빈 문자열이므로 제거
            if len(scene_blocks) > 1:
                scene_blocks = scene_blocks[1:]

            # scene_id와 내용을 쌍으로 처리
            for i in range(0, len(scene_blocks), 2):
                if i + 1 < len(scene_blocks):
                    scene_id = scene_blocks[i].strip()
                    scene_content = scene_blocks[i + 1].strip()

                    # 제목, 나레이션, 이미지 설명 추출
                    title_match = re.search(r'제목:\s*(.+?)(?:\n|$)', scene_content)
                    narration_match = re.search(r'나레이션:\s*(.+?)(?:\n이미지|$)', scene_content, re.DOTALL)
                    image_match = re.search(r'이미지 설명:\s*(.+?)(?:\n|$)', scene_content, re.DOTALL)

                    title = title_match.group(1).strip() if title_match else scene_id
                    narration = narration_match.group(1).strip() if narration_match else ""
                    image_desc = image_match.group(1).strip() if image_match else ""

                    # Scene 객체 생성
                    scene = Scene(
                        scene_id=scene_id,
                        title=title,
                        narration=narration,
                        image_prompt=image_desc,
                        duration_sec=self._estimate_duration(narration, profile.speech_speed)
                    )
                    scenes.append(scene)

        # Scene이 하나도 파싱되지 않았으면 템플릿 사용
        if not scenes:
            print("[ScriptEngine] Failed to parse LLM response, using template")
            # 간단한 fallback
            return self._generate_template_scenes(profile, None), CharacterProfile()

        return scenes, character_profile

    def _extract_json_from_response(self, content: str) -> dict:
        """
        Claude 응답에서 JSON 추출 및 파싱 (더 견고한 버전)

        Returns:
            파싱된 JSON 딕셔너리 또는 None
        """
        json_str = None

        try:
            # 1. 먼저 마크다운 코드 블록에서 JSON 추출 시도
            json_pattern = r'```(?:json)?\s*(\{[\s\S]*?\})\s*```'
            match = re.search(json_pattern, content, re.DOTALL)

            if match:
                json_str = match.group(1)
            else:
                # 2. 코드 블록 없이 직접 JSON이 있는 경우
                start_idx = content.find('{')
                end_idx = content.rfind('}')

                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_str = content[start_idx:end_idx + 1]
                else:
                    print(f"[ScriptEngine] JSON 블록을 찾을 수 없음")
                    return None

            # 3. 첫 번째 시도: 원본 그대로 파싱
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass  # 첫 시도 실패, 수정 후 재시도

            # 4. 두 번째 시도: 기본 수정 후 파싱
            fixed_str = self._fix_json_string(json_str)
            try:
                return json.loads(fixed_str)
            except json.JSONDecodeError:
                pass  # 두 번째 시도 실패, 더 공격적으로 수정

            # 5. 세 번째 시도: 공격적인 수정
            aggressive_fixed = self._aggressive_json_fix(json_str)
            try:
                result = json.loads(aggressive_fixed)
                print(f"[ScriptEngine] ✅ 공격적 JSON 수정으로 파싱 성공")
                return result
            except json.JSONDecodeError as e:
                print(f"[ScriptEngine] JSON 파싱 최종 실패: {e}")
                if hasattr(e, 'pos'):
                    start = max(0, e.pos - 100)
                    end = min(len(aggressive_fixed), e.pos + 100)
                    print(f"[ScriptEngine] 문제 위치 주변: ...{aggressive_fixed[start:end]}...")
                return None

        except Exception as e:
            print(f"[ScriptEngine] JSON 추출 실패: {e}")
            return None

    def _aggressive_json_fix(self, json_str: str) -> str:
        """
        JSON 문자열을 더 공격적으로 수정
        - 모든 문자열 값 내의 특수 문자를 이스케이프
        """
        # 문자열 값 패턴: "key": "value" (값에 쉼표, 콜론 등이 있을 수 있음)
        # 먼저 줄바꿈을 임시 문자로 치환
        json_str = json_str.replace('\n', '⌫')
        json_str = json_str.replace('\r', '')

        # 각 문자열 필드를 순차적으로 처리
        # scene_id, title, narration, image_prompt 등의 값을 안전하게 추출
        result = []
        i = 0

        while i < len(json_str):
            # "key": " 패턴 찾기
            key_match = re.match(r'"([^"]+)":\s*"', json_str[i:])
            if key_match:
                key = key_match.group(1)
                key_end = i + key_match.end()

                # 값의 끝 찾기 - 다음 ", 또는 "} 또는 "] 찾기
                value_start = key_end
                value_end = None

                # 중첩되지 않은 " 찾기
                j = value_start
                while j < len(json_str):
                    if json_str[j] == '"':
                        # 이것이 값의 끝인지 확인
                        after = json_str[j+1:j+10].lstrip()
                        if after.startswith((',', '}', ']')):
                            value_end = j
                            break
                    j += 1

                if value_end:
                    value = json_str[value_start:value_end]
                    # 값 정리
                    value = value.replace('"', "'")
                    value = value.replace('⌫', ' ')
                    result.append(f'"{key}": "{value}"')
                    i = value_end + 1
                else:
                    result.append(json_str[i])
                    i += 1
            else:
                char = json_str[i]
                if char == '⌫':
                    result.append(' ')
                else:
                    result.append(char)
                i += 1

        return ''.join(result)

    def _fix_json_string(self, json_str: str) -> str:
        """JSON 문자열의 흔한 오류 수정 (더 견고한 버전)"""

        # 1. 제어 문자 정리
        json_str = json_str.replace('\r\n', '\n').replace('\r', '\n')

        # 2. 문자열 값 내부의 문제 해결을 위해 상태 기반 파싱
        result = []
        i = 0
        in_string = False
        string_start = -1

        while i < len(json_str):
            char = json_str[i]

            if char == '"' and (i == 0 or json_str[i-1] != '\\'):
                if not in_string:
                    # 문자열 시작
                    in_string = True
                    string_start = i
                    result.append(char)
                else:
                    # 문자열 끝인지 확인 - 다음 문자가 :, ,, }, ] 중 하나이면 끝
                    next_non_space = i + 1
                    while next_non_space < len(json_str) and json_str[next_non_space] in ' \t\n':
                        next_non_space += 1

                    if next_non_space < len(json_str) and json_str[next_non_space] in ':,}]':
                        # 실제 문자열 끝
                        in_string = False
                        result.append(char)
                    else:
                        # 문자열 내부의 따옴표 - 작은따옴표로 변환
                        result.append("'")
            elif in_string:
                # 문자열 내부에서 특수 문자 처리
                if char == '\n':
                    result.append(' ')  # 줄바꿈을 공백으로
                elif char == '\t':
                    result.append(' ')  # 탭을 공백으로
                else:
                    result.append(char)
            else:
                result.append(char)

            i += 1

        json_str = ''.join(result)

        # 3. 후행 쉼표 제거
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

        # 4. 연속된 공백 정리 (문자열 외부만)
        json_str = re.sub(r'\n\s*\n', '\n', json_str)

        return json_str

    def _extract_narration_from_markdown(self, scene_content: str) -> str:
        """
        마크다운 형식에서 실제 나레이션 텍스트만 추출
        "나레이션:", "**나레이션:**", "Narration:", "**화면:**" 등의 마커와 이미지 설명 제거
        """
        # 다양한 마커 패턴 시도 (따옴표 다양한 형식 지원: ", ", ', ')
        patterns = [
            # **내레이션:** 또는 **나레이션:** 다음의 인용 부호 안의 텍스트만 추출
            r'\*\*[내나]레이션:\*\*\s*["\"\'](.+?)["\"\']',  # 따옴표로 감싸진 부분만
            # 따옴표 없이 바로 시작하는 경우
            r'\*\*[내나]레이션:\*\*\s*([^*\n].+?)(?=\n\*\*|\n\n|$)',
            # 영문 패턴
            r'\*\*Narration:\*\*\s*["\"\'](.+?)["\"\']',
            r'\*\*Narration:\*\*\s*([^*\n].+?)(?=\n\*\*|\n\n|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, scene_content, re.DOTALL | re.IGNORECASE)
            if match:
                narration = match.group(1).strip()
                # 추가 정리: 불필요한 마크다운 제거
                narration = re.sub(r'\*\*', '', narration)  # ** 제거
                narration = re.sub(r'\n\s*\n', ' ', narration)  # 빈 줄 제거
                narration = narration.strip()
                print(f"[ScriptEngine] ✓ Extracted narration: {narration[:100]}...")
                return narration

        # 마커를 찾지 못한 경우, 전체 내용에서 명확한 가이드라인 제거
        cleaned = scene_content

        # "제목:", "나레이션:", "이미지 설명:" 등의 레이블과 그 뒤의 내용 분리
        # 실제 나레이션은 "나레이션:" 다음부터 "이미지" 관련 텍스트 전까지
        lines = scene_content.split('\n')
        narration_lines = []
        in_narration = False

        for line in lines:
            line_stripped = line.strip()

            # 나레이션 시작 감지
            if re.match(r'\*?\*?나레이션:\*?\*?', line_stripped, re.IGNORECASE):
                in_narration = True
                # 콜론 뒤에 바로 텍스트가 있으면 추가
                text_after_colon = re.sub(r'^[\*\s]*나레이션:[\*\s]*', '', line_stripped, flags=re.IGNORECASE)
                if text_after_colon:
                    narration_lines.append(text_after_colon)
                continue

            # 이미지 설명 시작 시 종료
            if re.match(r'\*?\*?이미지|Image', line_stripped, re.IGNORECASE):
                in_narration = False
                continue

            # 제목 라인 스킵
            if re.match(r'\*?\*?제목:|Title:', line_stripped, re.IGNORECASE):
                continue

            # 나레이션 수집 중이면 추가
            if in_narration and line_stripped:
                narration_lines.append(line_stripped)

        if narration_lines:
            result = ' '.join(narration_lines).strip()
            # 마크다운 굵게 제거
            result = re.sub(r'\*\*', '', result)
            print(f"[ScriptEngine] Extracted narration (line-by-line): {result[:100]}...")
            return result

        # 그래도 없으면 전체 내용 반환 (fallback)
        print(f"[ScriptEngine] Warning: Could not extract narration, using full content")
        return scene_content.strip()

    def _extract_image_prompt_from_markdown(self, scene_content: str) -> str:
        """마크다운 형식에서 이미지 프롬프트 추출"""
        patterns = [
            r'\*\*이미지 설명:\*\*\s*(.+?)(?:\n\n|$)',
            r'이미지 설명:\s*(.+?)(?:\n\n|$)',
            r'\*\*Image:\*\*\s*(.+?)(?:\n\n|$)',
            r'Image:\s*(.+?)(?:\n\n|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, scene_content, re.DOTALL | re.IGNORECASE)
            if match:
                prompt = match.group(1).strip()
                prompt = re.sub(r'\*\*', '', prompt)  # ** 제거
                return prompt

        return ""

    def _estimate_duration(self, narration: str, speech_speed: float) -> int:
        """나레이션 텍스트 길이로 대략적인 재생 시간 추정"""
        # 한국어 기준: 1초당 약 3-4글자 (천천히 읽을 때)
        chars_per_second = 7.0  # Gemini TTS 실측 기반
        adjusted_speed = chars_per_second * speech_speed

        char_count = len(narration)
        duration = int(char_count / adjusted_speed)

        return max(5, duration)  # 최소 5초

    def _adjust_durations(self, scenes: list, target_duration: int, is_shorts: bool) -> list:
        """
        Scene들의 duration을 목표 시간에 맞게 조정

        Args:
            scenes: Scene 리스트
            target_duration: 목표 총 duration (초)
            is_shorts: Shorts 여부

        Returns:
            조정된 Scene 리스트
        """
        if not scenes:
            return scenes

        # 현재 총 duration 계산
        total_duration = sum(s.duration_sec for s in scenes)
        print(f"[ScriptEngine] Duration adjustment: {total_duration}s → {target_duration}s (target)")

        # 목표보다 길면 비율로 조정 (downscaling)
        if total_duration > target_duration:
            ratio = target_duration / total_duration
            print(f"[ScriptEngine] Scaling down by {ratio:.2f}")

            for scene in scenes:
                new_duration = max(3, int(scene.duration_sec * ratio))  # 최소 3초
                scene.duration_sec = new_duration

            # 재계산
            new_total = sum(s.duration_sec for s in scenes)
            print(f"[ScriptEngine] Adjusted total: {new_total}s")

        # 목표보다 짧으면 비율로 조정 (upscaling)
        elif total_duration < target_duration:
            ratio = target_duration / total_duration
            print(f"[ScriptEngine] Scaling up by {ratio:.2f}")

            for scene in scenes:
                new_duration = int(scene.duration_sec * ratio)
                # 씬당 최대 5분(300초)으로 제한
                scene.duration_sec = min(300, new_duration)

            # 재계산
            new_total = sum(s.duration_sec for s in scenes)
            print(f"[ScriptEngine] Adjusted total: {new_total}s")

            # 여전히 목표에 도달하지 못하면 균등하게 추가
            if new_total < target_duration:
                remaining = target_duration - new_total
                per_scene = remaining // len(scenes)
                extra = remaining % len(scenes)

                for i, scene in enumerate(scenes):
                    scene.duration_sec += per_scene
                    if i < extra:
                        scene.duration_sec += 1

                final_total = sum(s.duration_sec for s in scenes)
                print(f"[ScriptEngine] Final adjusted total: {final_total}s")

        # Shorts인데 여전히 길면 각 scene에 최대값 적용
        if is_shorts:
            max_per_scene = target_duration // len(scenes) + 2  # 약간의 여유
            for scene in scenes:
                if scene.duration_sec > max_per_scene:
                    scene.duration_sec = max_per_scene

        return scenes

    def _generate_template_scenes(self, profile: ContentProfile,
                                  title_block: TitleThumbnailResult = None) -> list:
        """템플릿 기반 더미 scene 생성 (API 없을 때 fallback)"""
        scenes = []

        # 템플릿에 따라 scene 구조 결정
        template = profile.template_id

        # ★ 5대 장르 템플릿 ★

        # ① 감동 실화형 (Emotional Storytelling)
        # 구성: 실제 사례 → 인물 소개 → 갈등/고난 → 극복/메시지 → 여운 마무리
        if template == "emotional_story":
            scene_ids = ["hook", "intro", "conflict", "struggle", "resolution", "message", "closing"]
        elif template == "emotional_story_short":
            scene_ids = ["hook", "story", "resolution", "closing"]

        # ② 회상·향수형 (Nostalgic & Retrospective)
        # 구성: 시대/물건 도입 → 당시 상황 → 오늘과의 차이 → 회상 → 여운 마무리
        elif template == "nostalgic_story":
            scene_ids = ["hook", "era_intro", "back_then", "contrast", "memories", "reflection", "closing"]
        elif template == "nostalgic_story_short":
            scene_ids = ["hook", "memories", "reflection", "closing"]

        # ③ 교훈·명언형 (Wisdom & Life Philosophy)
        # 구성: 명언 도입 → 배경 이야기 → 인물 설명 → 오늘 적용 교훈 → 정리
        elif template == "wisdom_story":
            scene_ids = ["hook", "quote_intro", "background", "figure", "application", "lesson", "closing"]
        elif template == "wisdom_story_short":
            scene_ids = ["hook", "wisdom", "lesson", "closing"]

        # ④ 지식·정보형 (Practical Knowledge)
        # 구성: 문제 제시 → 3~5가지 팁 → 사례 설명 → 실천법 → 요약 마무리
        elif template == "knowledge_info":
            scene_ids = ["hook", "problem", "tip1", "tip2", "tip3", "practice", "summary", "closing"]
        elif template == "knowledge_info_short":
            scene_ids = ["hook", "tips", "practice", "closing"]

        # ⑤ 명작·음악 해설형 (Classic Review & Music Story)
        # 구성: 작품 소개 → 배경 설명 → 창작자 이야기 → 핵심 해석 → 감정 연결
        elif template == "classic_review":
            scene_ids = ["hook", "work_intro", "background", "creator", "interpretation", "emotion", "closing"]
        elif template == "classic_review_short":
            scene_ids = ["hook", "review", "emotion", "closing"]

        # 유아 (기존 유지)
        elif template == "kids_story":
            scene_ids = ["intro", "problem", "try1", "try2", "try3", "resolution", "ending"]
        elif template == "kids_story_short":
            scene_ids = ["intro", "story", "resolution", "ending"]

        # 기본 (감동 실화형으로 폴백)
        else:
            scene_ids = ["hook", "story", "message", "closing"]

        # 전체 시간을 scene 수로 나눠서 각 scene 길이 결정
        total_duration = profile.duration_sec
        avg_scene_duration = max(3, total_duration // len(scene_ids))  # 최소 3초

        for idx, sid in enumerate(scene_ids):
            scenes.append(
                Scene(
                    scene_id=sid,
                    title=f"{sid} 장면",
                    narration=f"[{sid}] 여기에 {sid} 장면의 나레이션이 들어갑니다. (Claude API 키를 설정하면 실제 대본이 생성됩니다)",
                    image_prompt=f"{sid} 장면을 표현하는 이미지",
                    duration_sec=avg_scene_duration
                )
            )

        return scenes

    def _get_genre_instructions(self, mode_id: str, genre_style: str, core_emotion: list) -> str:
        """장르별 스크립트 작성 지침 생성 (현재 야담 모드만 지원)"""

        genre_guides = {
            # 야담형 서사 (전통 이야기)
            "yadam_kr_v1": """
🎭 야담형 서사 스토리 지침:

★★★ 개연성 확보를 위한 필수 규칙 ★★★

1. 스토리 구조 (반드시 순서대로):
   ① 도입부: 시대/장소 설정, 평화로운 일상 묘사
   ② 갈등 발생: 악당/문제 등장 (명확한 이유 제시)
   ③ 주인공 등장: 평범해 보이지만 특별한 과거 암시
   ④ 긴장 고조: 주인공과 악당의 첫 대면, "그들은 몰랐다" 패턴
   ⑤ 정체 공개: 주인공의 진짜 정체/과거 회상 (구체적 배경)
   ⑥ 위기/갈등: 소중한 것이 위협받음 (동기 명확화)
   ⑦ 클라이맥스: 대결/해결 (과정을 상세히)
   ⑧ 결말: 여운 있는 마무리, 직접적 교훈 금지

2. 개연성 확보 필수 요소:
   - 주인공의 능력에는 반드시 배경 설명 (왜 그런 능력이 있는지)
   - 악당의 행동에도 이유 부여 (단순 악행 X, 동기 O)
   - 사건 전개는 인과관계로 연결 (A 때문에 B가 발생)
   - 해결 방식은 복선 회수 (앞에서 언급된 능력/도구 활용)

3. 문어체 스타일 (설희야담 스타일):
   - "~했습니다", "~이었습니다" 완전한 존댓말
   - 비유와 묘사 풍부하게 사용
   - 전환점 표현 필수: "바로 그때였습니다", "그들은 몰랐습니다"

★★★ 묘사 밀도 강화 (필수) ★★★

4. 배경 묘사 (매 장면 4-5문장 필수):
   - 시각: 색감, 빛, 그림자, 형태 (예: "붉은 노을이 기와지붕을 물들이고")
   - 청각: 소리, 대화, 자연음 (예: "귀뚜라미 소리가 처마 밑에서")
   - 후각: 냄새, 향기 (예: "막걸리 익는 구수한 냄새가 코끝을 간질이고")
   - 촉각: 질감, 온도 (예: "차가운 밤공기가 목덜미를 스치고")

5. 의성어/의태어 (매 문단마다 1개 이상 필수):
   - 동작: 휙, 스윽, 펄럭, 덜컹, 뚜벅뚜벅, 사뿐사뿐
   - 소리: 뚜둑, 쿵, 철커덩, 찰랑찰랑, 쨍그랑
   - 감정: 두근두근, 조마조마, 오싹, 아릿아릿
   - 상태: 반짝반짝, 아슴아슴, 희미하게, 서늘하게

6. 문장 분량 (각 장면 최소 8-10문장):
   - 상황 설명 2-3문장
   - 배경/분위기 묘사 3-4문장 (오감 활용)
   - 행동/대화 2-3문장
   - 내면 심리/감정 1-2문장

7. 인물 묘사 (등장시마다 상세하게):
   - 표정: 눈빛, 입꼬리, 미간, 볼 (예: "미간이 찌푸려지며 눈빛이 날카로워지고")
   - 손동작: 손가락, 주먹, 손바닥 (예: "주먹을 꽉 쥐자 손등에 힘줄이 불끈")
   - 자세/몸짓: 어깨, 허리, 고개 (예: "어깨가 축 늘어지며")
   - 내면심리: 생각, 감정, 갈등 (예: "가슴 한구석이 서늘해지며")

8. 피해야 할 것:
   - 갑작스러운 능력 등장 (복선 없이)
   - 설명 없는 우연의 일치
   - 직접적 교훈 마무리 ("그래서 착하게 살아야...")
   - 현대적 표현이나 말투
   - 짧고 건조한 묘사 (반드시 오감으로 풍부하게)

★ 이미지 스타일: 한국 만화/웹툰 일러스트 스타일로 묘사할 것!
"""
        }

        # 기본 지침 (야담 스타일로 폴백)
        default_guide = genre_guides["yadam_kr_v1"]

        return genre_guides.get(mode_id, default_guide)

    def _assign_broll(self, scenes: list, profile: ContentProfile,
                     title_block: TitleThumbnailResult) -> list:
        """
        B-roll 비디오를 사용할 scene 결정 및 검색 쿼리 생성 (비율 기반)

        Args:
            scenes: Scene 리스트
            profile: 컨텐츠 프로필
            title_block: 제목/썸네일 정보

        Returns:
            B-roll 정보가 추가된 Scene 리스트
        """
        # 환경 변수에서 비디오 비율 가져오기 (0-100)
        video_ratio = int(os.getenv("BROLL_VIDEO_RATIO", "50"))
        video_ratio = max(0, min(100, video_ratio))  # 0-100 범위로 제한

        # Scene별 우선순위 (높을수록 비디오 사용 우선)
        scene_priority = {
            "hook": 10,      # 최우선 - 오프닝
            "action": 9,     # 행동 유도
            "empathy": 8,    # 공감
            "summary": 7,    # 요약
            "climax": 6,     # 클라이맥스
            "old_days": 5,   # 추억
            "story_intro": 4,
            "comfort": 3,
            "lesson": 2,
            "point1": 1,
            "point2": 1,
            "point3": 1,
            "point4": 1,
        }

        # 비율에 따라 비디오를 사용할 scene 수 계산
        total_scenes = len(scenes)
        video_count = int(total_scenes * video_ratio / 100)

        print(f"[ScriptEngine] B-roll ratio: {video_ratio}% ({video_count}/{total_scenes} scenes)")

        # 우선순위로 정렬
        scenes_with_priority = [
            (scene, scene_priority.get(scene.scene_id, 0))
            for scene in scenes
        ]
        scenes_with_priority.sort(key=lambda x: x[1], reverse=True)

        # 카테고리별 기본 검색 키워드
        category_keywords = {
            "health": "senior health exercise wellness meditation",
            "money": "retirement planning savings financial security",
            "emotion": "family warmth love togetherness",
            "memory": "vintage old times nostalgic memories",
            "general": "peaceful nature calm lifestyle"
        }

        category_base = category_keywords.get(profile.category, "peaceful nature")

        # Scene ID별 특화 키워드
        scene_keywords = {
            "hook": "attention grabbing interesting",
            "empathy": "relatable everyday moments",
            "summary": "peaceful conclusion calm",
            "action": "motivation positive energy",
            "climax": "emotional touching moments",
            "old_days": "vintage nostalgic old times",
            "story_intro": "beginning story opening",
            "comfort": "comfort peaceful warmth",
            "lesson": "learning wisdom knowledge"
        }

        # 상위 N개 scene에 비디오 할당
        for idx, (scene, priority) in enumerate(scenes_with_priority):
            if idx < video_count:
                scene.use_video = True

                # 검색 쿼리 생성
                query_parts = []

                # 카테고리 기본 키워드
                query_parts.append(category_base)

                # Scene 특화 키워드
                scene_specific = scene_keywords.get(scene.scene_id, "")
                if scene_specific:
                    query_parts.append(scene_specific)

                # 한국 관련 키워드 추가 (선택적)
                if profile.category in ["memory", "emotion"]:
                    query_parts.append("asian korean")

                scene.broll_query = " ".join(query_parts)

                print(f"[ScriptEngine] ✓ Video: {scene.scene_id} (priority {priority}): '{scene.broll_query}'")
            else:
                scene.use_video = False
                print(f"[ScriptEngine] ✗ Image: {scene.scene_id}")

        return scenes

    # ==========================================
    # ★★★ 4파트 분할 생성 방식 (15분 이상 영상용) ★★★
    # ==========================================

    def _generate_partitioned_script(self, profile: ContentProfile,
                                     title_block: TitleThumbnailResult) -> tuple:
        """
        긴 영상(15분+)을 위한 4파트 분할 스크립트 생성

        1단계: 전체 스토리 아웃라인 생성
        2단계: 4파트로 나눠서 상세 대본 생성 (맥락 유지)

        Returns:
            (scenes, character_profile) 튜플
        """
        duration_minutes = profile.duration_sec // 60
        # ★ Gemini TTS 실측: 약 7자/초 = 420자/분
        # 하지만 Claude가 목표 글자수의 약 65%만 생성하므로 1.6배 보정
        # 420 * 1.6 = 672 → 반올림하여 670자/분
        chars_per_minute = 670
        total_chars_needed = int(duration_minutes * chars_per_minute)
        chars_per_part = total_chars_needed // 4

        print(f"[ScriptEngine] ★★★ 4파트 분할 생성 모드 ★★★")
        print(f"[ScriptEngine] 목표: {duration_minutes}분 = {total_chars_needed}자 (보정된 670자/분)")
        print(f"[ScriptEngine] 파트당: 약 {chars_per_part}자 ({duration_minutes//4}분)")

        # 1단계: 스토리 아웃라인 생성
        print(f"\n[ScriptEngine] === 1단계: 스토리 아웃라인 생성 ===")
        outline = self._generate_outline(profile, title_block)

        if not outline:
            print("[ScriptEngine] 아웃라인 생성 실패, 기본 아웃라인으로 진행")
            # ★ 기본 아웃라인 생성 (파트별 대본 생성은 계속 진행)
            outline = {
                "title": title_block.final_title if title_block else "이야기",
                "synopsis": f"{title_block.main_keyword if title_block else '주제'}에 관한 이야기입니다.",
                "character": {
                    "name": "주인공",
                    "age": "중년",
                    "gender": "남성",
                    "description": "평범한 외모의 중년 남성"
                },
                "scenes": [
                    {"id": "opening", "title": "시작", "summary": "이야기의 시작을 알리는 장면"},
                    {"id": "hook", "title": "흥미 유발", "summary": "시청자의 관심을 끄는 장면"},
                    {"id": "intro", "title": "소개", "summary": "배경과 인물을 소개하는 장면"},
                    {"id": "rising1", "title": "전개1", "summary": "이야기가 본격적으로 전개되는 장면"},
                    {"id": "rising2", "title": "전개2", "summary": "갈등이 심화되는 장면"},
                    {"id": "reveal", "title": "반전", "summary": "중요한 사실이 드러나는 장면"},
                    {"id": "conflict", "title": "갈등", "summary": "핵심 갈등이 발생하는 장면"},
                    {"id": "climax1", "title": "클라이맥스1", "summary": "긴장감이 최고조에 달하는 장면"},
                    {"id": "climax2", "title": "클라이맥스2", "summary": "결정적 순간"},
                    {"id": "resolution", "title": "해결", "summary": "갈등이 해결되는 장면"},
                    {"id": "closing", "title": "마무리", "summary": "여운을 남기며 마무리하는 장면"}
                ]
            }
            print(f"[ScriptEngine] 기본 아웃라인 생성됨: 11개 씬")

        # 파트 정의 (기승전결)
        parts = [
            {"name": "기", "scenes": ["opening", "hook", "intro"], "chars": chars_per_part},
            {"name": "승", "scenes": ["rising1", "rising2", "reveal"], "chars": chars_per_part},
            {"name": "전", "scenes": ["conflict", "climax1", "climax2"], "chars": chars_per_part},
            {"name": "결", "scenes": ["resolution", "closing"], "chars": chars_per_part},
        ]

        all_scenes = []
        character_profile = None
        previous_summary = ""

        # 2단계: 파트별 상세 대본 생성
        for part_idx, part in enumerate(parts):
            part_num = part_idx + 1
            print(f"\n[ScriptEngine] === 2단계: 파트 {part_num}/4 ({part['name']}) 생성 ===")

            scenes, char_profile = self._generate_part(
                profile=profile,
                title_block=title_block,
                outline=outline,
                part_info=part,
                part_num=part_num,
                previous_summary=previous_summary
            )

            if scenes:
                all_scenes.extend(scenes)
                if char_profile and char_profile.name and not character_profile:
                    character_profile = char_profile

                # 다음 파트를 위한 요약 생성
                previous_summary = self._summarize_scenes(scenes)
                print(f"[ScriptEngine] 파트 {part_num} 완료: {len(scenes)}개 씬, {sum(len(s.narration) for s in scenes)}자")
            else:
                # ★ 파트 생성 실패 시 폴백 씬 생성
                print(f"[ScriptEngine] 파트 {part_num} 생성 실패 → 폴백 씬 생성")
                fallback_scenes = self._create_fallback_scenes_for_part(
                    outline=outline,
                    part_info=part,
                    title_block=title_block
                )
                all_scenes.extend(fallback_scenes)
                print(f"[ScriptEngine] 폴백 씬 {len(fallback_scenes)}개 생성됨")

        if not character_profile:
            character_profile = CharacterProfile()

        # 총 나레이션 길이 확인
        total_chars = sum(len(s.narration) for s in all_scenes)
        # ★ Gemini TTS 실측: 약 7자/초
        estimated_seconds = total_chars / 7.0
        print(f"\n[ScriptEngine] ★ 분할 생성 완료:")
        print(f"[ScriptEngine] ★ 총 {len(all_scenes)}개 씬, {total_chars}자")
        print(f"[ScriptEngine] ★ 예상 TTS 시간: {estimated_seconds:.0f}초 ({estimated_seconds/60:.1f}분) [Gemini TTS 기준]")

        return all_scenes, character_profile

    # ★ 아웃라인 패턴 정의 (환경변수 OUTLINE_PATTERN으로 선택)
    OUTLINE_PATTERNS = {
        # 패턴 1: 정체공개형 - 평범해 보이는 주인공의 정체가 드러남
        "reveal": {
            "name": "정체공개형",
            "description": "평범해 보이는 주인공이 알고 보니 대단한 인물",
            "structure": """
★ 이야기 패턴: 정체공개형 (숨겨진 정체가 드러나는 이야기)

필수 요소:
1. 주인공은 처음에 평범하거나 무시당하는 존재로 등장
2. 악당/문제 상황이 발생하여 위기 조성
3. "그들은 몰랐다" - 주인공의 과거/정체에 대한 암시
4. 주인공의 진짜 정체 공개 (전직 장군, 무림 고수, 은퇴한 명의 등)
5. 정체 공개 후 문제 해결
6. 여운 있는 마무리 (다시 평범한 일상으로)

예시 구조:
- opening: 평화로운 마을/시장 풍경
- hook: 악당 등장, 행패 시작
- intro: 평범해 보이는 주인공 등장 (보따리 장수, 노인 등)
- rising1: 악당과 주인공의 첫 대면
- rising2: 긴장 고조, "그들은 몰랐다" 복선
- reveal: 주인공의 과거 회상 또는 정체 암시
- conflict: 악당의 본격적인 위협
- climax1: 주인공 정체 공개
- climax2: 대결/해결
- resolution: 악당 응징
- closing: 여운 있는 마무리
"""
        },

        # 패턴 2: 성장형 - 시련을 통해 성장
        "growth": {
            "name": "성장형",
            "description": "주인공이 시련을 겪으며 성장하는 이야기",
            "structure": """
★ 이야기 패턴: 성장형 (시련과 성장의 이야기)

필수 요소:
1. 주인공은 부족하거나 미숙한 상태로 시작
2. 스승/조력자 등장
3. 시련 발생 (3번의 실패 또는 도전)
4. 깨달음의 순간
5. 성장한 모습으로 문제 해결
6. 다음 세대에게 가르침 전달

예시 구조:
- opening: 미숙한 주인공의 일상
- hook: 목표/꿈 제시 (장인이 되고 싶다 등)
- intro: 스승 등장, 수련 시작
- rising1: 첫 번째 시련과 실패
- rising2: 두 번째 시련과 좌절
- reveal: 스승의 가르침/깨달음
- conflict: 최종 시험 또는 위기
- climax1: 성장한 실력 발휘
- climax2: 목표 달성
- resolution: 인정받는 주인공
- closing: 다음 세대에게 전수
"""
        },

        # 패턴 3: 복수/통쾌형 - 억울함을 갚아주는 이야기
        "revenge": {
            "name": "복수형",
            "description": "억울함을 당한 후 통쾌하게 갚아주는 이야기",
            "structure": """
★ 이야기 패턴: 복수/통쾌형 (권선징악 이야기)

필수 요소:
1. 선량한 피해자와 탐욕스러운 가해자 설정
2. 부당한 피해 발생 (재산 강탈, 누명 등)
3. 절망적 상황에서 조력자 등장 (지혜로운 인물)
4. 치밀한 계획 수립
5. 악인의 본성을 드러나게 하는 함정
6. 통쾌한 응징과 피해 회복

예시 구조:
- opening: 행복한 가정/평화로운 일상
- hook: 탐욕스러운 악인 등장
- intro: 부당한 피해 발생 (사기, 강탈)
- rising1: 피해자의 절망과 고통
- rising2: 지혜로운 조력자 등장
- reveal: 복수 계획 수립
- conflict: 계획 실행 시작
- climax1: 악인을 함정에 빠뜨림
- climax2: 악인의 본성 폭로
- resolution: 통쾌한 응징, 피해 회복
- closing: 정의 실현, 교훈
"""
        },

        # 패턴 4: 반전형 - 예상치 못한 반전
        "twist": {
            "name": "반전형",
            "description": "예상치 못한 반전이 있는 이야기",
            "structure": """
★ 이야기 패턴: 반전형 (뜻밖의 진실)

필수 요소:
1. 겉으로 보이는 상황과 실제가 다름
2. 시청자도 속는 미스디렉션
3. 작은 단서들을 곳곳에 배치 (복선)
4. 반전 순간의 임팩트
5. 복선 회수로 "아하!" 느낌
6. 진짜 의미가 드러나는 결말

예시 구조:
- opening: 평범해 보이는 상황 설정
- hook: 미스터리/의문 제시
- intro: 겉으로 드러난 이야기 전개
- rising1: 작은 이상함들 (복선)
- rising2: 긴장감 고조
- reveal: 첫 번째 힌트
- conflict: 혼란/갈등
- climax1: 반전 공개!
- climax2: 복선 회수
- resolution: 진짜 의미 이해
- closing: 여운 있는 마무리
"""
        },

        # 패턴 5: 대결형 - 선과 악의 대결
        "showdown": {
            "name": "대결형",
            "description": "선과 악의 정면 대결",
            "structure": """
★ 이야기 패턴: 대결형 (선악의 정면승부)

필수 요소:
1. 강력한 악당의 위협
2. 정의로운 주인공 (또는 영웅)
3. 초반 패배 또는 위기
4. 약점 발견 또는 동료 합류
5. 최종 대결
6. 선의 승리와 평화 회복

예시 구조:
- opening: 평화로운 마을/세상
- hook: 강력한 악당 등장, 위협
- intro: 주인공 소개, 대결 결심
- rising1: 첫 대결, 패배 또는 무승부
- rising2: 수련/준비/동료 모집
- reveal: 악당의 약점 발견
- conflict: 악당의 반격, 위기
- climax1: 최종 대결 시작
- climax2: 치열한 승부
- resolution: 선의 승리
- closing: 평화 회복, 영웅의 귀환
"""
        },

        # 패턴 6: 롤플레잉형 - 점점 강해지는 주인공
        "levelup": {
            "name": "롤플레잉형",
            "description": "점점 강해지는 주인공 (레벨업)",
            "structure": """
★ 이야기 패턴: 롤플레잉형 (점점 강해지는 주인공)

필수 요소:
1. 주인공은 처음에 약하거나 무력한 상태
2. 첫 번째 시련에서 처참하게 패배 (굴욕)
3. 숨겨진 능력 발견 또는 특별한 기회 획득
4. 단계별 성장 (레벨1 → 레벨2 → 레벨3)
5. 각 단계마다 새로운 적 또는 시련 등장
6. 성장할 때마다 과거 자신을 뛰어넘는 모습
7. 최종 보스와의 대결에서 압도적 승리
8. "이제는 달라졌다"는 카타르시스

예시 구조:
- opening: 무력한 주인공의 일상 (무시당함, 괴롭힘)
- hook: 첫 번째 굴욕적 패배 (이대로는 안 된다)
- intro: 특별한 기회 발견 (스승, 비급, 능력 각성)
- rising1: 첫 번째 성장 + 복수 (레벨1 → 약한 적 처치)
- rising2: 두 번째 성장 + 중간 보스 (레벨2 → 더 강한 적)
- reveal: 주인공의 진정한 잠재력 암시
- conflict: 최강의 적 등장, 위기
- climax1: 세 번째 성장 (각성/폭발)
- climax2: 최종 대결, 압도적 승리
- resolution: 과거의 굴욕 청산
- closing: 새로운 강자로서의 일상 (존경받음)

★ 핵심 감정: 굴욕 → 설움 → 각성 → 쾌감 → 통쾌함
★ 성장 표현: "그때의 나와 지금의 나는 다르다" 대비 강조
"""
        }
    }

    def _get_outline_pattern(self) -> dict:
        """환경변수에서 아웃라인 패턴 선택"""
        pattern_name = os.getenv("OUTLINE_PATTERN", "reveal")
        pattern = self.OUTLINE_PATTERNS.get(pattern_name)

        if not pattern:
            print(f"[ScriptEngine] 알 수 없는 패턴 '{pattern_name}', 기본값 'reveal' 사용")
            pattern = self.OUTLINE_PATTERNS["reveal"]

        print(f"[ScriptEngine] ★ 아웃라인 패턴: {pattern['name']} ({pattern_name})")
        return pattern

    def _generate_outline(self, profile: ContentProfile,
                          title_block: TitleThumbnailResult) -> dict:
        """
        전체 스토리 아웃라인 생성 (뼈대)

        환경변수 OUTLINE_PATTERN으로 패턴 선택:
        - reveal: 정체공개형 (기본값)
        - growth: 성장형
        - revenge: 복수/통쾌형
        - twist: 반전형
        - showdown: 대결형

        Returns:
            {"title": "...", "synopsis": "...", "scenes": [{"id": "opening", "title": "...", "summary": "..."}]}
        """
        genre_style = profile.extra.get("genre_style", "yadam_kr_v1")

        # 아웃라인 패턴 가져오기
        pattern = self._get_outline_pattern()

        prompt = f"""당신은 한국 야담/전통 이야기 전문 작가입니다.
다음 주제로 {profile.duration_sec // 60}분짜리 이야기의 전체 구조를 설계해주세요.

[주제]
{title_block.main_keyword}

[최종 제목]
{title_block.final_title}

{pattern['structure']}

[필수 출력 형식 - JSON]
{{
  "title": "이야기 제목",
  "synopsis": "전체 이야기 요약 (3-5문장)",
  "character": {{
    "name": "주인공 이름",
    "age": "나이대",
    "gender": "성별",
    "description": "외모/성격 설명"
  }},
  "scenes": [
    {{"id": "opening", "title": "장면 제목", "summary": "이 장면에서 일어나는 일 (2-3문장)"}},
    {{"id": "hook", "title": "...", "summary": "..."}},
    {{"id": "intro", "title": "...", "summary": "..."}},
    {{"id": "rising1", "title": "...", "summary": "..."}},
    {{"id": "rising2", "title": "...", "summary": "..."}},
    {{"id": "reveal", "title": "...", "summary": "..."}},
    {{"id": "conflict", "title": "...", "summary": "..."}},
    {{"id": "climax1", "title": "...", "summary": "..."}},
    {{"id": "climax2", "title": "...", "summary": "..."}},
    {{"id": "resolution", "title": "...", "summary": "..."}},
    {{"id": "closing", "title": "...", "summary": "..."}}
  ]
}}

★ 중요:
- 11개 씬 모두 포함
- 각 씬의 summary는 구체적으로 (무슨 일이, 왜, 어떻게)
- 위 이야기 패턴을 반드시 따를 것
- JSON만 출력 (설명 없이)
- ⚠️ 절대 문자열 안에 큰따옴표(") 사용 금지! 작은따옴표(')만 사용
"""

        try:
            # prefill로 JSON 시작 강제
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                temperature=0.7,
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": "{"}  # prefill: JSON으로 시작
                ]
            )

            # prefill 때문에 응답 앞에 { 붙여줘야 함
            content = "{" + response.content[0].text
            outline = self._extract_json_from_response(content)

            if outline and "scenes" in outline:
                print(f"[ScriptEngine] 아웃라인 생성 성공: {len(outline['scenes'])}개 씬")
                return outline
            else:
                print("[ScriptEngine] 아웃라인 JSON 파싱 실패")
                print(f"[ScriptEngine] 응답 앞 200자: {content[:200]}")
                return None

        except Exception as e:
            print(f"[ScriptEngine] 아웃라인 생성 오류: {e}")
            return None

    def _generate_part(self, profile: ContentProfile,
                       title_block: TitleThumbnailResult,
                       outline: dict,
                       part_info: dict,
                       part_num: int,
                       previous_summary: str) -> tuple:
        """
        파트별 상세 대본 생성

        Args:
            profile: 컨텐츠 프로필
            title_block: 제목 정보
            outline: 전체 스토리 아웃라인
            part_info: {"name": "기", "scenes": ["opening", "hook", "intro"], "chars": 1500}
            part_num: 파트 번호 (1-4)
            previous_summary: 이전 파트 요약 (맥락 유지)
        """
        scene_ids = part_info["scenes"]
        target_chars = part_info["chars"]
        chars_per_scene = target_chars // len(scene_ids)

        # 해당 파트의 씬 아웃라인 추출
        scene_outlines = []
        for scene in outline.get("scenes", []):
            if scene.get("id") in scene_ids:
                scene_outlines.append(scene)

        # 캐릭터 정보
        character = outline.get("character", {})

        context = f"""
[이전 이야기 요약]
{previous_summary if previous_summary else "(이야기의 시작입니다)"}
""" if part_num > 1 else ""

        # ★ 파트 1(기)일 때 특별한 대사 강제 지침
        first_part_dialogue_rule = ""
        if part_num == 1:
            first_part_dialogue_rule = """
🚨🚨🚨 [파트 1 특별 규칙 - 1분 내 대사 필수!] 🚨🚨🚨
★ opening 씬: 배경 설명 후 바로 대사! (1회 이상)
★ hook 씬: 반드시 대사 2회 이상!!! (긴장감 있는 대화)
★ 영상 시작 후 1분(약 420자) 이내에 첫 대사가 등장해야 함!

예시 (opening에서 대사 시작 - 성별 표시!):
"아침 해가 기와지붕을 비추고 있었다. 대문이 열리며 한 사내가 들어섰다.
[DIALOGUE:M]'아버님, 다녀왔습니다.'[/DIALOGUE]
시어머니가 마루에서 내려다보며 대답했다.
[DIALOGUE:F]'오냐, 들어오너라.'[/DIALOGUE]"

★ 대사 없이 배경만 길게 쓰면 실패입니다!!!
"""

        prompt = f"""당신은 한국 야담/전통 이야기 전문 작가입니다.
아래 스토리 아웃라인을 바탕으로 {part_info['name']} 파트의 상세 대본을 작성해주세요.

[이야기 제목]
{outline.get('title', title_block.final_title)}

[전체 시놉시스]
{outline.get('synopsis', '')}

[주인공 정보]
- 이름: {character.get('name', '주인공')}
- 나이: {character.get('age', '중년')}
- 성별: {character.get('gender', '남성')}
- 특징: {character.get('description', '')}
{context}
{first_part_dialogue_rule}
[이번 파트에서 작성할 씬들]
{chr(10).join([f"- {s.get('id')}: {s.get('title')} - {s.get('summary')}" for s in scene_outlines])}

🚨🚨🚨 필수: 각 씬의 나레이션은 반드시 {chars_per_scene}자 이상!!! 🚨🚨🚨

★★★ 대사(DIALOGUE) 규칙 - 절대 무시 금지! ★★★
🚨 대사는 성별 표시 필수!
   - 남자 대사: [DIALOGUE:M]"대사 내용"[/DIALOGUE]
   - 여자 대사: [DIALOGUE:F]"대사 내용"[/DIALOGUE]
🚨 각 씬에 최소 1-2회 대사 필수 삽입!
🚨 opening/hook 씬에는 반드시 대사 2회 이상!
🚨 대사 없이 나레이션만 쓰면 안 됩니다!

좋은 예시 (대사가 자연스럽게 섞인 나레이션 - 성별 표시!):
"장터가 소란스러워지더니, 한 사내가 소리쳤습니다. [DIALOGUE:M]'이봐, 돈 내놔!'[/DIALOGUE] 상인들이 벌벌 떨기 시작했습니다. 그때 노파 한 분이 천천히 다가와 말했습니다. [DIALOGUE:F]'젊은이, 그러면 안 되지.'[/DIALOGUE]"

나쁜 예시 (대사 없음 - 금지!):
"장터가 소란스러워졌습니다. 사내가 행패를 부리고 있었습니다. 상인들이 두려움에 떨었습니다."

[나레이션 작성 규칙 - 묘사 밀도 강화 필수]
1. 배경 묘사 4-5문장 필수 (오감 활용):
   - 시각: 색감, 빛, 그림자 (예: "붉은 노을이 기와지붕을 물들이고")
   - 청각: 소리, 자연음 (예: "귀뚜라미 소리가 처마 밑에서")
   - 후각: 냄새, 향기 (예: "막걸리 익는 구수한 냄새가")
   - 촉각: 질감, 온도 (예: "차가운 밤공기가 목덜미를 스치고")
2. 인물 묘사 상세히:
   - 표정: 눈빛, 입꼬리, 미간 (예: "미간이 찌푸려지며")
   - 손동작: 손가락, 주먹 (예: "주먹을 꽉 쥐자 힘줄이")
   - 내면심리: 생각, 감정, 갈등 (예: "가슴 한구석이 서늘해지며")
3. 의성어/의태어 매 문단 1개 이상 필수:
   - 동작: 휙, 스윽, 펄럭, 뚜벅뚜벅, 사뿐사뿐
   - 소리: 뚜둑, 쿵, 철커덩, 찰랑찰랑, 쨍그랑
   - 감정: 두근두근, 조마조마, 오싹, 아릿아릿
4. 문장 분량: 각 씬 최소 8-10문장
   - 상황 설명 2-3문장
   - 배경 묘사 3-4문장 (오감)
   - 행동/대화 2-3문장
   - 내면 심리 1-2문장
5. 피해야 할 것: 짧고 건조한 묘사, 현대적 표현

[출력 형식 - JSON]
{{
  "scenes": [
    {{
      "scene_id": "opening",
      "title": "장면 제목",
      "narration": "여기에 {chars_per_scene}자 이상의 상세한 나레이션 작성...",
      "image_prompt": "이미지 생성용 영어 프롬프트",
      "duration_sec": 예상 초 (나레이션 길이 / 7.0),
      "camera_motion": "slow_zoom_in"
    }},
    ...
  ]
}}

★ camera_motion: slow_zoom_in, slow_zoom_out, slow_pan_left, slow_pan_right, static 중 선택
★ JSON만 출력
★ ⚠️ 절대 문자열 안에 큰따옴표(") 사용 금지! 작은따옴표(')만 사용
★ 🚨 대사([DIALOGUE]) 없는 씬은 실패로 처리됩니다!
"""

        try:
            # prefill로 JSON 시작 강제
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,  # 파트당 충분한 토큰
                temperature=0.7,
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": "{"}  # prefill: JSON으로 시작
                ]
            )

            # prefill 때문에 응답 앞에 { 붙여줘야 함
            content = "{" + response.content[0].text
            data = self._extract_json_from_response(content)

            if data and "scenes" in data:
                scenes = []
                character_profile = CharacterProfile(
                    name=character.get("name", ""),
                    age=character.get("age", ""),
                    gender=character.get("gender", ""),
                    appearance=character.get("description", "")
                )

                for scene_data in data["scenes"]:
                    scene = Scene(
                        scene_id=scene_data.get("scene_id", "unknown"),
                        title=scene_data.get("title", ""),
                        narration=scene_data.get("narration", ""),
                        image_prompt=scene_data.get("image_prompt", ""),
                        duration_sec=scene_data.get("duration_sec", 60),
                        camera_motion=scene_data.get("camera_motion", "slow_zoom_in")
                    )
                    scenes.append(scene)

                return scenes, character_profile
            else:
                print(f"[ScriptEngine] 파트 {part_num} JSON 파싱 실패")
                print(f"[ScriptEngine] 응답 앞 200자: {content[:200]}")
                return [], None

        except Exception as e:
            print(f"[ScriptEngine] 파트 {part_num} 생성 오류: {e}")
            return [], None

    def _summarize_scenes(self, scenes: list) -> str:
        """씬들을 요약하여 다음 파트에 맥락 전달"""
        summaries = []
        for scene in scenes:
            # 나레이션에서 첫 2문장 추출
            narration = scene.narration
            sentences = narration.split(".")[:2]
            summary = ".".join(sentences).strip()
            if summary:
                summaries.append(f"- {scene.title}: {summary}...")
        return "\n".join(summaries)

    def _create_fallback_scenes_for_part(self, outline: dict, part_info: dict,
                                         title_block) -> list:
        """
        파트별 대본 생성 실패 시 폴백 씬 생성
        outline의 scene summary를 확장하여 기본 나레이션 생성
        """
        scene_ids = part_info["scenes"]
        target_chars = part_info["chars"]
        chars_per_scene = target_chars // len(scene_ids)

        # outline에서 해당 씬들의 정보 추출
        scene_map = {s.get("id"): s for s in outline.get("scenes", [])}
        character = outline.get("character", {})
        char_name = character.get("name", "주인공")

        fallback_scenes = []

        for scene_id in scene_ids:
            scene_info = scene_map.get(scene_id, {})
            scene_title = scene_info.get("title", scene_id)
            scene_summary = scene_info.get("summary", "이야기가 전개됩니다.")

            # summary를 확장하여 나레이션 생성 (목표 글자수에 맞게)
            # 기본 문장 템플릿을 반복하여 목표 글자수 달성
            base_narration = f"{scene_title}. {scene_summary} "
            expanded_narration = self._expand_narration(
                base=base_narration,
                char_name=char_name,
                target_chars=chars_per_scene,
                scene_title=scene_title
            )

            scene = Scene(
                scene_id=scene_id,
                title=scene_title,
                narration=expanded_narration,
                image_prompt=f"Korean traditional story scene, {scene_title}, {char_name}, dramatic lighting, manhwa style illustration",
                duration_sec=len(expanded_narration) // 7,  # Gemini TTS 기준
                camera_motion="slow_zoom_in"
            )
            fallback_scenes.append(scene)

        return fallback_scenes

    def _expand_narration(self, base: str, char_name: str, target_chars: int, scene_title: str) -> str:
        """기본 나레이션을 목표 글자수까지 확장"""
        # 확장용 문장 템플릿
        expansion_templates = [
            f"{char_name}의 눈빛에는 깊은 생각이 담겨 있었다.",
            "그 순간, 주변의 공기가 묘하게 변했다.",
            "바람이 불어와 나뭇잎들이 흩날렸다.",
            f"{char_name}은 잠시 멈춰 서서 주위를 둘러보았다.",
            "멀리서 새 소리가 들려왔다.",
            "햇살이 따스하게 내리쬐고 있었다.",
            f"이 모든 것이 {char_name}에게는 특별한 의미로 다가왔다.",
            "시간이 천천히 흘러가는 듯했다.",
            "마음 한켠에 알 수 없는 감정이 일었다.",
            f"{char_name}은 깊은 한숨을 내쉬었다.",
            "어디선가 익숙한 향기가 느껴졌다.",
            "그의 발걸음은 점점 빨라졌다.",
            "구름 사이로 햇빛이 비쳐 내려왔다.",
            f"{char_name}의 마음속에는 결심이 굳어지고 있었다.",
            "저 멀리 산등성이가 희미하게 보였다.",
        ]

        narration = base
        template_idx = 0

        while len(narration) < target_chars and template_idx < len(expansion_templates) * 3:
            template = expansion_templates[template_idx % len(expansion_templates)]
            narration += " " + template
            template_idx += 1

        return narration.strip()
