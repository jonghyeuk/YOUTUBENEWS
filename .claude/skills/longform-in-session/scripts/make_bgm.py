"""ElevenLabs 효과음 생성으로 명상 배경음 bed를 만든다.

왜 효과음인가: 이 세션의 ElevenLabs 키는 music_generation 권한이 없고(401), sound-generation(≤30초)은 된다.
그래서 30초 루프 드론 2종을 크로스페이드로 이어 깔고, 싱잉볼·피리·산사 종을 35~46초 간격으로 얹는다.
키에 음악 권한이 생기면 /v1/music 으로 한 곡을 뽑는 편이 더 자연스럽다.

사용: python make_bgm.py <work_dir> <목표길이초>   → <work_dir>/bgm.mp3
"""
import sys, os, random, requests
from pydub import AudioSegment as A

ELEMENTS = {
    "drone":  ({"text": "Deep warm meditative ambient drone pad, sustained low harmonic tones, very slow gentle swelling, soft airy texture, peaceful Buddhist meditation atmosphere, no percussion, no melody", "duration_seconds": 30, "loop": True, "prompt_influence": 0.6}),
    "drone2": ({"text": "Soft ethereal ambient pad, warm sustained open fifth chord, gentle shimmering overtones, calm temple meditation atmosphere, no percussion", "duration_seconds": 30, "loop": True, "prompt_influence": 0.6}),
    "bowl1":  ({"text": "Single Tibetan singing bowl struck softly with a wooden mallet, medium pitch, long pure resonant shimmering decay, quiet room", "duration_seconds": 14, "prompt_influence": 0.7}),
    "bowl2":  ({"text": "Large deep Tibetan singing bowl struck gently once, low pitch, very long warm resonant decay", "duration_seconds": 18, "prompt_influence": 0.7}),
    "bell":   ({"text": "Distant Buddhist temple bell, a single soft deep toll echoing across misty mountains, long fading reverb", "duration_seconds": 16, "prompt_influence": 0.7}),
    "flute":  ({"text": "Soft breathy bamboo flute playing a slow sparse meditative phrase, long held notes, gentle hall reverb, solo, no other instruments", "duration_seconds": 20, "prompt_influence": 0.6}),
}


def fetch(work, name, body):
    path = os.path.join(work, "bgm_parts", f"{name}.mp3")
    if os.path.exists(path):
        return path
    r = requests.post("https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_192", json=body, timeout=300)
    r.raise_for_status()
    open(path, "wb").write(r.content)
    return path


def main(work, target_sec):
    os.makedirs(os.path.join(work, "bgm_parts"), exist_ok=True)
    parts = {n: fetch(work, n, b) for n, b in ELEMENTS.items()}
    norm = lambda a, t: a.apply_gain(t - a.dBFS)
    d1, d2 = norm(A.from_mp3(parts["drone"]), -24), norm(A.from_mp3(parts["drone2"]), -24)
    target = int(target_sec * 1000)
    bed, i = d1, 1
    while len(bed) < target:
        bed = bed.append(d2 if i % 2 else d1, crossfade=6000); i += 1
    bed = bed[:target]
    acc = {"bowl1": norm(A.from_mp3(parts["bowl1"]), -27), "bowl2": norm(A.from_mp3(parts["bowl2"]), -27),
           "bell": norm(A.from_mp3(parts["bell"]), -29), "flute": norm(A.from_mp3(parts["flute"]), -29)}
    order, t, k = ["bowl2", "flute", "bowl1", "bell"], 8000, 0
    random.seed(7)
    while t < target - 25000:
        bed = bed.overlay(acc[order[k % 4]].fade_in(50).fade_out(1500), position=t)
        t += random.randint(34000, 46000); k += 1
    bed = norm(bed.fade_in(4000).fade_out(8000), -21)
    out = os.path.join(work, "bgm.mp3")
    bed.export(out, format="mp3", bitrate="192k")
    print("bgm:", out, f"{len(bed)/1000:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]))
