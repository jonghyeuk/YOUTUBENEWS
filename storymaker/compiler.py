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

# --- 한국불교 (Classical Korean Ink-Wash) ---
KOREAN_CONSTRAINTS = """Keep the same Korean elderly character identity across all scenes.
Classical Korean ink-wash narrative painting style, Joseon dynasty landscape aesthetic.
Soft mineral colors, wide negative space, gentle brush texture, hand-painted feeling.
East Asian (Korean) faces only. No anime, no modern illustration, no bright digital colors.
No text, no watermark, no signature."""

# --- 중국불교 (Buddhist Icon Narrative) ---
CHINESE_CONSTRAINTS = """Buddhist icon narrative painting style. Flat symbolic composition.
Traditional temple painting/mural style. Strong primary colors (gold, vermillion, blue).
No perspective realism. Spiritual sacred mood. Storytelling iconography.
East Asian (Chinese) faces only. No anime, no modern illustration.
No text, no watermark, no signature."""

# --- 인도불교 (Narrative Concept Art) ---
INDIAN_CONSTRAINTS = """Narrative concept art illustration style. Soft pencil sketch texture.
Desaturated muted colors, low contrast shading, wide negative space.
Storyboard composition, silhouette-focused characters.
No cute, no anime gloss, no bright colors.
No text, no watermark, no signature."""

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
    region: str = "korea",
    engine: str = "gpt-image-1",
    engine_style_block: str = None
) -> str:
    """
    기존 프롬프트에 캐릭터/스타일 프리셋을 강제 적용 (하이브리드 방식)

    작가가 만든 창의적 씬 설명은 유지하되,
    캐릭터와 스타일은 프리셋으로 고정하여 일관성 확보
    엔진별 최적화된 스타일 블록 적용

    Args:
        original_prompt: 작가가 생성한 원본 이미지 프롬프트
        character_type: 캐릭터 타입 (old_grandfather, old_monk, 등)
        world_style: 세계관 스타일 (korean_minhwa, chinese_ink, indian_gandhara 등)
        camera: 카메라 샷 (WIDE, MEDIUM, CLOSE)
        region: 지역 (korea, china, india)
        engine: 이미지 엔진 (gpt-image-1, dalle, fal, imagen)
        engine_style_block: 엔진별 최적화 스타일 블록 (get_regional_style_block에서 가져옴)

    Returns:
        프리셋이 적용된 컴파일된 프롬프트
    """

    # 지역별 캐릭터 프리셋
    character_presets = {
        # 한국 (Classical Ink-Wash 스타일)
        "korea": {
            "old_grandfather": "Korean elderly grandfather in ink-wash style, age 70, East Asian Korean features, weathered kind face, traditional hanbok, gray topknot, soft brush strokes",
            "old_monk": "Korean elderly Buddhist monk in ink-wash style, age 68, shaved head, East Asian Korean features, serene wrinkled face, gray-brown traditional robe, contemplative pose",
            "young_monk": "Young Korean Buddhist monk in ink-wash style, age 22, shaved head, East Asian Korean features, calm serene face, gray robe, gentle brush texture",
            "young_scholar": "Young Korean scholar in ink-wash style, age 25, black topknot hair, East Asian Korean features, traditional white hanbok, thoughtful expression, soft mineral colors",
            "village_woman": "Korean village woman in ink-wash style, age 45, East Asian Korean features, braided hair, simple traditional hanbok, kind weathered face, soft brush strokes",
        },
        # 중국 (Buddhist Icon Narrative - 도상화/평면적)
        "china": {
            "old_grandfather": "Iconographic elderly Chinese man, flat symbolic style, Han Chinese features, white beard, traditional robe, halo/nimbus optional",
            "old_monk": "Buddhist master icon, flat temple painting style, shaved head, golden kasaya robe with patterns, dharma wheel motif, sacred aura",
            "young_monk": "Young Buddhist monk icon, flat symbolic composition, shaved head, saffron robe, prayer beads, humble posture",
            "bodhisattva": "Bodhisattva icon, flat symbolic style, golden skin, lotus seat, elaborate crown, dharma mudra, radiant halo",
            "buddha": "Buddha icon, flat symbolic composition, golden complexion, ushnisha, meditation mudra, lotus throne, radiant mandorla",
        },
        # 인도 (Narrative Concept Art - 실루엣/스케치 중심)
        "india": {
            "old_grandfather": "Silhouette of elderly Indian man, pencil sketch style, brown skin hint, simple white dhoti, contemplative distant pose",
            "old_monk": "Silhouette of Buddhist bhikkhu, soft pencil sketch, saffron robe color accent, meditative posture, minimal detail",
            "young_monk": "Silhouette of young Buddhist monk, pencil sketch texture, saffron robe hint, peaceful stance, wide negative space",
            "buddha": "Silhouette of the Buddha in meditation, pencil sketch, ushnisha visible, serene profile, minimal detail, narrative concept art",
            "village_woman": "Silhouette of Indian village woman, simple sketch, sari draping hint, gentle posture, wide negative space",
        },
    }

    # 지역별 세계관 프리셋
    world_presets = {
        # 한국 (Classical Ink-Wash 정본 스타일)
        "korea": {
            "classical_inkwash": "Classical Korean ink-wash narrative painting, Joseon dynasty landscape style, soft mineral colors, wide negative space, gentle brush texture, hand-painted feeling",
            "korean_minhwa": "Classical Korean ink-wash style with mineral color wash, traditional Korean aesthetic, soft earth tones, gentle brushwork",
            "joseon_traditional": "Joseon dynasty ink-wash painting style, traditional Korean aesthetics, soft mineral colors, hanok architecture, wide negative space",
            "mountain_temple": "Korean mountain temple (sansa) in ink-wash style, soft brush strokes, pine trees, misty atmosphere, wide negative space",
        },
        # 중국 (Buddhist Icon Narrative - 불교 도상화)
        "china": {
            "buddhist_icon": "Buddhist icon narrative painting, flat symbolic composition, traditional temple painting style, strong primary colors, no perspective realism, spiritual sacred mood",
            "temple_mural": "Traditional Chinese temple mural style, flat symbolic composition, gold and vermillion colors, dharma wheel iconography, sacred atmosphere",
            "dharma_scene": "Buddhist dharma teaching scene, icon narrative style, flat composition, strong primary colors, storytelling iconography",
        },
        # 인도 (Narrative Concept Art 스타일)
        "india": {
            "narrative_concept": "Narrative concept art illustration, soft pencil sketch, desaturated muted colors, low contrast shading, wide negative space, storyboard composition",
            "buddha_era": "Ancient India Buddha era, narrative concept art, soft pencil sketch, sepia tones, wide negative space, silhouette focus",
            "meditation": "Meditative scene, narrative concept art illustration, soft pencil sketch, desaturated colors, wide negative space, contemplative atmosphere",
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

    # 엔진별 프롬프트 구조 최적화
    if engine == "gpt-image-1":
        # GPT-mini: 짧고 단순하게, 스타일 먼저
        if engine_style_block:
            compiled = f"""{engine_style_block}.
{char_desc}. {cam_desc}.
{original_prompt}
{constraints}"""
        else:
            compiled = f"""{world_desc}.
{char_desc}. {cam_desc}.
{original_prompt}
{constraints}"""

    elif engine == "fal":
        # Fal (Flux): 매우 짧게, 핵심만
        if engine_style_block:
            compiled = f"""{engine_style_block}. {char_desc}. {cam_desc}. {original_prompt}"""
        else:
            compiled = f"""{world_desc}. {char_desc}. {cam_desc}. {original_prompt}"""

    elif engine == "imagen":
        # Imagen: 영화적 연출, depth of field 강조
        if engine_style_block:
            compiled = f"""{engine_style_block}.
Main character: {char_desc}.
{cam_desc}, depth of field.
Scene: {original_prompt}
{constraints}"""
        else:
            compiled = f"""{world_desc}.
Main character: {char_desc}.
{cam_desc}, depth of field, cinematic framing.
Scene: {original_prompt}
{constraints}"""

    else:
        # DALL-E 및 기타: 균형잡힌 설명
        if engine_style_block:
            compiled = f"""{engine_style_block}.
Main character: {char_desc}.
{cam_desc}.
Scene description: {original_prompt}
{constraints}"""
        else:
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
            "classical_inkwash": "Classical Korean ink-wash narrative painting, Joseon dynasty landscape style, soft mineral colors, wide negative space, gentle brush texture",
            "korean_minhwa": "Classical Korean ink-wash style with mineral color wash, traditional Korean aesthetic, soft earth tones, gentle brushwork",
            "joseon_traditional": "Joseon dynasty ink-wash painting style, soft mineral colors, hanok architecture, wide negative space",
            "mountain_temple": "Korean mountain temple in ink-wash style, soft brush strokes, pine trees, misty atmosphere",
        },
        "china": {
            "buddhist_icon": "Buddhist icon narrative painting, flat symbolic composition, traditional temple painting, strong primary colors, sacred mood",
            "temple_mural": "Traditional Chinese temple mural style, flat composition, gold and vermillion colors, dharma iconography",
            "dharma_scene": "Buddhist dharma teaching scene, icon narrative style, flat composition, storytelling iconography",
        },
        "india": {
            "narrative_concept": "Narrative concept art illustration, soft pencil sketch, desaturated muted colors, low contrast, wide negative space",
            "buddha_era": "Ancient India Buddha era, narrative concept art, soft pencil sketch, sepia tones, silhouette focus",
            "meditation": "Meditative scene, soft pencil sketch, desaturated colors, wide negative space, contemplative",
        },
    }

    # 지역별 캐릭터 매핑
    char_maps = {
        "korea": {
            "old_grandfather": "Korean elderly grandfather in ink-wash style, East Asian Korean features, weathered kind face, traditional hanbok, soft brush strokes",
            "old_monk": "Korean elderly Buddhist monk in ink-wash style, East Asian Korean features, shaved head, gray-brown robe, gentle brush texture",
            "young_monk": "Young Korean Buddhist monk in ink-wash style, East Asian Korean features, shaved head, gray robe, soft mineral colors",
            "young_scholar": "Young Korean scholar in ink-wash style, East Asian Korean features, black topknot, white hanbok, gentle brush strokes",
        },
        "china": {
            "old_grandfather": "Iconographic elderly Chinese man, flat symbolic style, white beard, traditional robe",
            "old_monk": "Buddhist master icon, flat temple painting style, golden kasaya, dharma motif, sacred aura",
            "young_monk": "Young Buddhist monk icon, flat symbolic composition, saffron robe, prayer beads",
            "buddha": "Buddha icon, flat symbolic, golden complexion, ushnisha, lotus throne, radiant mandorla",
        },
        "india": {
            "old_grandfather": "Silhouette of Indian elderly man, simple sketch, brown skin tone hint, white dhoti, contemplative pose",
            "old_monk": "Silhouette of Buddhist bhikkhu, pencil sketch style, saffron robe hint, meditative posture",
            "young_monk": "Silhouette of young Buddhist monk, simple sketch, saffron robe accent, peaceful stance",
            "buddha": "Silhouette of the Buddha, pencil sketch, meditation pose, ushnisha, minimal detail, serene",
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
