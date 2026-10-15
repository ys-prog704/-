#!/usr/bin/env python3
"""특수 무기 그림 빌드 스크립트.

이 게임을 위해 새로 그린 32×32 픽셀 그림 9종(대파 · 국자 · 효자손 · 바게트 · 삼선 슬리퍼 · 파리채 ·
고등어 · 뿅망치 · 리코더)입니다. +21 각성 그림을 그린 tools/build_awakened.py 의 도형 엔진을
32픽셀 크기로 그대로 써서, 부품마다 입체감을 계산하고 재질별 색 단계와 검은 외곽선을 입힙니다.

  1) assets/weapons/jokes/*.png 와 미리보기(preview.png)를 저장하고
  2) index.html 의 /* JOKE-SPRITES:BEGIN */ ~ /* JOKE-SPRITES:END */ 사이를
     data: URI 와 위치 정보(보통 무기 그림과 같은 P · T · g · h · s)로 다시 씁니다.

게임은 이 그림들을 무기 종류 하나("특수 무기")로 붙여서 일반 · 희귀 · 영웅 등급에서만 뽑습니다.

사용법:  pip install pillow numpy scipy
         python3 tools/build_jokes.py            (index.html 까지 갱신)
         python3 tools/build_jokes.py --preview  (그림과 미리보기만)
"""
import json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_awakened as ba                                   # noqa: E402
from build_awakened import Part, sym, ell, bez, stroke, rect  # noqa: E402
from PIL import Image                                         # noqa: E402

ba.N = 32                     # 보통 무기 그림과 같은 32×32
ba.R = ba.N * ba.SS
OUT = os.path.join(ba.ROOT, 'assets', 'weapons', 'jokes')

ba.RAMPS.update({
    'onionW':  ['#4A5240', '#7D8A6A', '#B6C2A2', '#DCE6CC', '#F2F7EA', '#FFFFFF'],
    'onionG':  ['#0E2A0E', '#1B4A18', '#2C7224', '#46992F', '#6FC043', '#A6E36F'],
    'root':    ['#3B2E1E', '#6B5636', '#9C8458', '#C9B084'],
    'bread':   ['#3A1A06', '#6A3510', '#9A5818', '#C77F2A', '#E3A548', '#F3C877'],
    'crumb':   ['#9C7A48', '#C9A66A', '#E8CC92', '#F7E6BE'],
    'fish':    ['#0A1E2A', '#123447', '#1E4F66', '#2E6E86', '#4A92A8', '#7DB8C8'],
    'belly':   ['#5E6670', '#8A939E', '#B4BCC6', '#D8DEE5', '#F2F5F8'],
    'fishDk':  ['#050C12', '#0B1A24', '#13283A'],
    'bamboo':  ['#3B2A0C', '#6A4C16', '#9A7224', '#C49A3A', '#DDBC5C', '#F0D888'],
    'redP':    ['#3A0408', '#6E0A12', '#A8141F', '#D8222C', '#F2484A', '#FF8A86'],
    'yellowP': ['#4A3200', '#7E5600', '#B88200', '#E6AE10', '#FFD23A', '#FFE98A'],
    'sole':    ['#06080E', '#0E121C', '#181E2C', '#232B3E', '#323C54'],
    'blueP':   ['#04102E', '#0A1E52', '#12307E', '#1C46AA', '#2E62D2', '#5A8AF0'],
    'stripe':  ['#9AA4B4', '#C8D0DC', '#EEF2F7', '#FFFFFF'],
    'ivory':   ['#5A4E34', '#8A7C58', '#B8AA80', '#DDD0A8', '#F2E9CC', '#FFFBEA'],
    'greenP':  ['#062A12', '#0C4A20', '#127030', '#1C9A44', '#30C25E', '#6EE08E'],
    'greenDk': ['#021208', '#062010', '#0A3018'],
    'steelDk': ['#2A2F38', '#3E4450', '#565E6C', '#727B8A'],
    'holeDk':  ['#0A0806', '#16120C', '#241D14'],
    'bambooDk': ['#2A1C06', '#45300E', '#5E4416'],
    'pinkP':   ['#3A0618', '#6E0E32', '#A81C52', '#D8337A', '#F466A2', '#FFB2D0'],
    'tear':    ['#06204A', '#0E3E84', '#1E66C2', '#4A9AF0', '#9ACCFF', '#E6F4FF'],
    'cork':    ['#4A2E14', '#7A5028', '#A8784A', '#CFA272', '#E8C79A'],
    'line':    ['#8C96A6', '#C8D0DC', '#F4F7FB'],
})


