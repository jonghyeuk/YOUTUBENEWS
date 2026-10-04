"""visual.json → 인물 기준 시트 1장 + 2x2 스토리보드 시트 프롬프트(job json)들을 만든다.

visual.json 형식:
{
  "style": "refined painterly illustration inspired by ... (화풍 한 문단)",
  "characters": {"SHARIPUTRA": "lean elderly monk around 60, ...", ...},
  "panels": ["SHARIPUTRA kneeling at a pond ...", "Vast calm ocean at dawn ...", ...]
}
panels 순서 = 영상 순서. 개수는 4의 배수로 맞춘다(모자라면 마지막 시트가 빈 칸을 지어낸다).

교훈(실제 실패에서 나옴):
- 모든 시트에 인물 목록을 넣으면, 인물이 이름으로 나오지 않는 풍경 칸에도 참조 시트의 인물 전원을
  그려 넣는다. → "이름이 나온 칸에만 인물" 규칙 + 풍경 칸에는 ", no people, no human figures"를 붙인다.
- 칸 사이는 얇은 검은 선으로 나누게 해야 split_sheet.py가 실제 경계를 찾아 자를 수 있다.
"""
import sys, os, json

LAYOUT = ("Create ONE image that is a storyboard sheet: a perfect 2 by 2 grid of four separate cinematic 16:9 panels, "
          "all exactly the same size, separated only by thin straight solid black lines exactly at the horizontal and "
          "vertical center of the image, no outer border. Each panel is an independent full composition. "
          "Absolutely no text, letters, captions, numbers, speech bubbles or watermarks anywhere. ")
POS = ["top-left", "top-right", "bottom-left", "bottom-right"]


def main(visual_path, work_dir):
    v = json.load(open(visual_path, encoding="utf-8"))
    names = list(v["characters"].keys())
    sheets = os.path.join(work_dir, "sheets"); os.makedirs(sheets, exist_ok=True)
    jobs = os.path.join(work_dir, "jobs"); os.makedirs(jobs, exist_ok=True)
    ref = os.path.join(sheets, "ref_characters.jpg")

    chars_txt = "; ".join(f"({i+1}) {n}: {d}" for i, (n, d) in enumerate(v["characters"].items()))
    json.dump({"out": ref, "quality": "high", "prompt":
               f"Character reference sheet. ART STYLE (defines the whole series): {v['style']} "
               f"Plain warm parchment background. Characters standing full body side by side, evenly spaced, clearly "
               f"separated, front three-quarter view: {chars_txt}. Absolutely no text, labels or numbers."},
              open(os.path.join(jobs, "ref.json"), "w", encoding="utf-8"), ensure_ascii=False)

    style = (f"Use EXACTLY the same art style and the same character designs as the attached reference sheet: {v['style']} "
             f"Characters (only when named): " + "; ".join(f"{n} = {d}" for n, d in v["characters"].items()) +
             ". Keep their faces, ages and clothing identical to the reference. "
             "IMPORTANT: draw a character ONLY in a panel where that character is explicitly named. Panels that do not "
             "name a character must contain NO people and NO human figures at all — landscape or still life only. ")
    panels = v["panels"]
    n_sheets = (len(panels) + 3) // 4
    for k in range(n_sheets):
        beats = panels[4*k:4*k+4]
        beats = [b if any(n in b for n in names) or "people" in b.lower() else b + ", no people, no human figures"
                 for b in beats]
        prompt = LAYOUT + style + "".join(f"Panel {i+1} ({POS[i]}): {b}. " for i, b in enumerate(beats))
        json.dump({"out": os.path.join(sheets, f"sheet_{k+1}.jpg"), "prompt": prompt, "refs": [ref], "quality": "high"},
                  open(os.path.join(jobs, f"sheet_{k+1}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"ref + {n_sheets} sheets → {jobs}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
