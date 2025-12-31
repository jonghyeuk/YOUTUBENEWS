"""
프롬프트 컴파일러 - 캐릭터/세계관/카메라/세트를 고정 슬롯으로 조합
일관된 이미지 생성을 위해 프롬프트 순서와 형식을 고정
"""

from typing import Dict, Any, Optional


# ═══════════════════════════════════════════════════════════════
# 한국/동양 스타일 강제 프리셋
# ═══════════════════════════════════════════════════════════════

KOREAN_STYLE_PREFIX = """Korean traditional minhwa folk art style,
East Asian aesthetic, warm earth tones, soft ink wash texture."""

KOREAN_CHARACTER_ENFORCE = """IMPORTANT: All human characters must be Korean/East Asian ethnicity.
Korean elderly man with traditional features, weathered kind face,
wearing traditional Korean hanbok or simple traditional clothes.
NO western features, NO caucasian faces."""

KOREAN_CONSTRAINTS = """Keep the same Korean elderly character identity across all scenes.
Traditional Korean art style, minhwa folk painting aesthetic.
East Asian faces only. No text, no watermark, no signature."""


def compile_hybrid_prompt(
    original_prompt: str,
    character_type: str = "old_grandfather",
    world_style: str = "korean_minhwa",
    camera: str = "MEDIUM"
) -> str:
    """
    기존 프롬프트에 캐릭터/스타일 프리셋을 강제 적용 (하이브리드 방식)

    작가가 만든 창의적 씬 설명은 유지하되,
    캐릭터와 스타일은 프리셋으로 고정하여 일관성 확보

    Args:
        original_prompt: 작가가 생성한 원본 이미지 프롬프트
        character_type: 캐릭터 타입 (old_grandfather, young_scholar 등)
        world_style: 세계관 스타일 (korean_minhwa, buddha_era 등)
        camera: 카메라 샷 (WIDE, MEDIUM, CLOSE)

    Returns:
        프리셋이 적용된 컴파일된 프롬프트
    """

    # 캐릭터 프리셋
    character_presets = {
        "old_grandfather": "Korean elderly grandfather, age 70, East Asian features, weathered kind face, traditional Korean hanbok, gray hair",
        "old_monk": "Korean elderly Buddhist monk, age 68, shaved head, East Asian features, serene wrinkled face, dark brown traditional robe",
        "young_monk": "Young Korean Buddhist monk, age 22, shaved head, East Asian features, calm serene face, saffron robe",
        "young_scholar": "Young Korean scholar, age 25, black topknot hair, East Asian features, traditional white hanbok, thoughtful expression",
        "village_woman": "Korean village woman, age 40, East Asian features, braided hair, simple traditional hanbok, kind weathered face",
    }

    # 세계관 프리셋
    world_presets = {
        "korean_minhwa": "Korean minhwa folk painting style, traditional Korean art, warm earth tones, soft brushwork",
        "buddha_era_night": "Ancient Buddhist art style, lantern night lighting, ink muted colors, mystical atmosphere",
        "buddha_era_day": "Ancient East Asian art style, clear daylight, warm natural colors, peaceful",
        "joseon_traditional": "Joseon dynasty Korean art style, traditional aesthetics, muted elegant colors",
    }

    # 카메라 프리셋
    camera_presets = {
        "WIDE": "wide shot composition, full scene visible",
        "MEDIUM": "medium shot composition, upper body focus",
        "CLOSE": "close-up shot, emotional detail focus",
    }

    # 프리셋 가져오기
    char_desc = character_presets.get(character_type, character_presets["old_grandfather"])
    world_desc = world_presets.get(world_style, world_presets["korean_minhwa"])
    cam_desc = camera_presets.get(camera, camera_presets["MEDIUM"])

    # 프롬프트 조합 (순서 중요!)
    # 1. 스타일 먼저 (전체 톤 설정)
    # 2. 캐릭터 강제 (동양인 고정)
    # 3. 원본 씬 설명 (창의적 내용 유지)
    # 4. 카메라
    # 5. 제약 조건 (마지막)

    compiled = f"""{world_desc}.
Main character: {char_desc}.
{cam_desc}.
Scene description: {original_prompt}
{KOREAN_CONSTRAINTS}"""

    return compiled.strip()