# 각 함수는 (부품들(뒤 → 앞), 손잡이 끝 v, 끝 v, 이펙트가 시작될 v) — v 는 손잡이 → 끝, u 는 가로(+u 는 그림 오른쪽 아래)
def daepa():
    """대파 — 수염뿌리, 흰 대, 세 갈래 초록 잎"""
    parts = []
    for a, b in ((-1.2, -2.4), (0, -0.6), (1.1, 2.2)):
        parts.append(Part(stroke(bez((a * 0.4, -13.2), (a * 0.7, -14.6), (b * 0.8, -15.6), (b, -17)), 0.9, 0.5), 'root', 'flat', bias=0.1))
    parts.append(Part(ell(0, -12.6, 2.1, 1.6), 'onionW', 'dome'))
    parts.append(Part(sym([(1.9, -12.8), (2.0, -6), (1.8, 2), (1.7, 4)]), 'onionW', 'dome'))
    parts.append(Part(sym([(1.75, 2), (1.8, 7), (1.7, 9)]), 'onionG', 'dome'))
    parts.append(Part(stroke(bez((-0.6, 8), (-1.4, 12), (-3.6, 15.5), (-5.6, 18.4)), 2.0, 0.7), 'onionG', 'bevel', bevel=0.9))
    parts.append(Part(stroke(bez((0.7, 8), (1.6, 12.5), (3.4, 15), (5.0, 17.2)), 2.0, 0.7), 'onionG', 'bevel', bevel=0.9))
    parts.append(Part(stroke(bez((0, 8), (0.2, 13), (-0.2, 17), (0.4, 21)), 2.2, 0.8), 'onionG', 'bevel', bevel=0.9))
    return parts, -17, 21, 3


def ladle():
    """국자 — 걸이 구멍 손잡이, 넓고 오목한 국자 머리(안쪽이 어둡게 보임)"""
    parts = [Part(stroke([(0, -16.0), (0, 0), (0.4, 6.0), (1.2, 7.6)], 1.7, 1.4), 'silver', 'dome'),
             Part(ell(0, -15.6, 1.7, 1.7), 'silver', 'dome'),
             Part(ell(0, -15.6, 0.7, 0.7), 'holeDk', 'flat', weight=3),
             Part(ell(0.6, 12.0, 5.4, 4.4), 'silver', 'dome'),
             Part(ell(0.2, 12.2, 4.1, 3.2), 'steelDk', 'dome', weight=2.2, amb=0.35),
             Part(ell(-1.4, 11.2, 1.4, 0.9, rot=-20), 'silver', 'flat', bias=0.35, weight=2.6)]
    return parts, -17.4, 16.6, 7


def scratcher():
    """효자손 — 마디 있는 대나무 자루, 끝에 손가락 셋이 갈라진 손(손가락 끝은 긁기 좋게 굽음)"""
    parts = [Part(sym([(0.85, -17.5), (0.95, 11.5)]), 'bamboo', 'dome')]
    for v in (-11, -3, 4.5):
        parts.append(Part(sym([(1.3, v - 0.45), (1.3, v + 0.45)]), 'bambooDk', 'dome', weight=1.8))
    parts.append(Part(ell(0, -16.6, 1.2, 1.2), 'bambooDk', 'dome'))
    parts.append(Part(sym([(1.0, 10.6), (2.7, 12.6), (3.3, 14.6), (3.3, 15.4)]), 'bamboo', 'dome'))
    for u in (-2.2, 0, 2.2):
        parts.append(Part(stroke(bez((u, 14.8), (u, 17.0), (u + 0.3, 18.6), (u + 1.2, 19.6)), 1.6, 1.2), 'bamboo', 'dome', weight=1.4))
    for u in (-1.1, 1.1):
        parts.append(Part(stroke([(u, 15.4), (u + 0.1, 17.4), (u + 0.4, 18.4)], 0.55), 'bambooDk', 'flat', weight=3))
    return parts, -17.5, 19.8, 10.6


