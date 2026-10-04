"""script.json → audio_full.mp3 + audio_segments.json (YOUTUBENEWS TTSEngine 그대로 사용).

script.json: {"title": "...", "scenes": [{"id": 1, "title": "...", "images": 2, "text": "나레이션"}, ...]}

- 엔진이 시작 무음 1.5초 + 씬마다 2초 무음을 넣는다. 영상 길이 = 1.5 + Σ(말 길이 + 2).
- --calm: 이번 영상처럼 교리·해설 내용이면 '불교종교'의 감정 태그 중 슬픔 계열([sad, comforting])을
  차분한 태그로 바꿔 쓴다. config.py는 건드리지 않고 이 실행에서만 바꾼다.
사용: python tts.py <work_dir> [--style 불교종교] [--calm]
"""
import sys, os, json, dataclasses, argparse
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, REPO); os.chdir(REPO)
os.environ.setdefault("ELEVENLABS_API_KEY", "proxy-injected")  # 클라우드 세션은 프록시가 키를 주입

import config
import engines.tts_engine as te
from models.types import Script, Scene

ap = argparse.ArgumentParser()
ap.add_argument("work_dir"); ap.add_argument("--style", default="불교종교"); ap.add_argument("--calm", action="store_true")
a = ap.parse_args()
if a.calm:
    config.EMOTION_TAGS[a.style] = {"intro": "[calm, gentle]", "body_sad": "[calm, warm]", "body_hope": "[calm, warm]",
                                    "climax": "[soft, contemplative]", "ending": "[peaceful, soothing]"}
    te.EMOTION_TAGS = config.EMOTION_TAGS

d = json.load(open(os.path.join(a.work_dir, "script.json"), encoding="utf-8"))
scenes = [Scene(scene_id=s["id"], title=s["title"], text=s["text"], image_count=s["images"]) for s in d["scenes"]]
script = Script(title=d["title"], scenes=scenes, duration_min=10, total_panels=sum(s.image_count for s in scenes))
tts = te.TTSEngine(engine="elevenlabs", style=a.style)
path, segs, subs = tts.generate_full_audio(script, os.path.join(a.work_dir, "audio_full.mp3"))
json.dump({"segments": [dataclasses.asdict(s) for s in segs],
           "subtitle_segments": [dataclasses.asdict(s) for s in subs]},
          open(os.path.join(a.work_dir, "audio_segments.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("audio:", path)
