"""채널 오프닝·엔딩 붙이기 — 렌더된 본편(final.mp4)은 다시 렌더하지 않고 앞뒤에 붙인다.

- 오프닝: 채널 고정 효과음(예: 번개+천둥) + 번개 섬광(흰 플래시) + 이 편의 그림 한 장 줌
- 엔딩: 나레이터의 마무리 멘트(좋아요·구독…) + 채널 고정 엔딩 음악 + 자막(본편과 같은 나눔명조 스타일) + 페이드아웃
- 연결: 오프닝→본편→엔딩을 1초 크로스페이드(영상 xfade + 소리 acrossfade)

채널 설정: assets/channels/<채널>.json. 효과음·음악은 처음 한 번 ElevenLabs 효과음 생성으로 만들어
assets/channels/<채널>/ 에 저장하고 이후 모든 편에서 같은 파일을 쓴다(채널 고정 소리 — 바꾸려면 파일을 지운다).

사용: python brand.py <work_dir> --channel yahwa [--intro-image panels/panel_23.jpg] [--outro-image panels/panel_24.jpg]
결과: <work_dir>/final_branded.mp4
"""
import sys, os, json, argparse, subprocess, requests, io, re
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
ASSETS = os.path.abspath(os.path.join(os.path.dirname(__file__), "../assets/channels"))
sys.path.insert(0, REPO); os.chdir(REPO)
for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_API_KEY"):
    os.environ.setdefault(k, "proxy-injected")
from pydub import AudioSegment as A
from engines.video_engine import VideoEngine
from engines.subtitle_engine import SubtitleEngine
from engines.audio_utils import get_audio_duration
import engines.tts_engine as te

ap = argparse.ArgumentParser()
ap.add_argument("work_dir"); ap.add_argument("--channel", default="yahwa")
ap.add_argument("--intro-image"); ap.add_argument("--outro-image")
a = ap.parse_args()
W = os.path.abspath(a.work_dir)
cfg = json.load(open(os.path.join(ASSETS, f"{a.channel}.json"), encoding="utf-8"))
B = os.path.join(W, "brand"); os.makedirs(B, exist_ok=True)
XF = 1.0


def asset(spec):
    """채널 고정 소리: 없으면 한 번만 생성해 저장."""
    path = os.path.join(ASSETS, spec["file"])
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        r = requests.post("https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_192",
                          json=spec["prompt"], timeout=300)
        r.raise_for_status()  # 실패 시 재시도하지 않는다(과금) — 원인 확인 후 재실행
        open(path, "wb").write(r.content)
        print("생성:", path)
    return path


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-1500:])


def ass_time(t):
    h, m = int(t // 3600), int(t % 3600 // 60); s = t - h * 3600 - m * 60
    return f"{h}:{m:02d}:{s:05.2f}"


panels = sorted(f for f in os.listdir(os.path.join(W, "panels")) if f.endswith(".jpg"))
intro_img = os.path.join(W, a.intro_image) if a.intro_image else os.path.join(W, "panels", panels[0])
outro_img = os.path.join(W, a.outro_image) if a.outro_image else os.path.join(W, "panels", panels[-1])
ve = VideoEngine()
main = os.path.join(W, "final.mp4")
# 본편 최종 믹스의 실제 음량(나레이션 구간)을 재서 오프닝·엔딩을 거기에 맞춘다.
# (엔진의 TTS+BGM 믹스가 나레이션을 약 -27dBFS로 낮추기 때문에, -18 같은 고정값을 쓰면 엔딩만 10dB 커진다)
_m = A.from_file(main)
REF = _m[30000:min(len(_m), 150000)].dBFS
print(f"본편 기준 음량 {REF:.1f} dBFS")

# ── 1. 오프닝 ─────────────────────────────────────────
snd = A.from_file(asset(cfg["opening_sound"]))
snd = snd.apply_gain((REF + 18) - snd.max_dBFS)[:6000]          # 천둥 피크 = 나레이션 평균보다 18dB 위
intro_len = max(3.0, len(snd) / 1000)
snd = (snd + A.silent(int((intro_len + XF) * 1000) - len(snd))).fade_out(800)
snd.export(f"{B}/intro.wav", format="wav")
ve._create_scene_clip_smooth_zoom([intro_img], intro_len, f"{B}/intro_raw.mp4", tail_overlap=XF, effect_offset=1)
flash = "+".join(f"between(t,{s},{e})" for s, e in cfg.get("opening_flashes", []))
vf = f"eq=brightness='if({flash},0.55,-0.12)':eval=frame" if flash else "null"   # 평소엔 조금 어둡게, 번개 때 번쩍
run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/intro_raw.mp4", "-i", f"{B}/intro.wav", "-vf", vf,
     "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
     "-shortest", f"{B}/intro.mp4"])