def baguette():
    """바게트 — 길쭉한 빵과 비스듬한 칼집 자국"""
    parts = [Part(sym([(0.6, -17.4), (1.9, -16.4), (2.7, -13.5), (2.9, -6), (2.9, 9), (2.7, 15.5), (1.9, 18.6), (0.6, 19.6)]),
                  'bread', 'dome')]
    for v in (-12, -6.5, -1, 4.5, 10, 15):
        parts.append(Part(stroke([(-1.6, v), (-0.2, v + 1.4), (1.6, v + 2.6)], 1.0, 0.8), 'crumb', 'dome', weight=2.2))
    return parts, -17.4, 19.6, -10


def slipper():
    """삼선 슬리퍼 — 고무 밑창, 파란 발등 덮개에 흰 줄 셋"""
    parts = [Part(sym([(1.6, -16.4), (2.8, -14.8), (3.4, -10), (3.3, -2), (3.7, 6), (3.9, 11), (3.4, 15), (2.2, 17.4), (0, 18.2)]),
                  'sole', 'bevel', bevel=1.0),
             Part(rect(-4.4, 4.4, 3.2, 12.2), 'blueP', 'dome', weight=1.4)]
    for v in (4.6, 7.2, 9.8):
        parts.append(Part(rect(-4.2, 4.2, v, v + 1.0), 'stripe', 'flat', bias=0.2, weight=3))
    return parts, -16.4, 18.2, 2


def swatter():
    """파리채 — 가는 자루와 구멍 뚫린 그물 머리"""
    parts = [Part(sym([(0.75, -15.4), (0.8, 4)]), 'greenP', 'dome'),
             Part(ell(0, -16.2, 1.5, 1.5), 'greenP', 'dome'),
             Part(ell(0, -16.2, 0.6, 0.6), 'dark', 'flat', weight=3),
             Part(sym([(2.0, 3.6), (4.4, 5.4), (4.9, 9), (4.9, 15), (4.3, 18), (2.4, 19.4), (0, 19.8)]), 'greenP', 'bevel', bevel=0.8)]
    for u in (-2.6, -0.85, 0.85, 2.6):
        for v in (7.0, 9.6, 12.2, 14.8, 17.2):
            if abs(u) > 2 and v > 16.5:
                continue
            parts.append(Part(rect(u - 0.42, u + 0.42, v - 0.42, v + 0.42), 'greenDk', 'flat', weight=3))
    return parts, -17.7, 19.8, 4


def mackerel():
    """고등어 — 꼬리를 잡고 휘두르는 푸른 등 생선 (눈 · 아가미 · 등 무늬)"""
    parts = [Part([(0, -11.2), (3.9, -16.6), (2.6, -12.6), (0, -13.4), (-2.6, -12.6), (-3.9, -16.6)], 'fish', 'bevel', bevel=0.8),
             Part(sym([(0.9, -12.4), (1.1, -9.5)]), 'fish', 'dome'),
             Part([(-1.0, 1), (-4.6, 4.5), (-3.2, 7.5), (-1.0, 7)], 'fish', 'bevel', bevel=0.7),
             Part(sym([(1.1, -9.5), (2.4, -5), (3.2, 1), (3.3, 7), (2.8, 11.5), (1.8, 14.6), (0.6, 16.6), (0, 17)]), 'fish', 'dome'),
             Part([(0.3, -7), (2.3, -4.5), (3.0, 1), (3.1, 7), (2.6, 11.4), (1.6, 14.4), (0.3, 15.8)], 'belly', 'dome', weight=1.3)]
    for v in (-5, -1, 3):
        parts.append(Part(stroke(bez((-0.4, v), (-1.4, v + 0.8), (-1.8, v + 2.0), (-2.6, v + 2.6)), 0.8, 0.6), 'fishDk', 'flat', weight=2))
    parts += [Part(ell(-0.6, 12.6, 1.05, 1.05), 'belly', 'dome', weight=2.5),
              Part(ell(-0.6, 12.7, 0.55, 0.55), 'dark', 'dome', weight=3.5),
              Part(stroke([(1.2, 11.0), (2.2, 9.6), (2.8, 8.2)], 0.6), 'fishDk', 'flat', weight=2.2)]
    return parts, -16.6, 17, -9


