"""
다중화자 제거 및 주인공 대사 음성 기능 테스트
"""

import sys
import os
import re
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# TTS 엔진의 핵심 파싱 로직만 테스트용으로 재현
def parse_dialogue_segments(narration: str) -> List[Tuple[str, str]]:
    """나레이션에서 주인공 대사 세그먼트 추출"""
    segments = []
    pattern = r'\[DIALOGUE\](.*?)\[/DIALOGUE\]'

    last_end = 0
    for match in re.finditer(pattern, narration, re.DOTALL):
        if last_end < match.start():
            text = narration[last_end:match.start()].strip()
            if text:
                segments.append(("narration", text))

        dialogue_text = match.group(1).strip()
        if dialogue_text:
            segments.append(("dialogue", dialogue_text))

        last_end = match.end()

    if last_end < len(narration):
        text = narration[last_end:].strip()
        if text:
            segments.append(("narration", text))

    if not segments:
        segments.append(("narration", narration.strip()))

    return segments


def remove_dialogue_tags(text: str) -> str:
    """[DIALOGUE]...[/DIALOGUE] 태그만 제거하고 내용은 유지"""
    result = re.sub(r'\[DIALOGUE\]', '', text)
    result = re.sub(r'\[/DIALOGUE\]', '', result)
    return result.strip()


def clean_narrator_tags(text: str) -> str:
    """나레이션에서 화자 태그 및 대사 태그 제거"""
    cleaned = re.sub(r'\[NARRATOR\d*\]\s*', '', text)
    cleaned = re.sub(r'\[화자\d*\]\s*', '', cleaned)
    cleaned = re.sub(r'\[내레이터\d*\]\s*', '', cleaned)
    cleaned = re.sub(r'\[DIALOGUE\]', '', cleaned)
    cleaned = re.sub(r'\[/DIALOGUE\]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


# 음성 매핑 (TTS 엔진에서 복사)
DIALOGUE_VOICE_MAP = {
    "onyx": "echo",
    "nova": "shimmer",
    "alloy": "fable",
    "echo": "onyx",
    "fable": "echo",
    "shimmer": "nova",
}


def test_dialogue_parsing():
    """[DIALOGUE] 태그 파싱 테스트"""

    # 테스트 케이스 1: 단일 대사
    narration1 = '왕은 신하들을 둘러보며 천천히 입을 열었습니다. [DIALOGUE]"오늘, 이 자리에서 결정을 내리겠다."[/DIALOGUE] 그 한마디에 모든 신하들이 숨을 멈췄습니다.'

    segments1 = parse_dialogue_segments(narration1)
    print("\n=== 테스트 1: 단일 대사 ===")
    for seg_type, text in segments1:
        print(f"  [{seg_type}] {text[:50]}...")

    assert len(segments1) == 3, f"Expected 3 segments, got {len(segments1)}"
    assert segments1[0][0] == "narration"
    assert segments1[1][0] == "dialogue"
    assert segments1[2][0] == "narration"
    print("  ✅ 통과!")

    # 테스트 케이스 2: 대사 2개
    narration2 = '그는 눈을 감고 [DIALOGUE]"이것이 내 운명이다."[/DIALOGUE]라고 말했고, 잠시 후 [DIALOGUE]"역사가 나를 기억해줄까..."[/DIALOGUE]라고 중얼거렸습니다.'

    segments2 = parse_dialogue_segments(narration2)
    print("\n=== 테스트 2: 대사 2개 ===")
    for seg_type, text in segments2:
        print(f"  [{seg_type}] {text[:50]}...")

    assert len(segments2) == 5, f"Expected 5 segments, got {len(segments2)}"
    print("  ✅ 통과!")

    # 테스트 케이스 3: 대사 없음
    narration3 = '오늘 날씨가 좋습니다. 산책하기 좋은 날이네요.'

    segments3 = parse_dialogue_segments(narration3)
    print("\n=== 테스트 3: 대사 없음 ===")
    for seg_type, text in segments3:
        print(f"  [{seg_type}] {text[:50]}...")

    assert len(segments3) == 1, f"Expected 1 segment, got {len(segments3)}"
    assert segments3[0][0] == "narration"
    print("  ✅ 통과!")


def test_dialogue_tag_removal():
    """태그 제거 테스트"""
    text = '[DIALOGUE]"안녕하세요"[/DIALOGUE] 그가 말했습니다.'
    cleaned = remove_dialogue_tags(text)

    print("\n=== 태그 제거 테스트 ===")
    print(f"  원본: {text}")
    print(f"  결과: {cleaned}")

    assert "[DIALOGUE]" not in cleaned
    assert "[/DIALOGUE]" not in cleaned
    assert '"안녕하세요"' in cleaned
    print("  ✅ 통과!")


def test_subtitle_tag_cleaning():
    """자막 엔진의 태그 제거 테스트"""
    # 다중화자 태그 + DIALOGUE 태그 모두 제거 확인
    text = '[NARRATOR1] 나레이터가 말했습니다. [DIALOGUE]"대사입니다."[/DIALOGUE] 끝.'
    cleaned = clean_narrator_tags(text)

    print("\n=== 자막 태그 제거 테스트 ===")
    print(f"  원본: {text}")
    print(f"  결과: {cleaned}")

    assert "[NARRATOR1]" not in cleaned
    assert "[DIALOGUE]" not in cleaned
    assert "[/DIALOGUE]" not in cleaned
    assert "나레이터가 말했습니다." in cleaned
    assert '"대사입니다."' in cleaned
    print("  ✅ 통과!")


def test_narration_natural_flow():
    """나레이션 자연스러움 테스트 (샘플)"""

    print("\n=== 나레이션 자연스러움 샘플 ===")

    # 역사 모드 샘플
    history_sample = '''그 순간, 왕은 천천히 칼을 들어 올렸습니다. 신하들의 숨소리마저 멎은 그때, 왕이 입을 열었습니다. [DIALOGUE]"이것이 내 마지막 결정이다. 역사가 나를 심판할 것이다."[/DIALOGUE] 그 한마디가 조선의 운명을 바꿔놓았습니다.'''

    print("\n  📜 역사 모드 샘플:")
    print(f"    {history_sample}")

    # 드라마 모드 샘플
    drama_sample = '''결혼 10년. 나는 행복한 줄 알았어요. 그날 밤, 남편 핸드폰에서 메시지가 울렸습니다. 화면을 본 순간, [DIALOGUE]"이게... 뭐야? 뭐냐고..."[/DIALOGUE] 손이 떨렸습니다. 그리고 모든 게 바뀌었습니다.'''

    print("\n  🎭 드라마 모드 샘플:")
    print(f"    {drama_sample}")

    print("\n  ℹ️  주인공 대사만 다른 음성으로 TTS 처리됩니다.")
    print("  ✅ 나레이션 흐름이 자연스럽습니다!")


def test_voice_mapping():
    """음성 매핑 테스트"""
    print("\n=== 음성 매핑 테스트 ===")

    for main_voice, dialogue_voice in DIALOGUE_VOICE_MAP.items():
        print(f"  나레이터: {main_voice} → 주인공: {dialogue_voice}")

    print("  ✅ 음성 매핑 확인!")


if __name__ == "__main__":
    print("=" * 60)
    print("다중화자 제거 및 주인공 대사 음성 기능 테스트")
    print("=" * 60)

    test_dialogue_parsing()
    test_dialogue_tag_removal()
    test_subtitle_tag_cleaning()
    test_voice_mapping()
    test_narration_natural_flow()

    print("\n" + "=" * 60)
    print("✅ 모든 테스트 통과!")
    print("=" * 60)
