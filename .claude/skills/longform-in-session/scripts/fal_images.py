"""fal(FLUX) 저가 이미지 — 씬 분위기만 맞추는 기본 방식 (장당 약 $0.003, flux-schnell).

종혁님 기준: 그림은 돈을 아낀다. 이야기가 이어지면 인물이 조금 달라도 되고, 상황·분위기만 맞으면 된다.
그래서 기본은 이 스크립트, gpt-image-2 2x2 시트(imggen.py)는 "인물 일관성이 꼭 필요하다"고 할 때만 쓴다.

화풍은 저장소에 이미 있는 종혁님 프롬프트를 그대로 쓴다:
  storymaker/ai_prompt_generator.py 의 REGIONAL_ENGINE_STYLES[region]["fal"]
  (korea = 수묵담채, china = 도상화, india = 연필 스케치 — 앱의 '이미지 스타일' 드롭다운과 같음)
FalGenerator는 style="default"로 만든다. 앱 기본 엔진 fal-anime는 "anime style …" 접두어를 붙이는데,
수묵담채 블록의 "no anime"과 충돌하기 때문이다.

준비: 환경 변수 FAL_KEY (세션 환경 설정 → Edit → 환경 변수. 새 세션부터 적용, 키는 채팅에 붙여 넣지 않음).
입력: <work_dir>/prompts.json = ["영어 장면 묘사", ...]  (컷 순서 = 영상 순서, 개수 = script.json images 합계)
사용: python fal_images.py <work_dir> [--region korea] [--model flux-schnell]
결과: <work_dir>/panels/panel_01.jpg … (render.py가 그대로 읽음). 이미 있는 컷은 건너뛴다(재실행해도 재과금 없음).
"""
import sys, os, json, argparse
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, REPO); os.chdir(REPO)
from PIL import Image
from engines.image_engine import FalGenerator
from storymaker.ai_prompt_generator import get_regional_style_block

ap = argparse.ArgumentParser()
ap.add_argument("work_dir"); ap.add_argument("--region", default="korea"); ap.add_argument("--model", default="flux-schnell")
a = ap.parse_args()
if not os.getenv("FAL_KEY"):
    sys.exit("FAL_KEY 환경 변수가 없습니다 — 세션 환경 설정에 등록 후 새 세션에서 실행하세요.")

W = os.path.abspath(a.work_dir)
prompts = json.load(open(f"{W}/prompts.json", encoding="utf-8"))
style = get_regional_style_block(a.region, "fal")
gen = FalGenerator(model=a.model, style="default")
os.makedirs(f"{W}/panels", exist_ok=True)
print(f"{len(prompts)}장 예정 (모델 {a.model}), 화풍: {style[:60]}...")
for i, p in enumerate(prompts, 1):
    out = f"{W}/panels/panel_{i:02d}.jpg"
    if os.path.exists(out):
        continue
    tmp = out.replace(".jpg", ".src")
    try:
        gen.generate(f"{style}. {p}, no text, no letters", tmp)
    except Exception as e:
        # 재시도하지 않는다: 원인을 보고 다시 실행하면 남은 컷만 생성된다
        sys.exit(f"컷 {i} 실패 — 원인 확인 후 재실행: {e}")
    Image.open(tmp).convert("RGB").save(out, quality=95); os.remove(tmp)
    print("saved", out)