def squeak():
    """뿅망치 — 노란 자루, 주름진 빨간 머리, 양쪽 노란 마개"""
    parts = [Part(sym([(1.05, -17), (1.15, 7.5)]), 'yellowP', 'dome'),
             Part(ell(0, -16.6, 1.4, 1.2), 'yellowP', 'dome'),
             Part(rect(-6.6, 6.6, 7.0, 14.4), 'redP', 'dome')]
    for u in (-3.4, 0, 3.4):
        parts.append(Part(rect(u - 0.35, u + 0.35, 7.2, 14.2), 'redP', 'flat', bias=-0.18, weight=1.6))
    parts += [Part(rect(5.6, 7.6, 6.4, 15.0), 'yellowP', 'dome', weight=1.5),
              Part(rect(-7.6, -5.6, 6.4, 15.0), 'yellowP', 'dome', weight=1.5)]
    return parts, -17, 15, 7


def recorder():
    """리코더 — 납작한 부리, 이음매 두 군데, 손가락 구멍, 활짝 벌어진 나팔"""
    parts = [Part(sym([(0.9, -16.8), (1.6, -15.6), (1.7, -11.8)]), 'ivory', 'dome'),
             Part(sym([(2.0, -11.9), (2.0, -10.4)]), 'ivory', 'dome', bias=-0.12, weight=1.6),
             Part(sym([(1.7, -10.5), (1.7, 8.6)]), 'ivory', 'dome'),
             Part(sym([(2.0, 8.5), (2.0, 10.0)]), 'ivory', 'dome', bias=-0.12, weight=1.6),
             Part(sym([(1.6, 10.0), (2.1, 13.0), (3.0, 15.6), (3.6, 17.0)]), 'ivory', 'dome'),
             Part(sym([(2.6, 16.2), (3.6, 17.0)]) + [(0, 17.4)], 'holeDk', 'flat', weight=1.2),
             Part(rect(-0.8, 0.8, -14.4, -13.2), 'holeDk', 'flat', weight=3)]
    for v in (-6.5, -2.5, 1.5, 5.5):
        parts.append(Part(ell(-0.3, v, 0.5, 0.5), 'holeDk', 'flat', weight=3))
    return parts, -16.8, 17.4, -10


# ── 전설: 친구들 이름이 붙은 무기 (속성과 상관없이 셋 중 하나가 똑같은 확률로) ──
def pic(u0, v0, down, right):
    """(u0, v0) 에서 그림 기준 아래로 down, 오른쪽으로 right 만큼 간 점 — 매달린 물건을 똑바로 세울 때."""
    k = math.sqrt(.5)
    return (u0 + (down + right) * k, v0 + (right - down) * k)


def heart_half(cv, s, side, crack):
    """하트 반쪽(side=-1 왼쪽, +1 오른쪽). 뾰족한 끝이 손잡이 쪽. crack 은 가운데 갈라진 선(위 → 아래)."""
    pts = []
    for i in range(25):
        t = math.pi * i / 24                                    # 0 = 위쪽 오목한 곳 → π = 아래 뾰족한 끝
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((side * x * s, cv + y * s))
    return pts + [(u, v) for u, v in reversed(crack)][1:-1]


