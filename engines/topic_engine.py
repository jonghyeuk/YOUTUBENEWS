from dataclasses import dataclass
from typing import List
from models.types import TopicScore, TitleThumbnailResult
import os
import re
from anthropic import Anthropic
# from utils.http_client import HttpClient  # HTTP 유틸 (직접 구현)

# 1) 키워드 기반 카테고리 룰 (5대 장르 + 유아)
# ★ 시니어 대상 유튜브 콘텐츠 - 청중이 시니어일 뿐, 등장인물/주제는 다양
TOPIC_RULES = [
    # ① 감동 실화형 (Emotional Storytelling)
    # 핵심 감정: 따뜻함, 감사, 여운, 공감
    {
        "category": "emotional",
        "keywords": ["감동", "눈물", "헌신", "사랑", "효도", "가족", "부모", "자녀", "희생",
                    "극복", "기적", "실화", "인생역전", "감사", "고마움", "은혜", "봉사",
                    "나눔", "베풂", "위인", "영웅", "용기", "도전", "성공", "꿈",
                    "아버지", "어머니", "할머니", "할아버지", "손자", "형제", "자매"],
        "recommended_duration": 420,
        "template_id": "emotional_story"
    },

    # ② 회상·향수형 (Nostalgic & Retrospective)
    # 핵심 감정: 향수, 그리움, 안정감
    {
        "category": "nostalgic",
        "keywords": ["추억", "옛날", "그시절", "학창시절", "군대", "청춘", "70년대", "80년대", "90년대",
                    "통신수단", "삐삐", "전화기", "교복", "가방", "다방", "음악다방",
                    "레코드", "카세트", "LP", "옛노래", "트로트", "가요", "국민학교",
                    "초등학교", "중학교", "고등학교", "대학", "첫월급", "첫직장",
                    "버스안내양", "새마을호", "비둘기호", "시골", "고향", "어린시절",
                    "라디오", "흑백TV", "컬러TV", "전축", "문방구", "오락실"],
        "recommended_duration": 360,
        "template_id": "nostalgic_story"
    },

    # ③ 교훈·명언형 (Wisdom & Life Philosophy)
    # 핵심 감정: 통찰, 자기 성찰, 격려
    # ★ 역사/위인 주제도 포함 (시대/맥락은 나레이션에서 동적 파악)
    {
        "category": "wisdom",
        "keywords": ["명언", "교훈", "인생", "철학", "지혜", "격언", "속담", "고사성어",
                    "위인", "영웅", "명장", "장군", "왕", "성현", "학자",
                    "역사", "전쟁", "전투", "독립", "혁명",
                    "CEO", "경영자", "리더", "대통령", "연설", "명연설",
                    "인생관", "가치관", "좌우명", "삶의지혜", "깨달음", "성찰",
                    "마음공부", "명상", "수양", "덕목", "인격", "품성"],
        "recommended_duration": 360,
        "template_id": "wisdom_story"
    },

    # ④ 지식·정보형 (Practical Knowledge)
    # 핵심 감정: 신뢰, 실용, 자기계발
    {
        "category": "knowledge",
        "keywords": ["건강", "혈압", "고혈압", "당뇨", "관절", "무릎", "허리", "수면", "불면",
                    "치매", "기억력", "운동", "식단", "영양", "비타민", "약", "병원",
                    "연금", "노후자금", "재테크", "주식", "배당", "부동산", "저축",
                    "스마트폰", "카톡", "유튜브", "인터넷", "컴퓨터", "앱",
                    "요리", "레시피", "생활팁", "살림", "청소", "정리", "수납",
                    "여행", "등산", "취미", "원예", "텃밭", "반려동물"],
        "recommended_duration": 420,
        "template_id": "knowledge_info"
    },

    # ⑤ 명작·음악 해설형 (Classic Review & Music Story)
    # 핵심 감정: 감탄, 감동, 흥미
    {
        "category": "classic",
        "keywords": ["명곡", "클래식", "음악", "노래", "가수", "김광석", "이문세", "조용필",
                    "나훈아", "송창식", "양희은", "김건모", "신승훈", "이승철",
                    "발라드", "포크", "록", "팝송", "올드팝", "비틀즈", "엘비스",
                    "영화", "명작", "고전", "문학", "시", "소설", "수필",
                    "그림", "미술", "화가", "작품", "예술", "전시", "공연",
                    "드라마", "배우", "명장면", "명대사", "OST", "주제가"],
        "recommended_duration": 420,
        "template_id": "classic_review"
    },

    # 유아 카테고리 (기존 유지)
    {
        "category": "kids",
        "keywords": ["동화", "옛날이야기", "토끼", "곰", "다람쥐", "펭귄", "고양이", "강아지",
                    "아기", "꼬마", "요정", "공주", "왕자", "마법", "무지개", "별",
                    "숲속", "바다", "하늘", "구름", "꽃", "나비", "동물친구",
                    "용기", "우정", "친구", "모험", "탐험", "소원",
                    "생일", "선물", "파티", "잠자리", "꿈나라", "자장가",
                    "유치원", "어린이집", "놀이터", "소풍", "캠핑",
                    "뽀로로", "핑크퐁", "코코몽", "타요", "로보카폴리",
                    "공룡", "로봇", "자동차", "비행기", "기차", "배",
                    "사탕", "초콜릿", "아이스크림", "케이크", "쿠키"],
        "recommended_duration": 300,
        "template_id": "kids_story"
    },

    # ⑥ 드라마형 서사 (Drama Storytelling)
    # 핵심 감정: 긴장감, 몰입, 반전, 공감
    # 소재: 가족갈등, 부부문제, 불륜/배신, 직장드라마, 이웃갈등
    {
        "category": "drama",
        "keywords": [
            # 가족 이야기
            "가족갈등", "부모자식", "효도", "유산", "상속", "형제갈등", "시댁", "며느리", "시어머니",
            # 연인·부부 갈등
            "이혼", "황혼이혼", "재혼", "부부싸움", "외도", "바람", "재회", "첫사랑",
            # 불륜·사기·배신
            "불륜", "배신", "사기", "뒤통수", "복수", "비밀", "거짓말",
            # 직장 내 인간관계
            "직장갈등", "상사", "부하", "괴롭힘", "왕따", "승진", "해고", "퇴사", "은퇴",
            # 이웃·사회적 갈등
            "층간소음", "이웃갈등", "아파트", "고독사", "독거노인", "사건", "사연",
            # 드라마 관련 일반
            "충격실화", "실화", "고백", "폭로", "눈물", "분노", "반전", "막장"
        ],
        "recommended_duration": 300,
        "template_id": "drama_story"
    }
]


