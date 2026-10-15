#!/usr/bin/env python3
"""홈 화면 앱 아이콘 빌드 스크립트.

+21 각성 용검 그림(assets/weapons/awakened/aw_sword_dragon.png)을 밤의 대장간 배경 위에 올려
assets/app/ 에 앱 아이콘을 만듭니다.

  icon-192.png · icon-512.png      — 보통 아이콘 (가장자리까지 꽉 찬 사각형)
  icon-maskable-512.png            — 안드로이드가 원 · 둥근 사각형으로 잘라 쓰는 아이콘
                                     (그림이 가운데 80% 원 안에 들어가게 조금 작게)
  apple-touch-icon.png (180)       — 아이폰 홈 화면 (모서리는 아이폰이 둥글게 자름)

사용법:  pip install pillow
         python3 tools/build_icons.py
"""
import os
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'assets', 'weapons', 'awakened', 'aw_sword_dragon.png')
OUT = os.path.join(ROOT, 'assets', 'app')

INK = (16, 14, 12)          # --ink
IRON = (34, 28, 23)         # --iron-2
EMBER = (255, 122, 46)      # 불씨 색


def background(n):
    """위는 조금 밝고 아래는 어두운 쇠 빛, 가운데에 불씨 빛."""
    bg = Image.new('RGB', (n, n), INK)
    d = ImageDraw.Draw(bg)
    for y in range(n):
        t = y / (n - 1)
        c = tuple(round(IRON[i] * (1 - t) + INK[i] * t) for i in range(3))
        d.line([(0, y), (n, y)], fill=c)
    glow = Image.new('L', (n, n), 0)
    gd = ImageDraw.Draw(glow)
    r = n * .36
    gd.ellipse([n / 2 - r, n * .54 - r, n / 2 + r, n * .54 + r], fill=150)
    glow = glow.filter(ImageFilter.GaussianBlur(n * .16))
    bg.paste(Image.new('RGB', (n, n), EMBER), (0, 0), glow)
    return bg


def sprite_box(img):
    """투명하지 않은 부분의 상자."""
    return img.getchannel('A').point(lambda a: 255 if a > 8 else 0).getbbox()


def icon(n, fill):
    """fill = 그림의 긴 변이 아이콘 크기에서 차지할 비율."""
    src = Image.open(SRC).convert('RGBA')
    src = src.crop(sprite_box(src))
    scale = max(1, int(n * fill / max(src.size)))          # 픽셀이 뭉개지지 않게 정수 배
    sp = src.resize((src.width * scale, src.height * scale), Image.NEAREST)
    bg = background(n).convert('RGBA')
    x, y = (n - sp.width) // 2, (n - sp.height) // 2
    # 그림 뒤의 불빛 테두리
    halo = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    a = Image.new('L', (n, n), 0)
    a.paste(sp.getchannel('A'), (x, y))
    a = a.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(n * .03))
    halo.paste((255, 150, 70, 255), (0, 0), a.point(lambda v: v * 3 // 4))
    bg = Image.alpha_composite(bg, halo)
    bg.alpha_composite(sp, (x, y))
    return bg.convert('RGB')


def build():
    os.makedirs(OUT, exist_ok=True)
    big = icon(1024, .74)
    for size, name in [(512, 'icon-512.png'), (192, 'icon-192.png'), (180, 'apple-touch-icon.png')]:
        big.resize((size, size), Image.LANCZOS).save(os.path.join(OUT, name), optimize=True)
    # 마스커블: 가운데 지름 80% 원 안에 들어가게 (대각선 그림이라 긴 변 56% 이하)
    icon(1024, .56).resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, 'icon-maskable-512.png'), optimize=True)
    print('assets/app/: icon-192 · icon-512 · icon-maskable-512 · apple-touch-icon')


if __name__ == '__main__':
    build()