def solo_staff():
    """정수의 솔로 지팡이 — 나무 지팡이 끝에 쩍 갈라진 분홍 하트, 눈물 한 방울"""
    s, cv = 0.40, 12.6
    top, bot = cv + 5 * s, cv - 17 * s
    crack = [(0, top), (1.1, top - 1.8), (-0.9, top - 3.8), (1.0, top - 5.8), (-0.8, top - 7.8), (0.4, bot + 1.4), (0, bot)]
    left = [(u - 0.45, v + 0.35) for u, v in heart_half(cv, s, -1, crack)]
    right = [(u + 0.45, v - 0.1) for u, v in heart_half(cv, s, 1, crack)]
    parts = [Part(sym([(0.9, -17.2), (1.0, bot + 0.6)]), 'wood', 'dome'),
             Part(ell(0, -16.9, 1.3, 1.3), 'wood', 'dome'),
             Part(sym([(1.5, -9.6), (1.5, -8.4)]), 'gold', 'dome', weight=1.6),
             Part(left, 'pinkP', 'dome', weight=1.2),
             Part(right, 'pinkP', 'dome', weight=1.2),
             Part(ell(-2.6, cv + 1.4, 0.9, 0.6, rot=-40), 'pinkP', 'flat', bias=0.4, weight=2.4),
             Part(stroke([(u * 1.1, v) for u, v in crack[:-1]], 0.55), 'holeDk', 'flat', weight=3)]
    c = pic(4.2, cv - 2.2, 3.2, 1.2)
    parts.append(Part([pic(c[0], c[1], -1.5, 0)] + [pic(c[0], c[1], 0.3 + 0.7 * math.sin(math.radians(a)), 0.75 * math.cos(math.radians(a)))
                                                     for a in range(-20, 210, 15)], 'tear', 'dome', weight=2))
    parts[-1].pts = [(c[0] + (u - c[0]) * 1.5, c[1] + (v - c[1]) * 1.5) for u, v in parts[-1].pts]
    return parts, -17.2, top + 0.6, 6


def fishing_rod():
    """소헌이의 낚싯대 — 코르크 손잡이, 릴, 금색 가이드, 줄 끝에 걸려 올라온 삼선 슬리퍼"""
    parts = [Part(stroke([(0, -16.0), (0, -9.0)], 2.5, 2.2), 'cork', 'dome'),
             Part(ell(0, -16.6, 1.5, 1.3), 'sole', 'dome'),
             Part(stroke([(0, -9.2), (0, 6), (0, 18.6)], 1.3, 0.45), 'blueP', 'dome'),
             Part(sym([(1.0, -9.4), (1.0, -8.2)]), 'gold', 'dome', weight=1.6),
             Part(stroke([(0.6, -6.6), (2.2, -6.2)], 0.8), 'silver', 'dome'),
             Part(ell(3.1, -6.4, 1.8, 1.8), 'silver', 'dome'),
             Part(ell(3.1, -6.4, 0.7, 0.7), 'steelDk', 'dome', weight=2.4),
             Part(stroke([(3.1, -6.4), (4.4, -4.8)], 0.55), 'gold', 'flat', weight=2)]
    for v in (-1.5, 5.5, 12.0, 17.2):
        parts.append(Part(ell(0.75, v, 0.45, 0.45), 'gold', 'dome', weight=2.2))
    tip = (0.3, 18.6)
    end = pic(tip[0], tip[1], 5.4, 0)
    parts.append(Part(stroke([tip, pic(tip[0], tip[1], 2.7, 0.2), end], 0.45), 'line', 'flat', bias=0.2, weight=1.4))
    # 슬리퍼: 걸린 쪽(뒤꿈치 끈)이 위, 발끝이 아래로 늘어짐. 그림 기준으로 똑바로 세워서 그림
    L, W = 11.0, 2.9
    sole = []
    for a in range(0, 360, 10):
        t = (1 - math.cos(math.radians(a))) / 2                  # 0 = 뒤꿈치(위) → 1 = 발끝(아래)
        wide = W * (0.78 + 0.3 * t) * (abs(math.sin(math.radians(a))) ** 0.6)
        sole.append(pic(end[0], end[1], 0.6 + L * t, wide if a < 180 else -wide))
    parts.append(Part(sole, 'sole', 'bevel', bevel=0.9))
    strap = [pic(end[0], end[1], d, side * (W + 0.25)) for d, side in ((1.3, -1), (1.3, 1), (6.2, 1), (6.2, -1))]
    parts.append(Part(strap, 'blueP', 'dome', weight=1.4))
    for d in (2.5, 3.8, 5.1):
        parts.append(Part([pic(end[0], end[1], d - 0.28, -W), pic(end[0], end[1], d - 0.28, W), pic(end[0], end[1], d + 0.28, W), pic(end[0], end[1], d + 0.28, -W)],
                          'stripe', 'flat', bias=0.25, weight=3))
    parts.append(Part(stroke([pic(end[0], end[1], -0.2, 0), pic(end[0], end[1], 1.0, 0.5), pic(end[0], end[1], 1.4, -0.3)], 0.45), 'silver', 'flat', weight=2.5))
    return parts, -17.0, 18.6, 4


