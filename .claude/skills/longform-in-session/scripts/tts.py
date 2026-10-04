"""script.json → audio_full.mp3 + audio_segments.json (YOUTUBENEWS TTSEngine 그대로 사용).

script.json: {"title": "...", "scenes": [{"id": 1, "title": "...", "images": 2, "text": "나레이션"}, ...]}

- 엔진이 시작 무음 1.5초 + 씬마다 2초 무음을 넣는다. 영상 길이 = 1.5 + Σ(말 길이 + 2).
- 기본값은 종혁님이 앱에서 실제로 쓰는 설정과 같다: 엔진 elevenlabs2.5(Turbo v2.5), 스타일 불교강의
  (voice 4p0HBzAAGyju0nYfNntV = 한국어 기본 음성), 속도 1.0(종혁님 요청: 앱 기본 0.9보다 조금 빠르게).
  ※ config의 '불교종교'(voice zgDzx5jL…)는 앱 스타일 목록에 없는 음성이다. 같은 voice라도 모델(v3 / v2.5)이
    다르면 소리가 달라지니 엔진도 앱과 맞춘다.
- --calm: v3 엔진(elevenlabs)에서만 의미 있음. 슬픔 계열 감정 태그를 차분한 태그로 바꾼다(이 실행에서만).
사용: python tts.py <work_dir> [--engine elevenlabs2.5] [--style 불교강의] [--speed 1.0] [--calm]
"""
import sys, os, json, dataclasses, argparse
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, REPO); os.chdir(REPO)
os.environ.setdefault("ELEVENLABS_API_KEY", "proxy-injected")  # 클라우드 세션은 프록시가 키를 주입

import config
import engines.tts_engine as te
from models.types import Script, Scene

ap = argparse.ArgumentParser()
ap.add_argument("work_dir"); ap.add_argument("--engine", default="elevenlabs2.5")
ap.add_argument("--style", default="불교강의"); ap.add_argument("--speed", type=float, default=1.0)
ap.add_argument("--calm", action="store_true")
ap.add_argument("--sample", type=int, default=0, help="1이면 첫 씬만 합성해 sample.mp3로 저장(목소리 확인용)")
a = ap.parse_args()
if a.calm:
    config.EMOTION_TAGS[a.style] = {"intro": "[calm, gentle]", "body_sad": "[calm, warm]", "body_hope": "[calm, warm]",
                                    "climax": "[soft, contemplative]", "ending": "[peaceful, soothing]"}
    te.EMOTION_TAGS = config.EMOTION_TAGS

d = json.load(open(os.path.join(a.work_dir, "script.json"), encoding="utf-8"))
scenes = [Scene(scene_id=s["id"], title=s["title"], text=s["text"], image_count=s["images"]) for s in d["scenes"]]
script = Script(title=d["title"], scenes=scenes, duration_min=10, total_panels=sum(s.image_count for s in scenes))
tts = te.TTSEngine(engine=a.engine, style=a.style, speed=a.speed)
if a.sample:
    audio = tts._synthesize(scenes[0].text, scene_idx=0, total_scenes=len(scenes))
    open(os.path.join(a.work_dir, "sample.mp3"), "wb").write(audio)
    print("sample:", os.path.join(a.work_dir, "sample.mp3")); sys.exit(0)
path, segs, subs = tts.generate_full_audio(script, os.path.join(a.work_dir, "audio_full.mp3"))
json.dump({"segments": [dataclasses.asdict(s) for s in segs],
           "subtitle_segments": [dataclasses.asdict(s) for s in subs]},
          open(os.path.join(a.work_dir, "audio_segments.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("audio:", path)
