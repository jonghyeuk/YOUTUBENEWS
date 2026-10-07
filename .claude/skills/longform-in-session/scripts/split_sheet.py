"""2x2 스토리보드 시트를 실제 검은 구분선 위치를 찾아 4컷으로 자른다.

모델이 구분선을 정확히 정중앙에 긋지 않으므로 반으로 자르지 않고 중앙 ±6% 띠에서 색이 가장
균일한(표준편차가 가장 낮은) 행/열을 찾는다. 어두운 패널(밤 장면, 등불 장면)은 배경이 선과 이어져 선이 수백 px로 오인될 수
있어(실제로 130px 과다 크롭 발생) 선 폭을 argmin ±8px로 제한한다.

사용: python split_sheet.py <sheet.jpg> <첫 컷 번호> <panels_dir>
  예) python split_sheet.py sheets/sheet_3.jpg 9 panels  → panels/panel_09..12.jpg
"""
import sys, os
import numpy as np
from PIL import Image


def find_line(profile, lo, hi, max_half=8):
    """profile: 행/열마다 픽셀 값의 표준편차. 구분선은 색이 균일해 표준편차가 가장 낮다
    (검은 선이든 밝은 선이든 상관없음 — gpt-image-1-mini는 밝은 선을 긋기도 한다)."""
    seg = profile[lo:hi]
    thr = seg.min() + 6
    c = int(np.argmin(seg)); s = e = c
    while s - 1 >= 0 and seg[s - 1] <= thr and c - s < max_half: s -= 1
    while e + 1 < len(seg) and seg[e + 1] <= thr and e - c < max_half: e += 1
    return lo + s, lo + e + 1


def split(path, first_index, out_dir, trim=6):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32).mean(2); H, W = a.shape
    v = find_line(a.std(0), int(W * .44), int(W * .56))
    h = find_line(a.std(1), int(H * .44), int(H * .56))
    boxes = [(0, 0, v[0] - trim, h[0] - trim), (v[1] + trim, 0, W, h[0] - trim),
             (0, h[1] + trim, v[0] - trim, H), (v[1] + trim, h[1] + trim, W, H)]
    os.makedirs(out_dir, exist_ok=True)
    for i, b in enumerate(boxes):
        im.crop(b).save(os.path.join(out_dir, f"panel_{first_index + i:02d}.jpg"), quality=95)
    sizes = [(b[2] - b[0], b[3] - b[1]) for b in boxes]
    print(os.path.basename(path), "lines v", v, "h", h, "panels", sizes)
    # 컷이 시트 절반의 90% 미만이면 선 검출이 빗나간 것 — 눈으로 확인할 것
    if min(s[0] for s in sizes) < W * 0.45 or min(s[1] for s in sizes) < H * 0.45:
        print("  WARNING: 비정상적으로 작은 컷 — 시트를 직접 확인하세요")


if __name__ == "__main__":
    split(sys.argv[1], int(sys.argv[2]), sys.argv[3])