def compile_prompt(
    scene_action: str,
    character: Dict[str, Any],
    world: Dict[str, Any],
    camera: Dict[str, Any],
    place: str,
    place_props: list = None
) -> str:
    """
    씬 정보를 고정 슬롯 프롬프트로 컴파일

    핵심: 프롬프트 순서/표현을 절대 바꾸지 않음 (흔들림 감소)
    순서: 스타일 → 캐릭터 → 장소 → 카메라 → 씬액션 → 제약조건

    Args:
        scene_action: 씬 설명 (2문장 이내)
        character: 캐릭터 프리셋 dict
        world: 세계관 프리셋 dict
        camera: 카메라 프리셋 dict
        place: 세트장 이름
        place_props: 세트장 소품 리스트

    Returns:
        컴파일된 프롬프트 문자열
    """

    parts = []

    # 1) 스타일/세계관 (가장 먼저 - 전체 톤 설정)
    style_part = f"Style: {world.get('style', 'korean_minhwa_folk_painting')}"
    style_part += f", lighting: {world.get('lighting', 'soft')}"
    style_part += f", color tone: {world.get('color', 'warm_earth_tones')}"
    if world.get('fog'):
        style_part += f", fog: {world.get('fog')}"
    parts.append(style_part + ".")

    # 2) 메인 캐릭터 (고정 속성 + 동양인 강제)
    char_part = f"Main character: {character.get('name', 'Korean elderly man')}"
    char_part += ", East Asian/Korean ethnicity"
    if character.get('age'):
        char_part += f", age {character.get('age')}"
    if character.get('gender'):
        char_part += f", {character.get('gender')}"
    if character.get('hair'):
        char_part += f", hair: {character.get('hair')}"
    if character.get('clothes'):
        char_part += f", wearing {character.get('clothes')}"
    if character.get('face'):
        char_part += f", face: {character.get('face')}"
    parts.append(char_part + ".")

    # 3) 장소/세트
    location_part = f"Location: {place.replace('_', ' ')}"
    if place_props:
        location_part += f", with {', '.join(place_props[:3])}"
    parts.append(location_part + ".")

    # 4) 카메라/샷
    cam_part = f"Camera: {camera.get('shot', 'medium shot')}"
    if camera.get('lens'):
        cam_part += f", {camera.get('lens')} lens"
    if camera.get('angle'):
        cam_part += f", {camera.get('angle')} angle"
    parts.append(cam_part + ".")

    # 5) 씬 액션 (변화하는 부분)
    parts.append(f"Scene: {scene_action}")

    # 6) 제약 조건 (항상 마지막 - 동양인 강제)
    parts.append(KOREAN_CONSTRAINTS)

    return " ".join(parts)


def compile_prompt_simple(
    scene_action: str,
    style: str = "korean_minhwa",
    character: str = "old_grandfather",
    camera: str = "MEDIUM",
    place: str = "mountain_village"
) -> str:
    """
    간단한 문자열 파라미터로 프롬프트 컴파일
    (프리셋 로드 없이 기본값 사용)
    """

    # 기본 스타일 매핑
    style_map = {
        "korean_minhwa": "Korean minhwa folk painting style, traditional Korean art, warm earth tones",
        "buddha_era_night": "ancient buddhist illustration, lantern night lighting, ink muted colors",
        "buddha_era_day": "ancient East Asian realism, clear daylight, warm natural colors",
        "zen_minimalist": "zen ink wash style, monochrome, minimal",
    }

    # 기본 캐릭터 매핑 (동양인 강제)
    char_map = {
        "old_grandfather": "Korean elderly grandfather, East Asian features, weathered kind face, traditional hanbok",
        "old_monk": "Korean elderly Buddhist monk, East Asian features, shaved head, dark brown robe, wise wrinkled face",
        "young_monk": "young Korean Buddhist monk, East Asian features, shaved head, saffron robe, calm serene face",
        "young_scholar": "young Korean scholar, East Asian features, black topknot, white hanbok, thoughtful expression",
    }

    # 기본 카메라 매핑
    cam_map = {
        "WIDE": "wide shot, 24mm lens, full scene",
        "MEDIUM": "medium shot, 50mm lens, upper body visible",
        "CLOSE": "close up shot, 85mm lens, face detail",
    }

    style_desc = style_map.get(style, style_map["korean_minhwa"])
    char_desc = char_map.get(character, char_map["old_grandfather"])
    cam_desc = cam_map.get(camera, cam_map["MEDIUM"])

    prompt = f"{style_desc}. Character: {char_desc}. Location: {place.replace('_', ' ')}. "
    prompt += f"Camera: {cam_desc}. Scene: {scene_action}. "
    prompt += KOREAN_CONSTRAINTS

    return prompt

