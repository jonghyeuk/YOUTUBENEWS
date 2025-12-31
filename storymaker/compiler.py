"""
프롬프트 컴파일러 - 캐릭터/세계관/카메라/세트를 고정 슬롯으로 조합
일관된 이미지 생성을 위해 프롬프트 순서와 형식을 고정
"""

from typing import Dict, Any, Optional


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
    style_part = f"Style: {world.get('style', 'asian_ink_painting')}"
    style_part += f", lighting: {world.get('lighting', 'soft')}"
    style_part += f", color tone: {world.get('color', 'muted')}"
    if world.get('fog'):
        style_part += f", fog: {world.get('fog')}"
    parts.append(style_part + ".")

    # 2) 메인 캐릭터 (고정 속성)
    char_part = f"Main character: {character.get('name', 'monk')}"
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

    # 6) 제약 조건 (항상 마지막)
    constraints = "Keep the same character identity across all scenes. "
    constraints += "Anime illustration style, clean lines, simple background. "
    constraints += "No text, no watermark, no signature."
    parts.append(constraints)

    return " ".join(parts)


def compile_prompt_simple(
    scene_action: str,
    style: str = "buddha_era_night",
    character: str = "young_monk",
    camera: str = "MEDIUM",
    place: str = "temple_hall"
) -> str:
    """
    간단한 문자열 파라미터로 프롬프트 컴파일
    (프리셋 로드 없이 기본값 사용)
    """

    # 기본 스타일 매핑
    style_map = {
        "buddha_era_night": "ancient buddhist illustration, lantern night lighting, ink muted colors",
        "buddha_era_day": "ancient chinese realism, clear daylight, warm natural colors",
        "joseon_minhwa": "korean minhwa folk painting style, warm earth tones",
        "zen_minimalist": "zen ink wash style, monochrome, minimal",
    }

    # 기본 캐릭터 매핑
    char_map = {
        "young_monk": "young buddhist monk, shaved head, saffron robe, calm serene face",
        "old_monk": "elderly buddhist monk, white stubble, dark brown robe, wise wrinkled face",
        "young_scholar": "young scholar, black topknot, white hanbok, thoughtful expression",
    }

    # 기본 카메라 매핑
    cam_map = {
        "WIDE": "wide shot, 24mm lens, full scene",
        "MEDIUM": "medium shot, 50mm lens, upper body visible",
        "CLOSE": "close up shot, 85mm lens, face detail",
    }

    style_desc = style_map.get(style, style_map["buddha_era_night"])
    char_desc = char_map.get(character, char_map["young_monk"])
    cam_desc = cam_map.get(camera, cam_map["MEDIUM"])

    prompt = f"{style_desc}. Character: {char_desc}. Location: {place.replace('_', ' ')}. "
    prompt += f"Camera: {cam_desc}. Scene: {scene_action}. "
    prompt += "Same character identity, anime illustration, no text."

    return prompt
