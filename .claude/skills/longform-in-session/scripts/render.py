"""YOUTUBENEWS 파이프라인 step5~7로 렌더 (자막 → 줌/크로스페이드 클립 + BGM → 자막 번인).

work_dir에 필요한 것: script.json, audio_full.mp3, audio_segments.json, panels/panel_01.jpg..., bgm.mp3(선택)
사용: python render.py <work_dir> [--style 불교강의] [--bgm-volume 0.18]
결과: <work_dir>/final.mp4  (파이프라인 산출물은 <work_dir>/project/ 아래)
"""
import sys, os, json, time, shutil, argparse
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, REPO); os.chdir(REPO)
for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_API_KEY"):
    os.environ.setdefault(k, "proxy-injected")

from pipeline import Pipeline
from models.types import Script, Scene, AudioSegment
from engines.tts_engine import SubtitleSegment

ap = argparse.ArgumentParser()
ap.add_argument("work_dir"); ap.add_argument("--style", default="불교강의"); ap.add_argument("--bgm-volume", type=float, default=0.18)
a = ap.parse_args()
W = os.path.abspath(a.work_dir)
d = json.load(open(f"{W}/script.json", encoding="utf-8"))
au = json.load(open(f"{W}/audio_segments.json", encoding="utf-8"))
n_img = sum(s["images"] for s in d["scenes"])
panels = [f"{W}/panels/panel_{i:02d}.jpg" for i in range(1, n_img + 1)]
missing = [p for p in panels if not os.path.exists(p)]
assert not missing, f"컷 이미지 없음: {missing[:3]}"

scenes, k = [], 0
for s in d["scenes"]:
    sc = Scene(scene_id=s["id"], title=s["title"], text=s["text"], image_count=s["images"])
    sc.image_paths = panels[k:k + s["images"]]; k += s["images"]
    scenes.append(sc)

p = Pipeline(project_dir=f"{W}/project")
p.create_project(d["title"][:20], 10)
p.project.style = a.style
p.project.script = Script(title=d["title"], scenes=scenes, duration_min=10, total_panels=n_img)
p.project.audio_path = f"{W}/audio_full.mp3"
p.project.audio_segments = [AudioSegment(**x) for x in au["segments"]]
p.project.subtitle_segments = [SubtitleSegment(**x) for x in au["subtitle_segments"]]
bgm = f"{W}/bgm.mp3" if os.path.exists(f"{W}/bgm.mp3") else None

t = time.time()
p.step5_generate_subtitles(use_whisper=False)
p.step6_render_video(use_ken_burns=True, bgm_path=bgm, bgm_volume=a.bgm_volume)
final = p.step7_burn_subtitles()
shutil.copy(final, f"{W}/final.mp4")
print("FINAL", f"{W}/final.mp4", f"{time.time()-t:.0f}s")