def bone_sword():
    """현근이의 뼈다귀검 — 칼날이 커다란 뼈다귀(한입 베어 문 자국), 코등이는 빨간 강아지 목줄과 금색 이름표"""
    w = 1.9
    left = []                                                    # -u 쪽 가장자리: 위(끝) → 아래, 가운데쯤 이빨 자국 두 개
    for i in range(81):
        v = 13.2 - 20.4 * i / 80
        d = 0.0
        if abs(v - 5.0) < 2.7:                                   # 크게 한입 + 가장자리에 이빨 자국(물결)
            d = max(0.0, math.sqrt(2.7 ** 2 - (v - 5.0) ** 2) - 0.55 * abs(math.sin(math.pi * (v - 5.0) / 1.35)))
        left.append((-w + d, v))
    shaft = [(w, -7.2), (w, 13.2)] + left
    parts = []
    parts += ba.grip(-16.4, -9.2, 1.25, 'leather', 'bone', 3)
    parts.append(Part(ell(0, -17.0, 1.6, 1.4), 'bone', 'dome'))
    for u in (-1.7, 1.7):
        parts.append(Part(ell(u, -6.4, 2.0, 1.9), 'bone', 'dome'))
    parts.append(Part(shaft, 'bone', 'dome'))
    for u in (-1.75, 1.75):
        parts.append(Part(ell(u, 14.6, 2.2, 2.2), 'bone', 'dome'))
    parts.append(Part(ell(0, 13.9, 1.7, 1.4), 'bone', 'dome'))
    parts.append(Part(rect(-4.6, 4.6, -9.6, -7.6), 'redP', 'dome', weight=1.3))
    for u in (-3.0, -1.0, 1.0, 3.0):
        parts.append(Part(ell(u, -8.6, 0.35, 0.35), 'yellowP', 'flat', bias=0.3, weight=3))
    tag = pic(0.6, -9.6, 1.8, 0)
    parts.append(Part(stroke([(0.6, -9.4), tag], 0.4), 'gold', 'flat', weight=2))
    parts.append(Part(ell(tag[0], tag[1], 1.25, 1.25), 'gold', 'dome', weight=1.6))
    return parts, -17.4, 16.8, -7


# (키, 등급 0 일반 · 1 희귀 · 2 영웅 · 3 전설, 한국어 이름, 그리는 함수[, 전설 별칭])
DESIGNS = [
    ('jkDaepa',     0, '대파',        daepa),
    ('jkLadle',     0, '국자',        ladle),
    ('jkScratcher', 0, '효자손',      scratcher),
    ('jkBaguette',  1, '바게트',      baguette),
    ('jkSlipper',   1, '삼선 슬리퍼', slipper),
    ('jkSwatter',   1, '파리채',      swatter),
    ('jkMackerel',  2, '고등어',      mackerel),
    ('jkSqueak',    2, '뿅망치',      squeak),
    ('jkRecorder',  2, '리코더',      recorder),
    ('jkSoloStaff', 3, '정수의 솔로 지팡이', solo_staff,  '혼자라서 더 강하다'),
    ('jkFishRod',   3, '소헌이의 낚싯대',   fishing_rod, '월척 대신 슬리퍼'),
    ('jkBoneSword', 3, '현근이의 뼈다귀검', bone_sword,  '동네 강아지들이 줄을 선다'),
]


def preview(sheet, z=8):
    """그대로 · 서리 · 핏빛으로 물들인 모습(게임의 보통 무기 물들이기와 같은 계산)을 나란히."""
    els = [None, ('#123A52', '#7FD4F5', '#F0FCFF'), ('#3A060C', '#E8304A', '#FFB8C0')]
    W = len(sheet) * (ba.N + 4) * z
    out = Image.new('RGBA', (W, len(els) * (ba.N + 4) * z), (24, 20, 17, 255))
    for col, (key, img) in enumerate(sheet):
        for row, el in enumerate(els):
            im = img if el is None else tint(img, el, 0.6)
            out.alpha_composite(im.resize((ba.N * z, ba.N * z), Image.NEAREST), (col * (ba.N + 4) * z + 2 * z, row * (ba.N + 4) * z + 2 * z))
    out.save(os.path.join(OUT, 'preview.png'))