class TopicScoringEngine:
    """
    - 온라인 API(구글 트렌드/검색, 유튜브 검색 결과 등)를 사용해
      search_volume_score / competition_score를 계산하는 모듈
    - 시니어 관심도(senior_fit_score)는 규칙 기반 + 키워드 매칭으로 계산
    """

    def __init__(self):
        # self.http = HttpClient()
        pass

    def _estimate_search_volume(self, keyword: str) -> float:
        # TODO: Google Trends나 검색 API로 실제 값 조회 → 0~1 정규화
        # 일단은 더미 값
        return 0.7

    def _estimate_competition(self, keyword: str) -> float:
        # TODO: YouTube 검색 결과 수, 상위 채널 규모 등으로 0~1 스케일
        return 0.5

    def _estimate_senior_fit(self, keyword: str) -> float:
        # TODO: 건강/노후/관계/추억 관련 단어 포함 여부 등으로 평가
        kw = keyword
        senior_terms = ["혈압", "고혈압", "무릎", "관절", "연금", "노후", "치매", "기억", "추억", "허리"]
        if any(t in kw for t in senior_terms):
            return 0.9
        return 0.5

    def score_topic(self, keyword: str) -> TopicScore:
        sv = self._estimate_search_volume(keyword)
        comp = self._estimate_competition(keyword)
        sf = self._estimate_senior_fit(keyword)

        final = 0.4 * sv + 0.3 * sf + 0.3 * (1 - comp)

        return TopicScore(
            main_keyword=keyword,
            related_keywords=[],  # TODO: 관련 검색어 수집
            search_volume_score=sv,
            competition_score=comp,
            senior_fit_score=sf,
            final_score=final
        )


