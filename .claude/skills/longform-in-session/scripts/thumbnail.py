"""유튜브식 썸네일 만들기 — 큰 제목 + 강조색 + 두꺼운 외곽선 + 상단 태그 + 하단 소제목.

종혁님 기준: 제목은 유튜브 제목과 달라도 되고(소제목 가능), 눈에 띄어야 한다.
글씨체는 시대상을 반영해 제목은 정자체(나눔명조 ExtraBold), 태그·소제목은 굵은 고딕(Pretendard Black).

thumb.json 예:
{"bg": "panels/panel_15.jpg", "focus": "left",          # 배경에서 인물이 있는 쪽 (글씨는 반대쪽 어둡게 깔고 올림)
 "tag": "실록에 적힌 실화",
 "lines": [["떠난 다음 날,", "#FFFFFF"], ["그 집에 ", "#FFFFFF", "화가 닥쳤다", "#FFD400"]],
 "sub": "앞날을 미리 본 사람, 토정 이지함"}
lines의 각 줄은 [글자, 색, 글자, 색, …] — 한 줄 안에서 단어별로 색을 바꿀 수 있다.
사용: python thumbnail.py <work_dir>   → <work_dir>/thumbnail.jpg (1920x1080), thumbnail_yt.jpg (1280x720 업로드용)
"""
import sys, os, json
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
TITLE_FONT = os.path.join(REPO, "fonts", "NanumMyeongjo-ExtraBold.ttf")   # 정자체
GOTHIC_FONT = os.path.join(REPO, "fonts", "Pretendard-Black.otf")         # 굵은 고딕
W, H = 1920, 1080


def cover(img, w, h):
    r = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * r + 0.5), int(img.height * r + 0.5)), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def fit_size(draw, segs, font_path, max_w, start):
    size = start
    while size > 40:
        f = ImageFont.truetype(font_path, size)
        if sum(draw.textlength(t, font=f) for t, _ in segs) <= max_w:
            return f
        size -= 4
    return ImageFont.truetype(font_path, size)


def main(work):
    spec = json.load(open(os.path.join(work, "thumb.json"), encoding="utf-8"))
    bg = cover(Image.open(os.path.join(work, spec["bg"])).convert("RGB"), W, H)
    bg = ImageEnhance.Contrast(ImageEnhance.Color(bg).enhance(1.15)).enhance(1.12)

    # 글씨 쪽을 어둡게: 인물 반대편으로 그라데이션 + 전체 비네트
    focus = spec.get("focus", "left")
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        p = x / W if focus == "left" else 1 - x / W
        sd.line([(x, 0), (x, H)], fill=int(215 * max(0.0, min(1.0, (p - 0.25) / 0.5))))
    bg = Image.composite(Image.new("RGB", (W, H), (8, 6, 4)), bg, shade)
    vig = Image.new("L", (W, H), 0); vd = ImageDraw.Draw(vig)
    vd.ellipse((-W * 0.25, -H * 0.3, W * 1.25, H * 1.3), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(160))
    bg = Image.composite(bg, Image.new("RGB", (W, H), (0, 0, 0)), vig)
    bot = Image.new("L", (W, H), 0); bd = ImageDraw.Draw(bot)
    for y in range(int(H * 0.68), H):
        bd.line([(0, y), (W, y)], fill=int(200 * (y - H * 0.68) / (H * 0.32)))
    bg = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), bg, bot)

    d = ImageDraw.Draw(bg)
    area_x0 = int(W * 0.40) if focus == "left" else 60
    area_x1 = W - 60 if focus == "left" else int(W * 0.60)
    area_w = area_x1 - area_x0
    cx = (area_x0 + area_x1) // 2

    # 상단 태그: 빨간 띠 + 흰 고딕
    y = 150
    if spec.get("tag"):
        tf = ImageFont.truetype(GOTHIC_FONT, 64)
        tw = d.textlength(spec["tag"], font=tf)
        pad = 26
        d.rectangle([cx - tw / 2 - pad, y - 12, cx + tw / 2 + pad, y + 78], fill=(200, 22, 22))
        d.text((cx - tw / 2, y - 4), spec["tag"], font=tf, fill="#FFFFFF")
        y += 140

    # 메인 제목 (정자체, 줄마다 크기 맞춤, 두꺼운 검은 외곽선)
    for line in spec["lines"]:
        segs = [(line[i], line[i + 1]) for i in range(0, len(line), 2)]
        f = fit_size(d, segs, TITLE_FONT, area_w, 190)
        lw = sum(d.textlength(t, font=f) for t, _ in segs)
        x = cx - lw / 2
        asc, desc = f.getmetrics()
        for t, col in segs:
            d.text((x + 6, y + 8), t, font=f, fill=(0, 0, 0), stroke_width=14, stroke_fill=(0, 0, 0))  # 그림자
            d.text((x, y), t, font=f, fill=col, stroke_width=12, stroke_fill=(10, 8, 6))
            x += d.textlength(t, font=f)
        y += asc + desc + 18

    # 하단 소제목 (고딕)
    if spec.get("sub"):
        sf = fit_size(d, [(spec["sub"], "")], GOTHIC_FONT, W - 160, 78)
        sw = d.textlength(spec["sub"], font=sf)
        d.text(((W - sw) / 2, H - 150), spec["sub"], font=sf, fill="#FFFFFF", stroke_width=8, stroke_fill=(0, 0, 0))

    out = os.path.join(work, "thumbnail.jpg")
    bg.save(out, quality=95)
    bg.resize((1280, 720), Image.LANCZOS).save(os.path.join(work, "thumbnail_yt.jpg"), quality=95)
    print("thumbnail:", out)


if __name__ == "__main__":
    main(sys.argv[1])