def tint(img, el, k):
    A, B, C = (ba.hexrgb(c) for c in el)
    im = img.copy()
    px = im.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            r, g, b, a = px[x, y]
            if not a:
                continue
            hi, lo = max(r, g, b), min(r, g, b)
            sat = (hi - lo) / hi if hi else 0
            if sat > .28 or hi < 40:
                continue
            l = (r * .3 + g * .59 + b * .11) / 255
            m = [A[i] + (B[i] - A[i]) * l * 2 for i in range(3)] if l < .5 else [B[i] + (C[i] - B[i]) * (l - .5) * 2 for i in range(3)]
            w = k * (1 - sat / .56)
            px[x, y] = (int(r + (m[0] - r) * w), int(g + (m[1] - g) * w), int(b + (m[2] - b) * w), a)
    return im


def build():
    os.makedirs(OUT, exist_ok=True)
    data, pools, sheet = {}, [[], [], [], []], []
    for key, rar, ko, fn, *rest in DESIGNS:
        parts, vmin, vmax, vg = fn()
        org, sc = ba.place(parts, vmin, vmax)
        img, _ = ba.render(parts, org, sc)
        img.save(os.path.join(OUT, key + '.png'), optimize=True)
        P = ba.to_tile(0, vmin, org, sc); T = ba.to_tile(0, vmax, org, sc)
        g = (vg - vmin) * sc
        h, s = ba.blade_half(img, P, T, g)
        data[key] = {'P': [round(P[0], 2), round(P[1], 2)], 'T': [round(T[0], 2), round(T[1], 2)],
                     'g': round(g, 2), 'h': h, 's': s, 'ko': ko, 'src': ba.uri(img)}
        if rest:
            data[key]['epi'] = rest[0]
        pools[rar].append(key)
        sheet.append((key, img))
        print('  %-12s %-7s 배율 %.2f  P=%s T=%s g=%.1f h=%.1f  %4d B' % (key, ko, sc, data[key]['P'], data[key]['T'], g, h, len(data[key]['src'])))
    preview(sheet)
    with open(os.path.join(OUT, 'CREDITS.md'), 'w', encoding='utf-8') as f:
        f.write('# 특수 무기 그림\n\n이 게임을 위해 새로 그린 그림입니다(tools/build_jokes.py 가 도형으로 그림). '
                '[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) — 자유롭게 쓸 수 있습니다.\n\n'
                '| 파일 | 이름 | 등급 |\n| --- | --- | --- |\n' +
                '\n'.join('| `%s.png` | %s | %s |' % (k, ko, ['일반', '희귀', '영웅', '전설'][r]) for k, r, ko, *_ in DESIGNS) + '\n')
    return data, pools


def inject(data, pools):
    block = ('/* JOKE-SPRITES:BEGIN */\n'
             '  /* 특수 무기 그림 — tools/build_jokes.py 가 만듭니다. 직접 고치지 마세요. JOKE_POOLS[등급] = 일반 · 희귀 · 영웅 · 전설 */\n'
             '  var JOKE_DATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n'
             '  var JOKE_POOLS = ' + json.dumps(pools, separators=(',', ':')) + ';\n'
             '  /* JOKE-SPRITES:END */')
    p = os.path.join(ba.ROOT, 'index.html')
    s = open(p, encoding='utf-8').read()
    pat = re.compile(r'/\* JOKE-SPRITES:BEGIN \*/.*?/\* JOKE-SPRITES:END \*/', re.S)
    if not pat.search(s):
        sys.exit('index.html 에 JOKE-SPRITES 표시가 없습니다.')
    s = pat.sub(lambda m: block, s, count=1)
    open(p, 'w', encoding='utf-8').write(s)
    print('index.html 갱신 (%d KB)' % (len(block) // 1024))


if __name__ == '__main__':
    d, pl = build()
    if '--preview' not in sys.argv:
        inject(d, pl)