class TitleThumbnailEngine:
    """
    - TopicScore를 받아서:
      1) 시니어용 제목 후보 생성 (Claude API 활용)
      2) 썸네일 텍스트
      3) 썸네일 이미지 프롬프트
    """

    def __init__(self):
        self.scoring_engine = TopicScoringEngine()

        # Claude API 초기화
        claude_api_key = os.getenv("ANTHROPIC_API_KEY")
        if claude_api_key:
            self.client = Anthropic(api_key=claude_api_key)
            self.enabled = True
        else:
            self.client = None
            self.enabled = False

    def _detect_category(self, keyword: str) -> str:
        """키워드 기반 카테고리 감지"""
        kw = keyword.lower()

        # 민감한 주제 (부고, 사고, 비극)
        sensitive_words = ["별세", "사망", "타계", "서거", "작고", "사고", "희생", "참사"]
        if any(word in kw for word in sensitive_words):
            return "sensitive"

        # 카테고리별 키워드 매칭
        for rule in TOPIC_RULES:
            if any(k in kw for k in rule["keywords"]):
                return rule["category"]

        return "general"

    def _generate_title_with_claude(self, keyword: str, category: str) -> List[str]:
        """Claude API를 사용하여 제목 생성"""
        if not self.enabled:
            return []

        # ★ 야담 카테고리 전용 프롬프트
        if category == "yadam":
            return self._generate_yadam_title(keyword)

        # 카테고리별 프롬프트 조정
        if category == "sensitive":
            tone = "존중하고 정중하게, 선정적이거나 자극적인 표현은 절대 피하세요"
            examples = [
                "故 이순재 선생님, 그가 남긴 것들",
                "이순재 선생의 생애와 업적을 되돌아보다",
                "이순재 선생님을 추억하며"
            ]
        else:
            tone = "친근하고 따뜻하지만 과도하게 자극적이지 않게"
            examples = [
                "건강검진, 60대가 꼭 확인해야 할 3가지",
                "노후자금 준비, 지금 시작해도 늦지 않습니다",
                "우리 세대의 추억, 70년대 학교 이야기"
            ]

        prompt = f"""당신은 유튜브 제목 전문 카피라이터입니다. 주어진 주제로 **궁금증을 유발하는** 제목 3개를 생성하세요.

주제: {keyword}

[필수 규칙 - 반드시 준수]
1. 어떤 주제든 거부하지 않고 제목을 생성합니다
2. "죄송합니다", "부적절합니다", "맞지 않습니다" 같은 거부 문구를 절대 사용하지 않습니다
3. 로맨스, 연애, 아이돌, 판타지 등 모든 엔터테인먼트 주제를 허용합니다
4. 제목만 3개 출력하고, 다른 설명이나 대안 제시를 하지 않습니다

[제목 스타일 - 궁금증 유발 필수!]
- {tone}
- 35-50자 이내
- **궁금증을 유발하는 제목** (클릭해서 내용을 알고 싶게 만드는)
- 낚시성/공포 조장 표현 금지

[궁금증 유발 기법 - 반드시 1개 이상 사용]
- 질문형: "왜 ~일까?", "~하면 어떻게 될까?"
- 비밀/숨겨진 것: "아무도 말 안 해주는 ~", "숨겨진 ~"
- 반전/놀라움: "알고 보니 ~", "사실은 ~"
- 미완성: "~한 이유", "~의 비밀", "~의 진실"
- 숫자+호기심: "3가지 이유", "5가지 방법 중 마지막이..."

[좋은 예시 - 궁금증 유발]
- "60대가 절대 하면 안 되는 운동, 뭘까요?"
- "의사들이 가족에게만 알려주는 건강 비결"
- "연금 받기 전에 꼭 알아야 할 것, 아무도 안 알려줍니다"
- "그날 밤 무슨 일이 있었을까?"
- "30년 만에 밝혀진 진실"

[출력 형식]
제목1
제목2
제목3

지금 바로 "{keyword}" 주제로 **궁금증 유발** 제목 3개를 생성하세요:"""

        try:
            print("[TitleEngine] 🤖 Claude API로 제목 생성 중...")
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",  # script_engine과 동일한 모델 사용
                max_tokens=500,
                temperature=0.7,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            content = response.content[0].text.strip()

            # 응답에서 제목 추출 (라인별로 분리, 번호나 마커 제거)
            titles = []
            for line in content.split('\n'):
                line = line.strip()
                # ★ 수정: 앞의 번호 패턴만 제거 (1. 2. 3. 또는 - * #)
                # 제목 자체의 숫자(예: "500년")는 보존
                line = re.sub(r'^[\d]+[.\)]\s*', '', line)  # "1. " "2) " 등 제거
                line = re.sub(r'^[-*#]\s*', '', line)  # "- " "* " "# " 제거
                line = line.strip()
                if line and len(line) > 10:  # 최소 길이 체크
                    titles.append(line)

            if titles:
                print(f"[TitleEngine] ✅ Claude API 성공: {len(titles)}개 제목 생성")
                return titles[:3]  # 최대 3개만
            else:
                print("[TitleEngine] ⚠️ Claude 응답에서 제목 추출 실패")
                return []

        except Exception as e:
            print(f"[TitleEngine] ❌ Claude API 에러: {type(e).__name__} - {e}")
            print(f"[TitleEngine] 💡 폴백 제목으로 전환합니다")
            return []

    def _generate_yadam_title(self, keyword: str) -> List[str]:
        """
        ★ 야담 전용 제목 생성
        스타일: 주인공 특성 + 상황 + 반전/결과
        예: "바보남편에게 시집간 처녀, 알고 보니 천재였던 남편?"
        """
        prompt = f"""당신은 한국 전통 야담(野談) 유튜브 채널의 제목 전문가입니다.
주어진 주제로 **궁금증을 유발하는 야담 스타일** 제목 3개를 생성하세요.

주제: {keyword}

★★★ 야담 제목 필수 공식 ★★★
[주인공 특성] + [상황/행동] + [반전/결과 암시]

[주인공 특성 예시]
- 신분: 과부, 처녀, 총각, 선비, 양반, 상놈, 거지, 나무꾼, 약초꾼
- 특징: 바보, 무식한, 가난한, 늙은, 젊은, 예쁜, 못생긴

[상황/행동 예시]
- ~에게 시집간, ~를 구해준, ~와 하룻밤을 보낸
- ~를 도와준, ~에게 속은, ~를 만난

[반전/결과 암시 예시]
- 알고 보니 ~였던, ~가 벌어졌다, ~를 받았다
- 그런데 ~하자, 결국 ~가 되었다

★★★ 실제 인기 야담 제목 예시 ★★★
- "바보남편에게 시집간 처녀, 알고 보니 천재였던 남편?"
- "역적의 딸을 전재산 1냥 주고 구해낸 무식한 망나니"
- "올무에 걸린 여우를 구해주고 천복을 받은 약초꾼"
- "거지를 출세 시킨 주막집 과부의 낡은 비녀"
- "폭설로 과부집에서 하룻밤 함께한 노총각 나무꾼"
- "첫날밤 도망친 신랑, 30년 후 다시 찾아온 이유"

[필수 규칙]
1. 반드시 위 공식을 따를 것 (주인공+상황+반전)
2. 30-50자 이내
3. "야담"이라는 단어를 제목에 넣지 말 것
4. 궁금증을 유발하되 결말을 알려주지 말 것
5. 조선시대/전통 분위기의 단어 사용

[출력 형식]
제목1
제목2
제목3

지금 바로 "{keyword}" 주제로 야담 스타일 제목 3개를 생성하세요:"""

        try:
            print("[TitleEngine] 🎭 야담 스타일 제목 생성 중...")
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                temperature=0.8,  # 창의적인 제목을 위해 약간 높임
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            titles = []
            for line in response.content[0].text.strip().split("\n"):
                line = line.strip()
                line = re.sub(r'^[\d]+[.\)]\s*', '', line)
                line = re.sub(r'^[-*#]\s*', '', line)
                line = line.strip()
                if line and len(line) > 10:
                    titles.append(line)

            if titles:
                print(f"[TitleEngine] ✅ 야담 제목 생성 완료: {titles[0]}")
                return titles[:3]
            else:
                print("[TitleEngine] ⚠️ 야담 제목 추출 실패, 폴백 사용")
                return self._get_yadam_fallback_titles(keyword)

        except Exception as e:
            print(f"[TitleEngine] ❌ 야담 제목 API 에러: {e}")
            return self._get_yadam_fallback_titles(keyword)

    def _get_yadam_fallback_titles(self, keyword: str) -> List[str]:
        """야담 폴백 제목"""
        return [
            f"{keyword}, 알고 보니 숨겨진 비밀이 있었다",
            f"가난한 총각이 {keyword}를 만나고 벌어진 일",
            f"{keyword}의 놀라운 반전, 결말이 충격적이다"
        ]

    def _get_fallback_titles(self, keyword: str, category: str) -> List[str]:
        """API 실패 시 카테고리별 fallback 제목 생성 (궁금증 유발 스타일)"""
        base_kw = keyword

        if category == "sensitive":
            # 민감한 주제는 존중하는 제목
            return [
                f"{base_kw}, 우리가 몰랐던 이야기",
                f"{base_kw}의 숨겨진 의미는?",
                f"{base_kw}를 기억하며"
            ]
        elif category == "health":
            return [
                f"{base_kw}, 왜 60대가 특히 주의해야 할까?",
                f"의사들이 말 안 해주는 {base_kw}의 진실",
                f"{base_kw} 관리, 이것만은 절대 하면 안 됩니다"
            ]
        elif category == "money":
            return [
                f"{base_kw}, 아무도 알려주지 않는 진짜 비결",
                f"왜 {base_kw}가 노후를 좌우할까?",
                f"{base_kw}로 실패하는 사람들의 공통점"
            ]
        elif category == "emotion":
            return [
                f"{base_kw}, 왜 우리 세대만 이럴까?",
                f"시니어가 {base_kw}를 느끼는 진짜 이유",
                f"{base_kw}의 숨겨진 의미를 아시나요?"
            ]
        elif category == "memory":
            return [
                f"{base_kw}, 그때 무슨 일이 있었을까?",
                f"왜 우리는 {base_kw}를 잊지 못할까",
                f"{base_kw}의 숨겨진 뒷이야기"
            ]
        elif category == "history":
            return [
                f"{base_kw}, 역사가 숨긴 놀라운 진실",
                f"왜 {base_kw}는 비밀에 부쳐졌을까?",
                f"{base_kw}, 그날 무슨 일이 있었나"
            ]
        elif category == "drama":
            return [
                f"{base_kw}, 이런 결말은 아무도 예상 못했다",
                f"{base_kw}의 숨겨진 진실이 밝혀졌다",
                f"{base_kw}, 그날 밤 무슨 일이 있었을까"
            ]
        elif category == "kids":
            return [
                f"🌈 {base_kw}에게 무슨 일이? | 어린이 동화",
                f"옛날 옛날에 {base_kw}가 살았어요 🎈",
                f"🐰 {base_kw}의 신기한 모험!"
            ]
        else:  # general
            return [
                f"{base_kw}, 왜 지금 알아야 할까?",
                f"아무도 말 안 해주는 {base_kw}의 비밀",
                f"{base_kw}에 대해 몰랐던 3가지"
            ]

    def generate(self, keyword: str) -> TitleThumbnailResult:
        topic_score = self.scoring_engine.score_topic(keyword)
        base_kw = topic_score.main_keyword

        # 카테고리 감지
        category = self._detect_category(base_kw)

        # 1) 제목 생성 (Claude API 우선, fallback)
        candidates = self._generate_title_with_claude(base_kw, category)

        if not candidates:
            print(f"[TitleEngine] 🔄 폴백 제목 사용 (카테고리: {category})")
            candidates = self._get_fallback_titles(base_kw, category)
            print(f"[TitleEngine] 📝 폴백 제목 후보: {candidates}")
        else:
            print(f"[TitleEngine] ✅ Claude 제목 후보: {candidates}")

        final_title = candidates[0] if candidates else base_kw
        print(f"[TitleEngine] 🎯 최종 제목: {final_title}")

        # 2) 썸네일 텍스트 (카테고리별 조정)
        if category == "sensitive":
            thumbnail_text = f"{base_kw}"
        elif category == "health":
            thumbnail_text = f"{base_kw}\n건강 관리"
        elif category == "money":
            thumbnail_text = f"{base_kw}\n노후 준비"
        elif category == "history":
            thumbnail_text = f"{base_kw}\n역사 이야기"
        elif category == "drama":
            thumbnail_text = f"{base_kw}\n실화 스토리"
        elif category == "kids":
            thumbnail_text = f"🌈 {base_kw}\n동화 이야기"
        else:
            thumbnail_text = f"{base_kw}\n핵심 정리"

        # 3) 썸네일 이미지 프롬프트 (카테고리별 조정)
        if category == "sensitive":
            thumbnail_image_prompt = (
                "조용하고 평화로운 분위기, 추모와 기억의 느낌, "
                "차분한 색감, 중년 이상의 한국인, 정중하고 품위있는 느낌"
            )
        elif category == "health":
            thumbnail_image_prompt = (
                "중년 이상의 한국인이 건강하고 활기찬 모습, "
                "따뜻한 색감, 시니어 건강 정보 유튜브 썸네일 스타일"
            )
        elif category == "money":
            thumbnail_image_prompt = (
                "중년 이상의 한국인이 안정적이고 편안한 모습, "
                "신뢰감 있는 색감, 노후 재테크 정보 썸네일 스타일"
            )
        elif category in ["emotion", "memory"]:
            thumbnail_image_prompt = (
                "중년 이상의 한국인, 따뜻하고 향수를 불러일으키는 분위기, "
                "부드러운 색감, 감성적인 이야기 썸네일 스타일"
            )
        elif category == "history":
            thumbnail_image_prompt = (
                "역사적 장면, 한국 전통 의상, 궁궐이나 역사적 배경, "
                "드라마틱하고 웅장한 분위기, 역사 다큐멘터리 썸네일 스타일"
            )
        elif category == "drama":
            thumbnail_image_prompt = (
                "한국 드라마 포스터 스타일, 감성적인 남녀 주인공, "
                "도시 야경이나 카페 배경, 멜로 드라마틱한 분위기, "
                "세련되고 감각적인 색감, 한국 로맨스 드라마 썸네일 스타일"
            )
        elif category == "kids":
            thumbnail_image_prompt = (
                "귀여운 동물 캐릭터, 밝고 화사한 파스텔 색감, "
                "동화책 일러스트 스타일, 꿈꾸는 듯한 판타지 배경, "
                "무지개, 별, 구름 등 동화적 요소, 어린이 동화 썸네일 스타일, "
                "3D 애니메이션 캐릭터 또는 따뜻한 그림체"
            )
        else:
            thumbnail_image_prompt = (
                "중년 이상의 한국인, 친근하고 따뜻한 분위기, "
                "밝고 명확한 색감, 시니어 정보 콘텐츠 썸네일 스타일"
            )

        return TitleThumbnailResult(
            final_title=final_title,
            candidates=candidates,
            thumbnail_text=thumbnail_text,
            thumbnail_image_prompt=thumbnail_image_prompt,
            main_keyword=topic_score.main_keyword,
            sub_keywords=topic_score.related_keywords,
            topic_score=topic_score
        )

    def generate_contextual_thumbnail(self, script: 'Script', category: str, keyword: str) -> tuple:
        """
        스크립트 내용을 분석하여 맥락에 맞는 썸네일 프롬프트 생성
        ★ 유튜브 CTR 최적화 썸네일 가이드라인 적용

        Args:
            script: 생성된 스크립트 객체
            category: 콘텐츠 카테고리
            keyword: 원본 키워드

        Returns:
            (thumbnail_text, thumbnail_image_prompt) 튜플
        """
        if not self.enabled:
            return self._get_fallback_thumbnail(category, keyword)

        # 스크립트에서 핵심 내용 추출
        scene_summaries = []
        for scene in script.scenes[:3]:  # 처음 3장면만
            if scene.narration:
                # 나레이션에서 태그 제거
                clean_narration = scene.narration
                clean_narration = clean_narration.replace("[NARRATOR1]", "").replace("[NARRATOR2]", "")
                clean_narration = clean_narration.replace("[NARRATOR]", "")
                clean_narration = clean_narration.replace("[DIALOGUE]", "").replace("[/DIALOGUE]", "")
                clean_narration = clean_narration.strip()
                scene_summaries.append(clean_narration[:200])

        script_context = "\n".join(scene_summaries)

        # ★ 5대 장르 + 유아 썸네일 템플릿 (CTR 최적화)
        # 기존 후킹 법칙과 새로운 장르 가이드 융합
        thumbnail_templates = {
            # ① 감동 실화형 - 따뜻함, 감사, 여운, 공감
            "emotional": {
                "template": "EMOTIONAL",
                "colors": "warm beige background, soft golden light, cream text with subtle shadow",
                "lighting": "soft warm lighting from side, gentle shadows, golden hour feel",
                "mood": "heartwarming, touching, emotional depth, life wisdom",
                "composition": "person with warm expression on LEFT, emotional text on RIGHT, symbolic scene",
                "text_style": "공감 유발, 감동 예고, 여운 암시",
                "text_patterns": ["눈물 없이 못 보는", "마음이 따뜻해지는", "가슴 뭉클한", "평생 잊지 못할"]
            },

            # ② 회상·향수형 - 향수, 그리움, 안정감
            "nostalgic": {
                "template": "NOSTALGIC",
                "colors": "sepia tones, warm vintage brown, cream text, film grain effect",
                "lighting": "nostalgic warm glow, soft focus, vintage film look",
                "mood": "nostalgic, bittersweet, reminiscent, comfortable",
                "composition": "contemplative expression or vintage object on LEFT, memory text on RIGHT",
                "text_style": "추억 환기, 그리움 자극, 시대 공감",
                "text_patterns": ["그 시절 기억하시나요", "다시 돌아갈 수 없는", "그때 그 시절", "아련한 추억"]
            },

            # ③ 교훈·명언형 - 통찰, 자기 성찰, 격려
            "wisdom": {
                "template": "WISDOM",
                "colors": "deep navy or dark green background, gold accents, elegant white text",
                "lighting": "contemplative lighting, subtle spotlight, dignified atmosphere",
                "mood": "thoughtful, wise, inspiring, profound",
                "composition": "wise figure or symbolic image on LEFT, profound text on RIGHT",
                "text_style": "통찰 제시, 깨달음 암시, 인생 교훈",
                "text_patterns": ["평생 가슴에 남는", "인생을 바꾼 한마디", "이 말 하나면", "깨달음을 주는"]
            },

            # ④ 지식·정보형 - 신뢰, 실용, 자기계발
            "knowledge": {
                "template": "KNOWLEDGE",
                "colors": "clean navy blue background, gold accents, clear white text",
                "lighting": "bright professional lighting, clear visibility, trustworthy",
                "mood": "trustworthy, informative, practical, helpful",
                "composition": "friendly expert face on LEFT, info text on RIGHT, clean design",
                "text_style": "실용 정보, 신뢰감, 전문성",
                "text_patterns": ["이것만 알면", "모르면 손해", "전문가가 알려주는", "꼭 알아야 할"]
            },

            # ⑤ 명작·음악 해설형 - 감탄, 감동, 흥미
            "classic": {
                "template": "CLASSIC",
                "colors": "rich dark background, warm amber accents, elegant gold text",
                "lighting": "artistic lighting, concert hall feel, appreciative atmosphere",
                "mood": "appreciative, moved, intrigued, artistic",
                "composition": "artwork or artist silhouette on LEFT, review text on RIGHT",
                "text_style": "작품 감상, 숨겨진 의미, 감동 포인트",
                "text_patterns": ["이 노래의 숨은 뜻", "아무도 몰랐던 비밀", "듣고 나면 달라지는", "전율이 느껴지는"]
            },

            # ⑥ 드라마형 서사 - 긴장감, 몰입, 반전, 공감
            "drama": {
                "template": "DRAMA",
                "colors": "dramatic dark tones with red or blue accents, high contrast, cinematic color grading",
                "lighting": "dramatic side lighting, strong shadows, noir-style contrast",
                "mood": "tense, immersive, suspenseful, emotionally charged",
                "composition": "silhouette or back view figure on LEFT, dramatic text on RIGHT, symbolic elements",
                "text_style": "긴장감 유발, 반전 암시, 갈등 표현",
                "text_patterns": ["결국 이런 결말이", "아무도 예상 못한", "그날 밤 무슨 일이", "충격 실화"]
            },

            # 유아 (기존 유지)
            "kids": {
                "template": "KIDS",
                "colors": "bright pastel rainbow, pink and yellow accents, sparkles",
                "lighting": "cheerful bright lighting, no shadows, magical glow",
                "mood": "fun, magical, adventurous, friendly",
                "composition": "cute character on LEFT, story title on RIGHT",
                "text_style": "재미, 모험, 친근함",
                "text_patterns": ["신나는 모험", "함께 떠나요", "재미있는 이야기", "두근두근"]
            },

            # 기본 (감동 실화형으로 폴백)
            "general": {
                "template": "EMOTIONAL",
                "colors": "warm beige background, soft golden light, cream text",
                "lighting": "soft warm lighting, friendly atmosphere",
                "mood": "friendly, approachable, emotionally engaging",
                "composition": "friendly face on LEFT, topic text on RIGHT",
                "text_style": "공감 유발, 정보 전달",
                "text_patterns": ["알아두면 좋은", "꼭 알아야 할", "함께 나누고 싶은", "마음에 남는"]
            }
        }

        template = thumbnail_templates.get(category, thumbnail_templates["general"])

        prompt = f"""유튜브 썸네일을 위한 이미지 프롬프트와 후킹 텍스트를 생성해주세요.

★★★ 유튜브 CTR 최적화 가이드라인 ★★★

카테고리: {category}
주제: {keyword}
템플릿 타입: {template['template']}

대본 내용 (처음 부분):
{script_context}

========== 썸네일 디자인 규칙 ==========
1. 색상: {template['colors']}
2. 조명: {template['lighting']}
3. 분위기: {template['mood']}
4. 구도: {template['composition']}

========== 후킹 텍스트 규칙 ==========
★ 3~6단어 (최대 15자)
★ 스타일: {template['text_style']}
★ 참고 패턴: {', '.join(template['text_patterns'])}

★★★ 절대 금지 ★★★
- 결과/정답을 알려주는 텍스트 (X: "세종대왕의 업적", O: "아무도 몰랐던 진실")
- 너무 긴 텍스트 (6단어 초과)
- 평범한 설명문 (X: "건강 정보입니다")

★★★ 좋은 예시 ★★★
- "그날 밤 무슨 일이" (궁금증 유발)
- "아무도 예상 못한 결말" (기대감)
- "의사도 놀란 비결" (권위+궁금증)
- "눈물 없이 못 보는" (감정 자극)

출력 형식:
IMAGE_PROMPT: (영어, 인물 왼쪽 배치, 오른쪽에 텍스트 공간 확보)
THUMBNAIL_TEXT: (한글 3~6단어, 궁금증 유발)"""

        try:
            print("[TitleEngine] 🎨 CTR 최적화 썸네일 생성 중...")
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=600,
                temperature=0.8,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            content = response.content[0].text.strip()

            # 응답 파싱
            image_prompt = ""
            thumbnail_text = ""

            for line in content.split('\n'):
                line = line.strip()
                if line.startswith("IMAGE_PROMPT:"):
                    image_prompt = line.replace("IMAGE_PROMPT:", "").strip()
                elif line.startswith("THUMBNAIL_TEXT:"):
                    thumbnail_text = line.replace("THUMBNAIL_TEXT:", "").strip()

            # 텍스트 길이 검증 (3~6단어, 15자 이내)
            if thumbnail_text:
                word_count = len(thumbnail_text.replace(" ", ""))
                if word_count > 15:
                    # 너무 길면 자르기
                    thumbnail_text = thumbnail_text[:15]
                    print(f"  ⚠️ 텍스트 길이 초과, 자동 조정: {thumbnail_text}")

            if image_prompt and thumbnail_text:
                print(f"[TitleEngine] ✅ CTR 최적화 썸네일 생성 완료")
                print(f"  - 템플릿: {template['template']}")
                print(f"  - 후킹 텍스트: {thumbnail_text}")
                print(f"  - 이미지 구도: 인물 왼쪽, 텍스트 오른쪽")
                return thumbnail_text, image_prompt
            else:
                print("[TitleEngine] ⚠️ 응답 파싱 실패, 폴백 사용")
                return self._get_fallback_thumbnail(category, keyword)

        except Exception as e:
            print(f"[TitleEngine] ❌ 썸네일 프롬프트 생성 실패: {e}")
            return self._get_fallback_thumbnail(category, keyword)

    def _get_fallback_thumbnail(self, category: str, keyword: str) -> tuple:
        """
        폴백 썸네일 텍스트와 프롬프트
        ★ 5대 장르별 CTR 최적화 스타일 적용
        """
        fallbacks = {
            # ① 감동 실화형
            "emotional": (
                "눈물 없이 못 보는",
                "Warm Korean person on LEFT SIDE with gentle emotional expression, "
                "soft beige cream background with golden light, warm brown tones, "
                "RIGHT SIDE empty for text overlay, soft warm side lighting, "
                "heartwarming touching mood, YouTube thumbnail, 1280x720"
            ),

            # ② 회상·향수형
            "nostalgic": (
                "그 시절 기억하시나요",
                "Contemplative Korean person on LEFT SIDE with nostalgic expression, "
                "sepia vintage tones, warm brown background with film grain effect, "
                "RIGHT SIDE empty for text, nostalgic soft glow lighting, "
                "memories and reminiscence mood, YouTube thumbnail, 1280x720"
            ),

            # ③ 교훈·명언형
            "wisdom": (
                "인생을 바꾼 한마디",
                "Wise Korean person on LEFT SIDE with thoughtful contemplative expression, "
                "deep navy or dark green background, elegant gold accents, "
                "RIGHT SIDE empty for text overlay, dignified subtle spotlight, "
                "wisdom and insight mood, YouTube thumbnail, 1280x720"
            ),

            # ④ 지식·정보형
            "knowledge": (
                "이것만 알면",
                "Friendly expert Korean person on LEFT SIDE with trustworthy expression, "
                "clean navy blue background, golden light accents, "
                "RIGHT SIDE empty for text overlay, bright professional lighting, "
                "informative trustworthy mood, YouTube thumbnail, 1280x720"
            ),

            # ⑤ 명작·음악 해설형
            "classic": (
                "이 노래의 숨은 뜻",
                "Artistic scene with musician silhouette or artwork on LEFT SIDE, "
                "rich dark background with warm amber accents, elegant gold tones, "
                "RIGHT SIDE empty for text overlay, concert hall artistic lighting, "
                "appreciative artistic mood, YouTube thumbnail, 1280x720"
            ),

            # ⑥ 드라마형 서사
            "drama": (
                "그날 밤 무슨 일이",
                "Dramatic silhouette or back view of Korean person on LEFT SIDE, "
                "dark moody background with red or blue accent lighting, high contrast cinematic look, "
                "RIGHT SIDE empty for text overlay, dramatic side lighting with strong shadows, "
                "tense suspenseful noir mood, YouTube thumbnail, 1280x720"
            ),

            # 유아 (기존 유지)
            "kids": (
                "신나는 모험",
                "Cute adorable animal character on LEFT SIDE with big sparkling eyes, "
                "bright pastel rainbow background with pink and yellow sparkles, "
                "RIGHT SIDE empty for title text, cheerful bright magical lighting, "
                "magical fairy tale atmosphere, 3D animation style, YouTube thumbnail, 1280x720"
            ),

            # 기본 (감동 실화형으로 폴백)
            "general": (
                "마음에 남는 이야기",
                "Friendly Korean person on LEFT SIDE with warm welcoming expression, "
                "soft beige background with warm golden accents, "
                "RIGHT SIDE empty for text overlay, soft warm lighting, "
                "emotionally engaging friendly mood, YouTube thumbnail, 1280x720"
            )
        }

        return fallbacks.get(category, fallbacks["general"])