# ── 2. 엔딩 ─────────────────────────────────────────
tts = te.TTSEngine(engine="elevenlabs2.5", style="불교강의", speed=1.0)
tts.voice_id = cfg["narrator"]
voice = A.from_mp3(io.BytesIO(tts._synthesize(cfg["outro_text"], 0, 1)))
voice = voice.apply_gain(REF + 0.5 - voice.dBFS)                 # 본편 나레이션과 같은 음량
lead, tail = 1.0, 4.0
outro_len = lead + len(voice) / 1000 + tail
music = A.from_file(asset(cfg["outro_music"]))
music = music.apply_gain(REF - 9 - music.dBFS)
while len(music) < outro_len * 1000:
    music = music.append(music, crossfade=2000)
music = music[:int(outro_len * 1000)].fade_in(1500).fade_out(3000)
mix = music.overlay(voice, position=int(lead * 1000))
mix.export(f"{B}/outro.wav", format="wav")
ve._create_scene_clip_smooth_zoom([outro_img], outro_len, f"{B}/outro_raw.mp4", tail_overlap=0.0, effect_offset=0)
# 자막: 문장 단위, 글자 수 비례로 시간 배분 (본편과 같은 ASS 스타일)
sents = [s.strip() for s in re.split(r"(?<=[.?!])\s+", cfg["outro_text"]) if s.strip()]
total = sum(len(s) for s in sents); t = lead; lines = []
for s in sents:
    d = len(voice) / 1000 * len(s) / total
    lines.append(f"Dialogue: 0,{ass_time(t)},{ass_time(t + d)},Default,,0,0,0,,{s}"); t += d
open(f"{B}/outro.ass", "w", encoding="utf-8").write(SubtitleEngine()._get_ass_header() + "\n".join(lines) + "\n")
run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/outro_raw.mp4", "-i", f"{B}/outro.wav",
     "-vf", f"fade=t=out:st={outro_len - 2:.2f}:d=2", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
     "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", f"{B}/outro_nosub.mp4"])
ve.burn_subtitles(f"{B}/outro_nosub.mp4", f"{B}/outro.ass", f"{B}/outro.mp4")

# ── 3. 오프닝 + 본편 + 엔딩 ─────────────────────────────
L = [get_audio_duration(p) for p in (f"{B}/intro.mp4", main, f"{B}/outro.mp4")]
fc = ("[0:a]aformat=sample_rates=44100:channel_layouts=stereo[a0];"
      "[1:a]aformat=sample_rates=44100:channel_layouts=stereo[a1];"
      "[2:a]aformat=sample_rates=44100:channel_layouts=stereo[a2];"
      f"[0:v][1:v]xfade=transition=fade:duration={XF}:offset={L[0] - XF:.3f}[v01];"
      f"[v01][2:v]xfade=transition=fade:duration={XF}:offset={L[0] + L[1] - 2 * XF:.3f}[v];"
      f"[a0][a1]acrossfade=d={XF}[a01];[a01][a2]acrossfade=d={XF}[a]")
run(["ffmpeg", "-y", "-v", "error", "-i", f"{B}/intro.mp4", "-i", main, "-i", f"{B}/outro.mp4",
     "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
     "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", f"{W}/final_branded.mp4"])
print("BRANDED", f"{W}/final_branded.mp4", f"오프닝 {L[0]:.1f}s + 본편 {L[1]:.1f}s + 엔딩 {L[2]:.1f}s")
