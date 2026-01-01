"""
프롬프트 컴파일러 - 캐릭터/세계관/카메라/세트를 고정 슬롯으로 조합
일관된 이미지 생성을 위해 프롬프트 순서와 형식을 고정

지원 스타일:
- 한국불교: 민화풍, 조선시대
- 중국불교: 수묵화풍, 당송명청
- 인도불교: 간다라 미술, 붓다 시대
"""

from typing import Dict, Any, Optional


# ═══════════════════════════════════════════════════════════════
# 지역별 스타일 프리셋
# ═══════════════════════════════════════════════════════════════

# --- 한국불교 ---
KOREAN_CONSTRAINTS = """Keep the same Korean elderly character identity across all scenes.
Traditional Korean art style, minhwa folk painting aesthetic.
East Asian faces only. No text, no watermark, no signature."""

# --- 중국불교 ---
CHINESE_CONSTRAINTS = """Keep the same Chinese elderly character identity across all scenes.
Traditional Chinese ink wash painting style, shanshui landscape aesthetic.
East Asian (Chinese) faces only. No text, no watermark, no signature."""

# --- 인도불교 ---
INDIAN_CONSTRAINTS = """Keep the same Indian/South Asian character identity across all scenes.
Ancient Gandhara Buddhist art style, warm golden tones.
South Asian (Indian) faces only. No text, no watermark, no signature."""

# 지역별 제약조건 매핑
REGIONAL_CONSTRAINTS = {
    "korea": KOREAN_CONSTRAINTS,
    "korean_minhwa": KOREAN_CONSTRAINTS,
    "한국불교": KOREAN_CONSTRAINTS,
    "china": CHINESE_CONSTRAINTS,
    "chinese_ink": CHINESE_CONSTRAINTS,
    "중국불교": CHINESE_CONSTRAINTS,
    "india": INDIAN_CONSTRAINTS,
    "indian_gandhara": INDIAN_CONSTRAINTS,
    "인도불교": INDIAN_CONSTRAINTS,
}


def compile_hybrid_prompt(
    original_prompt: str,
    character_type: str = "old_grandfather",
    world_style: str = "korean_minhwa",
    camera: str = "MEDIUM",
    region: str = "korea"
) -> str:
    """
    기존 프롬프트에 캐릭터/스타일 프리셋을 강제 적용 (하이브리드 방식)

    작가가 만든 창의적 씬 설명은 유지하되,
    캐릭터와 스타일은 프리셋으로 고정하여 일관성 확보

    Args:
        original_prompt: 작가가 생성한 원본 이미지 프롬프트
        character_type: 캐릭터 타입 (old_grandfather, old_monk, 등)
        world_style: 세계관 스타일 (korean_minhwa, chinese_ink, indian_gandhara 등)
        camera: 카메라 샷 (WIDE, MEDIUM, CLOSE)
        region: 지역 (korea, china, india)

    Returns:
        프리셋이 적용된 컴파일된 프롬프트
    """

    # 지역별 캐릭터 프리셋
    character_presets = {
        # 한국
        "korea": {
            "old_grandfather": "Korean elderly grandfather, age 70, East Asian features, weathered kind face, traditional Korean hanbok, gray hair in topknot",
            "old_monk": "Korean elderly Buddhist monk, age 68, shaved head, East Asian features, serene wrinkled face, dark gray traditional robe",
            "young_monk": "Young Korean Buddhist monk, age 22, shaved head, East Asian features, calm serene face, gray robe",
            "young_scholar": "Young Korean scholar, age 25, black topknot hair, East Asian features, traditional white hanbok, thoughtful expression",
            "village_woman": "Korean village woman, age 45, East Asian features, braided hair, simple traditional hanbok, kind weathered face",
        },
        # 중국
        "china": {
            "old_grandfather": "Chinese elderly grandfather, age 72, Han Chinese features, long white beard, traditional changshan robe, wise contemplative expression",
            "old_monk": "Chinese elderly Buddhist master, age 70, shaved head, Han Chinese features, long white beard, saffron and burgundy kasaya robe",
            "young_monk": "Young Chinese Buddhist monk, age 20, shaved head, Han Chinese features, orange-yellow kasaya, peaceful expression",
            "young_scholar": "Young Chinese scholar, age 24, Han Chinese features, black hair in traditional bun, blue scholar robe, holding scroll",
            "village_woman": "Chinese village woman, age 40, Han Chinese features, hair in traditional bun, simple hanfu dress, gentle expression",
        },
        # 인도
        "india": {
            "old_grandfather": "Indian elderly man, age 70, South Asian features, brown skin, white beard, simple white dhoti, wise weathered face",
            "old_monk": "Indian elderly Buddhist bhikkhu, age 68, South Asian features, brown skin, shaved head, saffron robes, serene expression",
            "young_monk": "Young Indian Buddhist monk, age 22, South Asian features, brown skin, shaved head, saffron robes, calm demeanor",
            "buddha": "The Buddha (Siddhartha Gautama), South Asian features, golden-brown skin, ushnisha (crown bump), serene compassionate smile, saffron robes",
            "village_woman": "Indian village woman, age 35, South Asian features, brown skin, traditional sari, bindi, kind expression",
        },
    }

    # 지역별 세계관 프리셋
    world_presets = {
        # 한국
        "korea": {
            "korean_minhwa": "Korean minhwa folk painting style, traditional Korean art, warm earth tones, soft brushwork, dancheong colors",
            "joseon_traditional": "Joseon dynasty Korean art style, traditional aesthetics, muted elegant colors, hanok architecture",
            "mountain_temple": "Korean mountain temple (sansa) setting, pine trees, traditional eaves, peaceful atmosphere",
        },
        # 중국
        "china": {
            "chinese_ink": "Traditional Chinese ink wash painting (shuimo hua), shanshui style, misty mountains, flowing brushwork",
            "tang_dynasty": "Tang dynasty art style, rich golden and vermillion colors, ornate Buddhist temple architecture",
            "zen_garden": "Chinese Zen garden setting, bamboo groves, moon gate, lotus pond, tranquil atmosphere",
        },
        # 인도
        "india": {
            "indian_gandhara": "Gandhara Buddhist art style, Greco-Buddhist influences, warm golden and terracotta tones, intricate carvings",
            "buddha_era": "Ancient India Buddha era setting, sal trees, simple mud huts, Ganges river, warm sunset colors",
            "ajanta_style": "Ajanta cave painting style, rich earth pigments, flowing lines, spiritual atmosphere",
        },
    }

    # 카메라 프리셋
    camera_presets = {
        "WIDE": "wide shot composition, full scene visible, environmental context",
        "MEDIUM": "medium shot composition, upper body focus, character interaction",
        "CLOSE": "close-up shot, emotional detail focus, intimate connection",
    }

    # 지역 정규화
    region_map = {
        "한국불교": "korea", "korean_minhwa": "korea", "korea": "korea",
        "중국불교": "china", "chinese_ink": "china", "china": "china",
        "인도불교": "india", "indian_gandhara": "india", "india": "india",
    }
    normalized_region = region_map.get(region, region_map.get(world_style, "korea"))

    # 프리셋 가져오기
    region_chars = character_presets.get(normalized_region, character_presets["korea"])
    region_worlds = world_presets.get(normalized_region, world_presets["korea"])

    char_desc = region_chars.get(character_type, list(region_chars.values())[0])

    # world_style에서 지역 접두사 제거하고 매칭
    style_key = world_style.replace(f"{normalized_region}_", "")
    world_desc = region_worlds.get(world_style, region_worlds.get(style_key, list(region_worlds.values())[0]))

    cam_desc = camera_presets.get(camera, camera_presets["MEDIUM"])

    # 제약 조건
    constraints = REGIONAL_CONSTRAINTS.get(normalized_region, KOREAN_CONSTRAINTS)

    # 프롬프트 조합 (순서 중요!)
    compiled = f"""{world_desc}.
Main character: {char_desc}.
{cam_desc}.
Scene description: {original_prompt}
{constraints}"""

    return compiled.strip()


def compile_prompt(
    scene_action: str,
    character: Dict[str, Any],
    world: Dict[str, Any],
    camera: Dict[str, Any],
    place: str,
    place_props: list = None,
    region: str = "korea"
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
        region: 지역 (korea, china, india)

    Returns:
        컴파일된 프롬프트 문자열
    """

    # 지역별 민족 설정
    ethnicity_map = {
        "korea": "East Asian/Korean ethnicity",
        "china": "Han Chinese ethnicity",
        "india": "South Asian/Indian ethnicity, brown skin",
    }
    ethnicity = ethnicity_map.get(region, ethnicity_map["korea"])

    parts = []

    # 1) 스타일/세계관 (가장 먼저 - 전체 톤 설정)
    style_part = f"Style: {world.get('style', 'traditional_art')}"
    style_part += f", lighting: {world.get('lighting', 'soft')}"
    style_part += f", color tone: {world.get('color', 'warm_earth_tones')}"
    if world.get('fog'):
        style_part += f", fog: {world.get('fog')}"
    parts.append(style_part + ".")

    # 2) 메인 캐릭터 (고정 속성 + 민족 강제)
    char_part = f"Main character: {character.get('name', 'elderly man')}"
    char_part += f", {ethnicity}"
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
    constraints = REGIONAL_CONSTRAINTS.get(region, KOREAN_CONSTRAINTS)
    parts.append(constraints)

    return " ".join(parts)


def compile_prompt_simple(
    scene_action: str,
    style: str = "korean_minhwa",
    character: str = "old_grandfather",
    camera: str = "MEDIUM",
    place: str = "mountain_village",
    region: str = "korea"
) -> str:
    """
    간단한 문자열 파라미터로 프롬프트 컴파일
    (프리셋 로드 없이 기본값 사용)

    Args:
        scene_action: 씬 설명
        style: 스타일 키
        character: 캐릭터 키
        camera: 카메라 샷
        place: 장소
        region: 지역 (korea, china, india)
    """

    # 지역별 스타일 매핑
    style_maps = {
        "korea": {
            "korean_minhwa": "Korean minhwa folk painting style, traditional Korean art, warm earth tones, dancheong colors",
            "joseon_traditional": "Joseon dynasty Korean art style, traditional aesthetics, muted elegant colors",
            "mountain_temple": "Korean mountain temple setting, traditional architecture, pine trees",
        },
        "china": {
            "chinese_ink": "Chinese ink wash painting (shuimo hua), shanshui style, misty mountains, flowing brushwork",
            "tang_dynasty": "Tang dynasty art style, rich golden and vermillion colors, ornate architecture",
            "zen_garden": "Chinese Zen garden, bamboo groves, lotus pond, tranquil atmosphere",
        },
        "india": {
            "indian_gandhara": "Gandhara Buddhist art style, Greco-Buddhist, warm golden and terracotta tones",
            "buddha_era": "Ancient India Buddha era, sal trees, Ganges river, warm sunset colors",
            "ajanta_style": "Ajanta cave painting style, rich earth pigments, spiritual atmosphere",
        },
    }

    # 지역별 캐릭터 매핑
    char_maps = {
        "korea": {
            "old_grandfather": "Korean elderly grandfather, East Asian features, weathered kind face, traditional hanbok",
            "old_monk": "Korean elderly Buddhist monk, East Asian features, shaved head, dark gray robe",
            "young_monk": "Young Korean Buddhist monk, East Asian features, shaved head, gray robe",
            "young_scholar": "Young Korean scholar, East Asian features, black topknot, white hanbok",
        },
        "china": {
            "old_grandfather": "Chinese elderly grandfather, Han Chinese features, long white beard, traditional changshan",
            "old_monk": "Chinese elderly Buddhist master, Han Chinese features, shaved head, saffron kasaya",
            "young_monk": "Young Chinese Buddhist monk, Han Chinese features, shaved head, orange kasaya",
            "young_scholar": "Young Chinese scholar, Han Chinese features, traditional bun, blue scholar robe",
        },
        "india": {
            "old_grandfather": "Indian elderly man, South Asian features, brown skin, white beard, simple dhoti",
            "old_monk": "Indian elderly Buddhist bhikkhu, South Asian features, brown skin, saffron robes",
            "young_monk": "Young Indian Buddhist monk, South Asian features, brown skin, saffron robes",
            "buddha": "The Buddha, South Asian features, golden-brown skin, ushnisha, saffron robes",
        },
    }

    # 카메라 매핑
    cam_map = {
        "WIDE": "wide shot, 24mm lens, full scene",
        "MEDIUM": "medium shot, 50mm lens, upper body visible",
        "CLOSE": "close up shot, 85mm lens, face detail",
    }

    # 지역 정규화
    region_norm = region.lower()
    if "한국" in region or "korea" in region:
        region_norm = "korea"
    elif "중국" in region or "china" in region:
        region_norm = "china"
    elif "인도" in region or "india" in region:
        region_norm = "india"

    style_map = style_maps.get(region_norm, style_maps["korea"])
    char_map = char_maps.get(region_norm, char_maps["korea"])

    style_desc = style_map.get(style, list(style_map.values())[0])
    char_desc = char_map.get(character, list(char_map.values())[0])
    cam_desc = cam_map.get(camera, cam_map["MEDIUM"])

    constraints = REGIONAL_CONSTRAINTS.get(region_norm, KOREAN_CONSTRAINTS)

    prompt = f"{style_desc}. Character: {char_desc}. Location: {place.replace('_', ' ')}. "
    prompt += f"Camera: {cam_desc}. Scene: {scene_action}. "
    prompt += constraints

    return prompt


def get_available_regions() -> Dict[str, str]:
    """사용 가능한 지역 목록"""
    return {
        "korea": "한국불교 (민화풍, 조선시대)",
        "china": "중국불교 (수묵화풍, 당송명청)",
        "india": "인도불교 (간다라 미술, 붓다 시대)",
    }
