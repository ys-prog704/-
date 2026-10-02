#!/usr/bin/env python3
"""+21 각성 무기 그림 빌드 스크립트.

이 게임을 위해 새로 그린 64×64 픽셀 그림 15종(무기 종류마다 3가지)입니다. 손으로 찍는 대신
도형(다각형·곡선)으로 무기를 설계하고, 부품마다 입체감(칼날 능선·테두리 경사·둥근 보석)을
계산해 8배 크게 그린 뒤 64×64 로 줄이고, 재질별 색 단계와 검은 외곽선을 입힙니다.

  1) assets/weapons/awakened/*.png 와 미리보기(preview.png)를 저장하고
  2) index.html 의 /* AWAKEN-SPRITES:BEGIN */ ~ /* AWAKEN-SPRITES:END */ 사이를
     data: URI 와 위치 정보로 다시 씁니다.

칼날·빛나는 부분처럼 속성 색으로 물들일 픽셀은 마스크(m)로 따로 담습니다.
게임은 그 픽셀만 밝기에 따라 속성 색(그림자 → 본색 → 하이라이트 → 흰빛)으로 바꾸고,
금장식·보석·나무·뼈는 그대로 둡니다.

사용법:  pip install pillow numpy scipy
         python3 tools/build_awakened.py            (index.html 까지 갱신)
         python3 tools/build_awakened.py --preview  (그림과 미리보기만)
"""
import base64, io, json, math, os, re, sys
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'assets', 'weapons', 'awakened')
N, SS = 64, 8                      # 결과 크기, 슈퍼샘플링 배율
R = N * SS
LIGHT = np.array([-1.0, -1.15, 1.25]); LIGHT /= np.linalg.norm(LIGHT)      # 왼쪽 위에서 오는 빛
HALF = LIGHT + np.array([0.0, 0.0, 1.0]); HALF /= np.linalg.norm(HALF)
AX = np.array([math.sqrt(.5), -math.sqrt(.5)])   # v: 손잡이 → 끝 (그림에서 오른쪽 위)
NX = np.array([math.sqrt(.5), math.sqrt(.5)])    # u: 가로 (+u 는 그림에서 오른쪽 아래)
OUTLINE = (11, 8, 16)


def hexrgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# 재질별 색 단계 (어두움 → 밝음). steel·energy 는 게임에서 속성 색으로 바뀝니다(밝기만 씀).
RAMPS = {
    'steel':   ['#1B1E25', '#353A45', '#555C69', '#7C8491', '#A6AEBA', '#CED4DD', '#EEF1F5', '#FFFFFF'],
    'energy':  ['#3C424C', '#5F6672', '#8C939E', '#B8BEC7', '#DDE1E7', '#F5F7FA', '#FFFFFF'],
    'silver':  ['#23232B', '#3E3F4A', '#60636F', '#868A96', '#AEB2BC', '#D3D6DD', '#F1F2F5'],
    'gold':    ['#3A1C06', '#64360C', '#985714', '#C9801F', '#EBAA33', '#F9D162', '#FFEDA6', '#FFFBE6'],
    'dark':    ['#0E0915', '#1B1229', '#2A1D3F', '#3D2B58', '#554076', '#715A96'],
    'bone':    ['#3F3426', '#6A5A44', '#968467', '#BFAE8E', '#DED2B6', '#F5EEDC'],
    'wood':    ['#24130A', '#3F2412', '#5E381D', '#80502B', '#A46C3D', '#C38D58'],
    'leather': ['#1A0C09', '#341A12', '#53291B', '#723B27', '#8F5135'],
    'red':     ['#2A0306', '#55070F', '#8C0E1C', '#C2182B', '#E8384A', '#FF7A86'],
    'gemR':    ['#2C0008', '#5E0014', '#9E0C27', '#DA2440', '#FF5A6E', '#FFB2BC', '#FFFFFF'],
    'gemB':    ['#00082A', '#001C58', '#06379A', '#165FD8', '#3E95FF', '#A8D6FF', '#FFFFFF'],
    'gemG':    ['#001A0C', '#003A1C', '#086A32', '#16A04C', '#3ED872', '#A8F5BE', '#FFFFFF'],
    'gemP':    ['#16002A', '#320058', '#5A0E96', '#8A26D2', '#B85CFF', '#DEB2FF', '#FFFFFF'],
    'leaf':    ['#06200C', '#0E3A16', '#18602A', '#2A8A3C', '#4CB858', '#8EE08A'],
    'rock':    ['#120E0E', '#231B1A', '#382B28', '#4F3D38', '#6A534B', '#86695E'],
}
TINTED = {'steel', 'energy'}


class Part:
    """하나의 부품. prof: ridge(칼날 능선) · bevel(테두리 경사) · dome(둥근 면) · flat · const(고정 밝기)"""
    def __init__(self, pts, mat, prof='bevel', bevel=1.6, k=1.0, amb=None, weight=1.0, tint=None,
                 bias=0.0, spec=0.6, const=None):
        self.pts, self.mat, self.prof, self.bevel, self.k = pts, mat, prof, bevel, k
        self.amb = amb if amb is not None else (0.28 if prof == 'ridge' else 0.22)
        self.weight, self.bias, self.spec, self.const = weight, bias, spec, const
        self.tint = (mat in TINTED) if tint is None else tint


class Spark:
    """떠 있는 반짝이 — 그림 격자에 맞춘 + 모양 (외곽선 없음, 속성 색으로 물듦)"""
    def __init__(self, cu, cv, size=1):
        self.cu, self.cv, self.size = cu, cv, size
        self.pts = [(cu, cv)]


# ── 도형 도우미 (u: 가로, v: 손잡이 → 끝 방향, 단위는 결과 그림의 픽셀) ──
def sym(right):
    """오른쪽(+u) 반쪽 점들로 좌우 대칭 다각형 (v 가 커지는 순서로)."""
    return [(u, v) for u, v in right] + [(-u, v) for u, v in reversed(right)]


def mirror(pts):
    return [(-u, v) for u, v in pts]


def ell(cu, cv, ru, rv, rot=0.0, n=40, a0=0.0, a1=360.0):
    out = []
    full = abs(a1 - a0) >= 360
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    for i in range(n if full else n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        x, y = ru * math.cos(a), rv * math.sin(a)
        out.append((cu + x * c - y * s, cv + x * s + y * c))
    return out


def bez(p0, p1, p2, p3, n=16):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def stroke(path, w0, w1=None):
    """중심선을 따라 두께 w0 → w1 로 바뀌는 띠 (뿔·덩굴·빛줄기)."""
    w1 = w0 if w1 is None else w1
    left, right = [], []
    for i, (x, y) in enumerate(path):
        a = path[max(0, i - 1)]; b = path[min(len(path) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        w = (w0 + (w1 - w0) * i / max(1, len(path) - 1)) / 2
        left.append((x + nx * w, y + ny * w)); right.append((x - nx * w, y - ny * w))
    return left + right[::-1]


def star(cu, cv, r0, r1, n=4, rot=0.0):
    out = []
    for i in range(n * 2):
        r = r1 if i % 2 == 0 else r0
        a = math.radians(rot + 180 * i / n)
        out.append((cu + r * math.sin(a), cv + r * math.cos(a)))
    return out


def crescent(c1, r1, c2, r2, n=28):
    """원 c1(반지름 r1)에서 원 c2(r2)를 도려낸 초승달. 두 원이 만나는 곳이 뾰족한 끝."""
    (x1, y1), (x2, y2) = c1, c2
    d = math.hypot(x2 - x1, y2 - y1)
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, r1 * r1 - a * a))
    mx, my = x1 + a * (x2 - x1) / d, y1 + a * (y2 - y1) / d
    p0 = (mx + h * (y2 - y1) / d, my - h * (x2 - x1) / d)
    p1 = (mx - h * (y2 - y1) / d, my + h * (x2 - x1) / d)
    away = math.degrees(math.atan2(y1 - y2, x1 - x2))          # c2 반대쪽 (초승달의 두꺼운 쪽)

    def arc(c, r, qa, qb):
        s = math.degrees(math.atan2(qa[1] - c[1], qa[0] - c[0]))
        e = math.degrees(math.atan2(qb[1] - c[1], qb[0] - c[0]))
        ccw = (e - s) % 360
        span = ccw if (away - s) % 360 <= ccw else ccw - 360
        return [(c[0] + r * math.cos(math.radians(s + span * i / n)), c[1] + r * math.sin(math.radians(s + span * i / n)))
                for i in range(n + 1)]
    return arc(c1, r1, p0, p1) + arc(c2, r2, p1, p0)[1:-1]


def grip(v0, v1, w, mat='leather', band='gold', n=3, bw=0.55):
    parts = [Part(sym([(w, v0), (w, v1)]), mat, 'dome')]
    for i in range(n):
        v = v0 + (v1 - v0) * (i + 0.5) / n
        parts.append(Part(sym([(w + 0.55, v - bw), (w + 0.55, v + bw)]), band, 'dome', weight=1.6))
    return parts


def jewel(cu, cv, r, gem='gemB', setting='gold', ring=1.1, weight=2.0):
    return [Part(ell(cu, cv, r + ring, r + ring), setting, 'dome'),
            Part(ell(cu, cv, r, r), gem, 'dome', weight=weight, spec=0.9)]


def rect(u0, u1, v0, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


# ── 그리기 ──
def to_tile(u, v, org, sc=1.0):
    return org + (AX * v + NX * u) * sc


def raster(pts, org, sc):
    img = Image.new('L', (R, R), 0)
    ImageDraw.Draw(img).polygon([tuple(to_tile(u, v, org, sc) * SS) for u, v in pts], fill=255)
    return np.asarray(img) > 127


def shade(mask, P, sc):
    if P.const is not None:
        return np.full(mask.shape, float(P.const))
    d = ndimage.distance_transform_edt(mask) / SS / sc
    if P.prof == 'ridge':
        h = d
    elif P.prof == 'bevel':
        h = np.minimum(d, P.bevel)
    elif P.prof == 'dome':
        Rr = max(d.max(), 0.5)
        h = np.sqrt(np.clip(2 * Rr * d - d * d, 0, None))
    else:
        h = np.zeros_like(d)
    h = ndimage.gaussian_filter(h, SS * 0.18)
    gy, gx = np.gradient(h)
    gx *= SS * sc * P.k; gy *= SS * sc * P.k
    nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1)
    nxx, nyy = -gx * nz, -gy * nz
    dif = np.clip(nxx * LIGHT[0] + nyy * LIGHT[1] + nz * LIGHT[2], 0, 1)
    spec = np.clip(nxx * HALF[0] + nyy * HALF[1] + nz * HALF[2], 0, 1) ** 28
    return P.amb + (1 - P.amb) * dif + P.spec * spec + P.bias


def render(parts, org, sc):
    sparks = [p for p in parts if isinstance(p, Spark)]
    parts = [p for p in parts if isinstance(p, Part)]
    pid = np.full((R, R), -1, np.int16)
    sh = np.zeros((R, R), np.float32)
    for i, P in enumerate(parts):
        m = raster(P.pts, org, sc)
        if m.any():
            pid[m] = i; sh[m] = shade(m, P, sc)[m]
    blk = lambda a: a.reshape(N, SS, N, SS).sum(axis=(1, 3))
    cover = blk((pid >= 0).astype(np.float32)) / (SS * SS)
    score = np.zeros((len(parts), N, N), np.float32)
    shsum = np.zeros((len(parts), N, N), np.float32)
    for i, P in enumerate(parts):
        m = (pid == i).astype(np.float32)
        c = blk(m)
        score[i] = c * P.weight
        shsum[i] = blk(sh * m) / np.maximum(c, 1)
    win = score.argmax(axis=0)
    opaque = (cover >= 0.42) | (score.max(axis=0) >= SS * SS * 0.32)
    idx = np.zeros((N, N), np.int16)
    for y, x in zip(*np.nonzero(opaque)):
        i = win[y, x]; ramp = RAMPS[parts[i].mat]
        idx[y, x] = int(np.clip(round(shsum[i, y, x] * (len(ramp) - 1)), 0, len(ramp) - 1))
    # 뒤 부품이 다른 재질의 앞 부품과 닿는 곳은 어둡게 (부품 사이 경계선)
    out_idx = idx.copy()
    for y, x in zip(*np.nonzero(opaque)):
        a = win[y, x]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, yy = x + dx, y + dy
            if 0 <= xx < N and 0 <= yy < N and opaque[yy, xx] and win[yy, xx] > a and parts[win[yy, xx]].mat != parts[a].mat:
                out_idx[y, x] = max(0, idx[y, x] - 2)
                break
    rgba = np.zeros((N, N, 4), np.uint8)
    tint = np.zeros((N, N), np.uint8)
    for y, x in zip(*np.nonzero(opaque)):
        P = parts[win[y, x]]
        rgba[y, x, :3] = hexrgb(RAMPS[P.mat][out_idx[y, x]]); rgba[y, x, 3] = 255
        tint[y, x] = 255 if P.tint else 0
    ring = np.zeros_like(opaque)
    ring[1:, :] |= opaque[:-1, :]; ring[:-1, :] |= opaque[1:, :]; ring[:, 1:] |= opaque[:, :-1]; ring[:, :-1] |= opaque[:, 1:]
    ring &= ~opaque
    rgba[ring, :3] = OUTLINE; rgba[ring, 3] = 255
    E = RAMPS['energy']
    for sp in sparks:
        x, y = (int(math.floor(c)) for c in to_tile(sp.cu, sp.cv, org, sc))
        cells = [(0, 0, len(E) - 1)] + [(dx * d, dy * d, len(E) - 1 - d - (1 if sp.size == 1 else 0))
                                        for d in range(1, sp.size + 1) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        for dx, dy, lv in cells:
            xx, yy = x + dx, y + dy
            if 0 <= xx < N and 0 <= yy < N and rgba[yy, xx, 3] == 0:
                rgba[yy, xx, :3] = hexrgb(E[max(0, lv)]); rgba[yy, xx, 3] = 255; tint[yy, xx] = 255
    return Image.fromarray(rgba, 'RGBA'), Image.fromarray(tint, 'L')


def place(parts, vmin, vmax):
    """무기 축의 가운데를 그림 한가운데 두고, 넘치면 줄이고 옮겨서 1픽셀 여백 안에 넣습니다."""
    sc = 1.0
    for _ in range(40):
        org = np.array([N / 2, N / 2]) - AX * ((vmin + vmax) / 2) * sc
        pts = np.array([to_tile(u, v, org, sc) for P in parts for u, v in P.pts])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        if (hi - lo).max() <= N - 2.6:
            shift = (np.array([N / 2, N / 2]) - (lo + hi) / 2) * 0
            for k in range(2):
                if lo[k] < 1.3: shift[k] = 1.3 - lo[k]
                if hi[k] > N - 1.3: shift[k] = (N - 1.3) - hi[k]
            return org + shift, sc
        sc *= 0.985
    return org, sc


# ═════════════════════════ 무기 15종 ═════════════════════════
# 각 함수는 (부품들(뒤 → 앞), 손잡이 끝 v, 끝 v, 이펙트가 시작될 v) 를 돌려줍니다.

def sword_heaven():
    """천공의 성검 — 날개 코등이, 넓은 성검, 빛나는 홈"""
    parts = []
    feathers = [(((2.5, -2.5), (7, -3.6), (11, -3.2), (14.5, -1.2)), 2.4, 0.7, 'silver'),
                (((2.5, -1.5), (8, -1.6), (13, 0), (18, 3.2)), 2.8, 0.8, 'silver'),
                (((2.5, 0), (9, 1.4), (15, 4.2), (21, 9.5)), 3.2, 0.9, 'silver'),
                (((2.5, 1.5), (9, 4.2), (16, 9.5), (22, 17.5)), 3.6, 0.9, 'gold')]
    for ctrl, w0, w1, mat in feathers:
        f = stroke(bez(*ctrl, n=16), w0, w1)
        parts += [Part(f, mat, 'bevel', bevel=1.0), Part(mirror(f), mat, 'bevel', bevel=1.0)]
    parts.append(Part(sym([(4.6, 2), (4.9, 10), (4.6, 26), (4.0, 38), (2.6, 45), (0, 50)]), 'steel', 'ridge', k=0.9))
    parts.append(Part(sym([(1.3, 5), (1.4, 30), (0.8, 38), (0, 42)]), 'energy', 'dome', weight=2.4, amb=0.25))
    parts.append(Part(sym([(5.6, -2.2), (6.9, -0.4), (5.2, 1.9), (2.5, 2.9)]), 'gold', 'bevel', bevel=1.3))
    parts += jewel(0, 0, 2.4, 'gemB')
    parts += grip(-14, -3, 2.0)
    parts.append(Part(sym([(0.1, -22), (2.8, -19), (3.2, -17), (2.2, -14.2)]), 'gold', 'ridge', k=0.8))
    parts.append(Part(ell(0, -17.6, 1.3, 1.3), 'gemB', 'dome', weight=2, spec=0.9))
    return parts, -22, 50, 2.5


def sword_abyss():
    """심연의 마검 — 물결치는 검은 칼날, 갈라지는 빛줄기, 뿔 코등이와 마안"""
    parts = []
    horn = stroke(bez((3, -0.5), (10.5, -1.5), (15.5, 5), (13, 15.5), 18), 4.2, 0.6)
    parts += [Part(horn, 'bone', 'dome'), Part(mirror(horn), 'bone', 'dome')]
    right = [(5.4, 2)]
    for i in range(7):
        v = 4 + i * 5.6; w = 5.6 - i * 0.33
        right += [(w + 1.6, v + 1.3), (w - 0.6, v + 3.7)]
    right += [(2.6, 44), (0, 50)]
    parts.append(Part(sym(right), 'dark', 'ridge', k=1.0, amb=0.34))
    parts.append(Part(sym([(1.5, 3), (1.6, 22), (1.1, 36), (0, 44)]), 'energy', 'dome', weight=2.6, amb=0.18))
    for i, v in enumerate((8, 15, 22, 29, 35)):
        sgn = 1 if i % 2 == 0 else -1
        parts.append(Part(stroke([(0, v), (sgn * 2.0, v + 1.6), (sgn * 3.6, v + 3.8), (sgn * 4.4, v + 5.6)], 1.2, 0.5),
                          'energy', 'dome', weight=2.2, amb=0.3))
    parts.append(Part(sym([(7, -2.6), (8.2, -0.4), (5.4, 2.6), (2.0, 3.2)]), 'dark', 'bevel', bevel=1.2, amb=0.3))
    parts.append(Part(ell(0, 0, 3.7, 2.9), 'gold', 'dome'))
    parts.append(Part(ell(0, 0, 2.5, 1.9), 'gemR', 'dome', weight=2, spec=0.9))
    parts.append(Part(ell(0, 0, 0.55, 1.5), 'dark', 'const', const=0.0, weight=3))
    parts += grip(-14, -3, 1.9, 'leather', 'bone', 3)
    parts.append(Part(sym([(0.1, -23), (1.6, -20.5), (4.4, -20.4), (2.6, -18.2), (3.5, -15.8), (1.9, -14)]), 'dark', 'ridge', amb=0.32))
    parts.append(Part(ell(0, -17.8, 1.15, 1.15), 'gemR', 'dome', weight=2))
    return parts, -23, 50, 3


def sword_dragon():
    """창세의 용검 — 붉은 용 날개 코등이, 불꽃 무늬가 타오르는 칼날, 용의 눈, 여의주를 쥔 발톱"""
    parts = []
    root, wrist = (2.6, 1.2), (8.4, 6.6)
    tips = [(12.8, 17.6), (20.4, 12.0), (20.6, 3.4), (14.6, -2.6)]
    for sgn in (1, -1):
        f = lambda q: (q[0] * sgn, q[1])
        mem = [f(root), f(wrist), f(tips[0])]
        for a, b in zip(tips, tips[1:] + [(3.0, -1.6)]):
            ca = (a[0] + (wrist[0] - a[0]) * 0.34, a[1] + (wrist[1] - a[1]) * 0.34)
            cb = (b[0] + (wrist[0] - b[0]) * 0.34, b[1] + (wrist[1] - b[1]) * 0.34)
            mem += [f(q) for q in bez(a, ca, cb, b, 8)[1:]]
        parts.append(Part(mem, 'red', 'bevel', bevel=1.0, amb=0.35))
        parts.append(Part(stroke([f(root), f(wrist), f(tips[0])], 1.9, 0.9), 'gold', 'dome', weight=1.5))
        for t in tips[1:]:
            parts.append(Part(stroke([f(wrist), f(t)], 1.3, 0.6), 'gold', 'dome', weight=1.5))
        parts.append(Part([f((tips[0][0] - 0.6, tips[0][1] - 0.4)), f((tips[0][0] + 0.4, tips[0][1] + 2.4)), f((tips[0][0] + 1.0, tips[0][1] - 0.8))], 'gold', 'ridge'))
    blade = [(-3.1, 2), (-3.5, 20), (-3.1, 34), (-1.7, 44), (0.6, 50), (2.4, 44), (3.4, 34), (3.6, 18), (3.1, 2)]
    parts.append(Part(blade, 'steel', 'ridge', k=0.9))
    outer = [(3.0, 5), (3.3, 18), (3.1, 33), (2.3, 43), (0.8, 48)]
    inner = [(1.0, 46)]
    for i in range(9):
        v = 42 - i * 4.2
        inner += [(2.0, v - 0.6), (0.8, v - 2.4)]
    inner += [(1.4, 5)]
    parts.append(Part(outer + inner, 'energy', 'dome', weight=2.0, amb=0.28))
    parts.append(Part(sym([(5.0, -2.6), (5.8, -0.6), (4.4, 1.8), (2.4, 2.8)]), 'gold', 'bevel', bevel=1.3))
    parts.append(Part(ell(0, 0, 3.5, 3.0), 'gold', 'dome'))
    parts.append(Part(ell(0, 0, 2.4, 1.9), 'gemR', 'dome', weight=2, spec=0.9))
    parts.append(Part(ell(0, 0, 0.5, 1.6), 'gemR', 'const', const=0.0, weight=3))
    parts += grip(-14, -3, 2.0, 'red', 'gold', 4, bw=0.45)
    ov = -17.6
    parts.append(Part(ell(0, ov, 2.7, 2.7), 'gemR', 'dome', weight=1.5, spec=0.9))
    for sgn in (-1, 1):
        parts.append(Part(stroke(bez((sgn * 1.4, -14.4), (sgn * 3.8, -15.6), (sgn * 3.8, ov - 1.5), (sgn * 1.4, ov - 2.6), 10), 1.35, 0.5), 'gold', 'dome', weight=1.6))
    parts.append(Part(stroke(bez((0, -14.6), (0.6, -16.2), (0.4, ov - 1), (-0.4, ov - 1.2), 8), 1.0, 0.45), 'gold', 'dome', weight=1.8))
    return parts, -20.8, 50, 2.5


def axe_titan():
    """거신의 양날도끼 — 뾰족한 뿔이 달린 반달 양날, 날을 따라 빛나는 룬 줄, 금테 자루"""
    parts = []
    parts.append(Part(sym([(1.8, -35), (1.8, 22)]), 'wood', 'dome'))
    for v in (-29, -21, -13, -5):
        parts.append(Part(sym([(2.35, v - 0.6), (2.35, v + 0.6)]), 'gold', 'dome', weight=1.6))
    parts.append(Part(sym([(0.1, -39), (2.0, -36.6), (2.7, -34.2), (2.3, -32.6)]), 'gold', 'ridge'))
    blade = ([(3, 8)] + bez((3, 8), (6.5, 4.8), (9.8, 0.2), (12.6, -5), 10)[1:]
             + bez((12.6, -5), (21.6, 1.6), (21.6, 24.4), (12.6, 31), 24)[1:] + bez((12.6, 31), (9.8, 25.8), (6.5, 21.2), (3, 18), 10)[1:])
    for b in (blade, mirror(blade)):
        parts.append(Part(b, 'steel', 'ridge', k=0.85))
    for s in (1, -1):
        rune = stroke(bez((s * 12.2, -1.4), (s * 18.2, 4.4), (s * 18.2, 21.6), (s * 12.2, 27.4), 18), 1.3)
        parts.append(Part(rune, 'energy', 'dome', weight=2.3, amb=0.22))
        parts.append(Part(stroke(bez((s * 3.3, 8.4), (s * 6.6, 5.4), (s * 9.0, 1.8), (s * 11.4, -2.6), 10), 1.4, 0.6), 'gold', 'dome', weight=1.5))
        parts.append(Part(stroke(bez((s * 3.3, 17.6), (s * 6.6, 20.6), (s * 9.0, 24.2), (s * 11.4, 28.6), 10), 1.4, 0.6), 'gold', 'dome', weight=1.5))
    parts.append(Part(sym([(2.2, 21), (1.7, 27), (0, 33.5)]), 'steel', 'ridge', k=0.9))
    parts.append(Part(sym([(3.8, 4.6), (4.3, 6.6), (4.3, 19.4), (3.8, 21.4)]), 'gold', 'bevel', bevel=1.4))
    parts += jewel(0, 13, 2.3, 'gemB')
    return parts, -39, 33.5, 3.5


def axe_chaos():
    """혼돈의 처형도끼 — 거대한 외날, 날 끝을 따라 흐르는 빛, 해골 장식과 뒤쪽 뿔"""
    parts = []
    parts.append(Part(sym([(1.7, -36), (1.7, 24)]), 'dark', 'dome', amb=0.3))
    for v in (-30, -21, -12):
        parts.append(Part(sym([(2.4, v - 0.7), (3.0, v), (2.4, v + 0.7)]), 'bone', 'bevel', bevel=0.8, weight=1.5))
    parts.append(Part(sym([(0.1, -40.5), (2.7, -37), (2.0, -35)]), 'bone', 'ridge'))
    horn = stroke(bez((2, 12.5), (8, 12), (12.5, 16), (13.5, 23.5), 14), 3.8, 0.6)
    parts.append(Part(horn, 'bone', 'dome'))
    edge = bez((-6.5, -4.5), (-23, -0.5), (-24, 22.5), (-9.5, 31.5), 26)
    blade = [(-2, 3.5)] + bez((-2, 3.5), (-3, 0.5), (-4.5, -2.5), (-6.5, -4.5), 6)[1:] + edge[1:] + bez((-9.5, 31.5), (-7, 28.5), (-4, 26.5), (-2, 25.5), 6)[1:]
    parts.append(Part(blade, 'dark', 'ridge', k=0.9, amb=0.34))
    for i, v in enumerate((6, 12.5, 19)):
        parts.append(Part([(-6.5 - i * 0.3, v - 1.6), (-9.5 - i * 0.5, v), (-6.5 - i * 0.3, v + 1.6)], 'dark', 'const', const=0.0, weight=1.6))
    parts.append(Part(stroke(bez((-7.8, -2.3), (-21.2, 1.4), (-22.2, 21.4), (-9.8, 29), 22), 1.7), 'energy', 'dome', weight=2.4, amb=0.22))
    parts.append(Part(sym([(1.9, 24), (1.3, 29), (0, 34.5)]), 'dark', 'ridge', amb=0.32))
    parts.append(Part(ell(0, 14.5, 4.6, 4.4), 'bone', 'dome'))
    parts.append(Part(sym([(2.9, 8.6), (3.3, 10.6), (4.0, 12.5)]), 'bone', 'bevel', bevel=1.0))
    for s in (1, -1):
        parts.append(Part(ell(s * 1.9, 14.2, 1.35, 1.15), 'energy', 'dome', weight=3, amb=0.45))
    parts.append(Part([(0, 12.6), (0.75, 11.3), (-0.75, 11.3)], 'bone', 'const', const=0.0, weight=3))
    for u in (-1.6, 0, 1.6):
        parts.append(Part(rect(u - 0.3, u + 0.3, 8.9, 10.2), 'bone', 'const', const=0.05, weight=1.8))
    return parts, -40.5, 34.5, -2


def axe_thunder():
    """뇌신의 도끼 — 긴 수염이 달린 은빛 외날, 날을 가로지르는 번개, 뒤쪽 금빛 날개"""
    parts = []
    parts.append(Part(sym([(1.7, -35), (1.7, 24)]), 'silver', 'dome'))
    for v in np.arange(-20, 4, 3.2):
        parts.append(Part(stroke([(-1.9, v), (1.9, v + 1.8)], 0.95), 'gold', 'dome', weight=1.4))
    parts += grip(-35, -22, 2.0, 'leather', 'gold', 3)
    parts.append(Part(sym([(0.1, -39), (2.4, -36.4), (2.2, -34.6)]), 'gold', 'ridge'))
    for ctrl, w0 in ((((2, 15.5), (5, 16.2), (7.2, 18.8), (8.0, 23)), 2.2), (((2, 11.5), (5.6, 11.8), (8.6, 14.4), (10.4, 19.6)), 2.7),
                     (((2, 7.5), (6.4, 7.4), (10, 10), (12.4, 16)), 3.1)):
        parts.append(Part(stroke(bez(*ctrl, n=10), w0, 0.7), 'gold', 'bevel', bevel=0.9))
    blade = ([(-2.5, 24)] + bez((-2.5, 24), (-6.5, 25), (-10.5, 26.4), (-14.6, 28.6), 10)[1:]
             + bez((-14.6, 28.6), (-21, 20), (-21, 6), (-11.6, -4.4), 22)[1:] + bez((-11.6, -4.4), (-8.2, -0.6), (-5.6, 3.2), (-2.5, 5.4), 10)[1:])
    parts.append(Part(blade, 'silver', 'ridge', k=0.85, amb=0.3))
    parts.append(Part(stroke(bez((-13.6, 26.6), (-19.4, 19.0), (-19.4, 7.0), (-11.0, -2.4), 20), 1.2), 'gold', 'dome', weight=1.8))
    bolt = [(-4.4, 21.6), (-10.6, 18.4), (-7.8, 15.4), (-14.8, 10.6), (-10.8, 8.8), (-16.8, 3.0)]
    parts.append(Part(stroke(bolt, 2.5, 1.2), 'energy', 'dome', weight=2.8, amb=0.2))
    parts.append(Part(stroke([(-10.6, 18.4), (-14.2, 21.6), (-13.4, 24.0)], 1.4, 0.7), 'energy', 'dome', weight=2.4, amb=0.25))
    parts.append(Part(sym([(2.2, 24), (1.6, 29.5), (0, 35.5)]), 'steel', 'ridge', k=0.9))
    parts.append(Part(sym([(3.2, 3.5), (3.6, 5.5), (3.6, 22.5), (3.2, 24.5)]), 'gold', 'bevel', bevel=1.3))
    parts += jewel(0, 14, 1.9, 'gemB')
    return parts, -39, 35.5, 3


def staff_star():
    """성좌의 지팡이 — 초승달이 품은 별, 주위의 작은 별들, 금빛 나선"""
    parts = []
    parts.append(Part(sym([(1.3, -38), (1.3, 13)]), 'silver', 'dome'))
    for v in np.arange(-36, 11, 3):
        parts.append(Part(stroke([(-1.55, v), (1.55, v + 1.6)], 0.8), 'gold', 'dome', weight=1.3))
    parts.append(Part(sym([(0.1, -42), (1.9, -39), (1.7, -37)]), 'gold', 'ridge'))
    parts.append(Part(crescent((0, 21), 9.6, (0, 24.6), 8.3), 'gold', 'bevel', bevel=1.5))
    parts.append(Part(ell(0, 25.2, 5.0, 5.0), 'energy', 'dome', weight=1.5, amb=0.2))
    for cu, cv, size in ((-9.5, 31.5, 2), (8.8, 33.2, 1), (0.6, 36.4, 2), (-11.6, 23.6, 1), (11.6, 25.0, 2), (-5.4, 36.0, 1)):
        parts.append(Spark(cu, cv, size))
    parts.append(Part(sym([(2.4, 10.4), (3.2, 12), (2.2, 14.2)]), 'gold', 'bevel', bevel=1.0))
    parts += jewel(0, 12.4, 1.5, 'gemB', ring=0.9)
    return parts, -42, 38, 11


def staff_tree():
    """세계수의 지팡이 — 꼬인 나무 줄기, 빛나는 열매를 감싼 가지와 잎, 뿌리"""
    parts = []
    for ph in (0, math.pi):
        path = [(1.15 * math.sin(v * 0.42 + ph), v) for v in np.arange(-37, 12.1, 0.5)]
        parts.append(Part(stroke(path, 2.3), 'wood', 'dome'))
    parts.append(Part(stroke([(0, -36), (0, -41.5)], 2.0, 0.6), 'wood', 'dome'))
    for s in (-1, 1):
        parts.append(Part(stroke(bez((0, -35.5), (s * 1.6, -37.5), (s * 3.2, -38.6), (s * 3.8, -41.2), 8), 1.6, 0.5), 'wood', 'dome'))
    parts.append(Part(ell(0, 21.5, 5.3, 5.3), 'energy', 'dome', weight=1.4, amb=0.2))
    br = [stroke(bez((1, 9.5), (8, 12.5), (9.6, 22), (4.4, 29), 16) + bez((4.4, 29), (2.4, 31), (-0.4, 30.6), (0.6, 28.6), 6)[1:], 2.2, 0.8),
          stroke(bez((-1, 9.5), (-8.4, 13), (-9.4, 22.5), (-4.6, 28.4), 16) + bez((-4.6, 28.4), (-3, 30.4), (-1.2, 30.2), (-1.4, 28.4), 6)[1:], 2.0, 0.8),
          stroke(bez((0.4, 12), (2.6, 14.5), (4.2, 15.2), (6.6, 15.4), 8), 1.2, 0.5),
          stroke(bez((-0.4, 13), (-2.4, 14.6), (-3.8, 16.6), (-4, 18.4), 8), 1.1, 0.5)]
    for b in br:
        parts.append(Part(b, 'wood', 'dome'))
    for cu, cv, rot in ((8.9, 17.0, 35), (-9.0, 20.0, -40), (6.6, 27.6, 65), (-6.6, 26.8, -60), (10.4, 23.8, 10), (-10.2, 15.4, -15),
                        (7.8, 15.8, -30), (1.6, 31.6, 80), (-2.6, 31.8, -75)):
        parts.append(Part(ell(cu, cv, 2.0, 1.05, rot=rot), 'leaf', 'dome', weight=1.4))
    return parts, -41.5, 32.5, 9.5


def staff_lich():
    """리치왕의 지팡이 — 등뼈 자루, 눈이 빛나는 해골, 가시 왕관과 그 위에 뜬 구슬"""
    parts = []
    parts.append(Part(sym([(1.0, -38), (1.0, 12)]), 'bone', 'dome', bias=-0.12))
    for v in np.arange(-36, 11, 2.6):
        parts.append(Part(ell(0, v, 2.15, 0.95), 'bone', 'dome', weight=1.3))
    for v in np.arange(-31, -19, 1.7):
        parts.append(Part(stroke([(-2.4, v), (2.4, v + 1.3)], 1.0), 'red', 'dome', weight=1.6))
    parts.append(Part(sym([(0.1, -42), (2.0, -39), (1.6, -37)]), 'bone', 'ridge'))
    for s in (1, -1):
        parts.append(Part(stroke(bez((s * 4.6, 18.5), (s * 9, 18.4), (s * 11.4, 22.4), (s * 10.6, 28), 12), 2.8, 0.5), 'dark', 'dome', amb=0.3))
    for a in (40, 65, 90, 115, 140):
        r0 = 5.6
        cu, cv = r0 * math.cos(math.radians(a)), 19.8 + r0 * math.sin(math.radians(a))
        L = 6.8 if a == 90 else 5.4
        tu, tv = cu + L * math.cos(math.radians(a)), cv + L * math.sin(math.radians(a))
        pu, pv = 1.25 * math.sin(math.radians(a)), -1.25 * math.cos(math.radians(a))
        parts.append(Part([(cu + pu, cv + pv), (tu, tv), (cu - pu, cv - pv)], 'gold', 'ridge', k=0.9))
    parts.append(Part(ell(0, 19.8, 6.2, 6.0), 'bone', 'dome'))
    parts.append(Part(sym([(2.7, 11.2), (3.5, 13), (4.5, 15.6)]), 'bone', 'bevel', bevel=1.0))
    parts.append(Part(stroke(bez((-5.2, 21.6), (-2, 24.4), (2, 24.4), (5.2, 21.6), 12), 1.4), 'gold', 'dome', weight=1.6))
    parts.append(Part(ell(0, 24.0, 0.9, 0.9), 'gemR', 'dome', weight=2.5))
    for s in (1, -1):
        parts.append(Part(ell(s * 2.4, 18.8, 1.85, 1.55), 'energy', 'dome', weight=3, amb=0.45))
    parts.append(Part([(0, 16.4), (0.8, 15.0), (-0.8, 15.0)], 'bone', 'const', const=0.0, weight=3))
    for u in (-1.7, 0, 1.7):
        parts.append(Part(rect(u - 0.3, u + 0.3, 11.6, 13.0), 'bone', 'const', const=0.05, weight=1.8))
    parts.append(Part(ell(0, 34.0, 3.3, 3.3), 'energy', 'dome', weight=1.5, amb=0.22))
    return parts, -42, 37.3, 11


def spear_sky():
    """천룡의 창 — 붉은 칠 자루, 금빛 날개 날밑, 긴 잎사귀 창날과 붉은 술"""
    parts = []
    parts.append(Part(sym([(1.4, -37), (1.4, 14)]), 'red', 'dome'))
    for v in (-33, -23, -13, -3):
        parts.append(Part(sym([(1.95, v - 0.6), (1.95, v + 0.6)]), 'gold', 'dome', weight=1.6))
    parts.append(Part(sym([(0.1, -40), (2.0, -37.6), (1.8, -36)]), 'gold', 'ridge'))
    for i, (du, dv) in enumerate(((3.6, -9.5), (5.2, -8.2), (6.6, -6.4), (7.8, -4.2))):
        parts.append(Part(stroke(bez((1.2, 12), (2.2 + du * 0.3, 12 + dv * 0.3), (1.4 + du * 0.8, 12 + dv * 0.75), (1.2 + du, 12 + dv), 10), 1.6, 0.9),
                          'red', 'dome', weight=1.2, bias=0.05 * (i % 2)))
    for s in (1, -1):
        parts.append(Part([(s * 1.8, 15)] + bez((s * 1.8, 15), (s * 7.4, 13.8), (s * 10.4, 17.2), (s * 10.6, 22.6), 10)[1:]
                          + bez((s * 10.6, 22.6), (s * 8.2, 20), (s * 5.2, 18.8), (s * 2.0, 19.4), 10)[1:], 'gold', 'bevel', bevel=1.1))
    parts.append(Part(sym([(2.3, 15), (3.7, 20.5), (3.9, 27.5), (2.7, 35.5), (0, 44)]), 'steel', 'ridge', k=0.85))
    parts.append(Part(sym([(0.8, 18.5), (0.9, 30), (0, 37.5)]), 'energy', 'dome', weight=2.4, amb=0.22))
    parts.append(Part(sym([(2.5, 10.8), (2.7, 12.4), (2.5, 14.8)]), 'gold', 'bevel', bevel=1.0))
    parts += jewel(0, 16.4, 1.15, 'gemR', ring=0.9)
    return parts, -40, 44, 14.5


def spear_trident():
    """해신의 삼지창 — 물결 모양 받침, 미늘 달린 세 갈래, 바다빛 보석"""
    parts = []
    parts.append(Part(sym([(1.4, -38), (1.4, 12)]), 'silver', 'dome'))
    for v in (-34, -26, -18, -10, -2):
        parts.append(Part(sym([(1.95, v - 0.55), (1.95, v + 0.55)]), 'gold', 'dome', weight=1.6))
    parts.append(Part(sym([(0.1, -41.5), (2.1, -38.6), (1.8, -37)]), 'gold', 'ridge'))
    for s in (1, -1):
        prong = stroke(bez((s * 7.4, 14), (s * 8.6, 20), (s * 8.2, 25.6), (s * 7.2, 29.6), 12), 2.4, 1.7)
        parts.append(Part(prong, 'steel', 'ridge', k=0.8))
        parts.append(Part([(s * 5.0, 28.6), (s * 7.0, 30.2), (s * 9.4, 28.0), (s * 7.5, 35.6)], 'steel', 'ridge', k=0.9))
    parts.append(Part(sym([(1.6, 13), (1.6, 30)]), 'steel', 'ridge', k=0.8))
    parts.append(Part(sym([(3.8, 29.2), (2.5, 32.4), (0, 41.6)]), 'steel', 'ridge', k=0.9))
    parts.append(Part(sym([(0.6, 15), (0.6, 30.5), (0, 35)]), 'energy', 'dome', weight=2.2, amb=0.25))
    parts.append(Part(sym([(2, 10), (6, 10.4), (9.2, 12.4), (9.8, 15.2), (8.0, 16.2), (5.0, 15.0), (2, 15.2)]), 'gold', 'bevel', bevel=1.3))
    for s in (1, -1):
        parts.append(Part(stroke(bez((s * 3.2, 12.6), (s * 4.6, 11.4), (s * 6.4, 12.0), (s * 6.0, 13.6), 8), 0.9), 'energy', 'dome', weight=2.0, amb=0.35))
    parts += jewel(0, 12.8, 1.6, 'gemB', ring=1.0)
    return parts, -41.5, 41.6, 12


def spear_reaper():
    """사신의 대낫 — 검은 자루, 크게 휘어진 낫날과 날 끝의 빛, 해골 이음새"""
    parts = []
    parts.append(Part(sym([(1.5, -38), (1.5, 27)]), 'dark', 'dome', amb=0.3))
    for v in (-31, -21, -11, -1):
        parts.append(Part(sym([(2.2, v - 0.65), (2.6, v), (2.2, v + 0.65)]), 'bone', 'bevel', bevel=0.8, weight=1.5))
    parts.append(Part(sym([(0.1, -42), (2.2, -39), (1.8, -37)]), 'bone', 'ridge'))
    blade = [(-1, 29.5)] + bez((-1, 30.5), (-10.5, 34), (-21, 30), (-28, 13.5), 22)[1:] + bez((-28, 13.5), (-20, 22.2), (-10.5, 25.2), (-1, 23.5), 18)[1:]
    parts.append(Part(blade, 'steel', 'ridge', k=0.85))
    parts.append(Part(stroke(bez((-26.2, 15.6), (-19.4, 22.6), (-10.4, 25.0), (-2.2, 24.4), 18), 1.3, 1.8), 'energy', 'dome', weight=2.4, amb=0.22))
    parts.append(Part(ell(0.4, 26.6, 3.4, 3.6), 'bone', 'dome'))
    parts.append(Part(sym([(2.0, 21.4), (2.4, 22.6), (3.0, 24.0)]), 'bone', 'bevel', bevel=0.8))
    for s in (1, -1):
        parts.append(Part(ell(0.4 + s * 1.35, 26.4, 1.0, 0.9), 'energy', 'dome', weight=3, amb=0.45))
    parts.append(Part(sym([(1.0, 30.6), (0.6, 33.2), (0, 35)]), 'dark', 'ridge', amb=0.3))
    return parts, -42, 35, 20


def mace_sun():
    """태양신의 철퇴 — 불꽃 햇살을 두른 황금 해 원반, 가운데 빛나는 핵"""
    parts = []
    parts += grip(-34, -21, 1.8, 'leather', 'gold', 3)
    parts.append(Part(sym([(1.6, -21), (1.6, 9)]), 'gold', 'dome'))
    for v in (-15, -8, -1):
        parts.append(Part(sym([(2.15, v - 0.55), (2.15, v + 0.55)]), 'gold', 'dome', weight=1.6, bias=0.1))
    parts.append(Part(ell(0, -36, 2.5, 2.5), 'gold', 'dome'))
    parts.append(Part(star(0, 19, 7.4, 14.2, n=12, rot=15), 'energy', 'bevel', bevel=1.2, amb=0.3))
    parts.append(Part(sym([(2.2, 6.8), (3.6, 9.6), (2.6, 11.6)]), 'gold', 'bevel', bevel=1.0))
    parts.append(Part(ell(0, 19, 7.7, 7.7), 'gold', 'dome'))
    parts.append(Part(ell(0, 19, 5.5, 5.5), 'gold', 'bevel', bevel=1.0, bias=-0.08))
    parts.append(Part(ell(0, 19, 3.7, 3.7), 'energy', 'dome', weight=1.6, amb=0.25))
    return parts, -38.5, 33.2, 9


def mace_doom():
    """파멸의 전투망치 — 룬이 새겨진 검은 망치 머리, 한쪽 가시와 은빛 타격면"""
    parts = []
    parts += grip(-36, -24, 1.9, 'leather', 'gold', 3)
    parts.append(Part(sym([(1.7, -24), (1.7, 14)]), 'dark', 'dome', amb=0.3))
    for v in (-16, -6, 4):
        parts.append(Part(sym([(2.3, v - 0.6), (2.3, v + 0.6)]), 'gold', 'dome', weight=1.6))
    parts.append(Part(sym([(0.1, -40), (2.3, -37.4), (2.1, -35.6)]), 'gold', 'ridge'))
    parts.append(Part([(-11.6, 15.2), (-19.4, 19.2), (-11.6, 23.2)], 'steel', 'ridge', k=0.9))
    parts.append(Part([(11.6, 13.2), (15.2, 14.2), (15.2, 24.2), (11.6, 25.2)], 'silver', 'bevel', bevel=1.2))
    parts.append(Part(sym([(10.6, 11.8), (12.2, 13.4), (12.2, 24.8), (10.6, 26.4)]), 'dark', 'bevel', bevel=2.0, amb=0.3))
    for v0, v1 in ((11.8, 13.4), (24.8, 26.4)):
        parts.append(Part(sym([(10.6, v0), (11.4, (v0 + v1) / 2), (10.6, v1)]), 'gold', 'bevel', bevel=0.7, weight=1.4))
    u0 = -7.2
    runes = [[(u0 - 1.0, 15.4), (u0 - 1.0, 22.8)], [(u0 - 1.0, 22.8), (u0 + 1.8, 20.9)], [(u0 - 1.0, 19.9), (u0 + 1.8, 18.0)],
             [(0, 15.4), (0, 22.8)], [(0, 18.9), (-2.1, 22.6)], [(0, 18.9), (2.1, 22.6)],
             [(7.2, 22.8), (9.3, 20.5)], [(9.3, 20.5), (7.2, 18.2)], [(7.2, 18.2), (5.1, 20.5)], [(5.1, 20.5), (7.2, 22.8)],
             [(7.2, 18.2), (5.0, 15.4)], [(7.2, 18.2), (9.4, 15.4)]]
    for r in runes:
        parts.append(Part(stroke(r, 1.15), 'energy', 'dome', weight=2.4, amb=0.3))
    parts.append(Part(sym([(2.3, 26), (1.5, 30), (0, 34.5)]), 'steel', 'ridge', k=0.9))
    return parts, -40, 34.5, 11.5


def mace_meteor():
    """유성의 모닝스타 — 갈라진 틈으로 빛이 새는 운석 머리, 사방의 가시"""
    parts = []
    parts += grip(-34, -21, 1.8, 'leather', 'gold', 3)
    parts.append(Part(sym([(1.5, -21), (1.5, 11)]), 'silver', 'dome'))
    for v in (-14, -6, 2):
        parts.append(Part(sym([(2.05, v - 0.55), (2.05, v + 0.55)]), 'gold', 'dome', weight=1.6))
    parts.append(Part(ell(0, -36, 2.3, 2.3), 'gold', 'dome'))
    for a in range(0, 360, 36):
        if 150 <= a <= 210:
            continue
        rad = math.radians(a + 90)
        L = 13.6 if a == 0 else 12.0
        bu, bv = math.cos(rad), math.sin(rad)
        pu, pv = -bv, bu
        tip = (bu * L, 20 + bv * L)
        parts.append(Part([(bu * 6.2 + pu * 1.9, 20 + bv * 6.2 + pv * 1.9), tip, (bu * 6.2 - pu * 1.9, 20 + bv * 6.2 - pv * 1.9)], 'steel', 'ridge', k=0.9))
    parts.append(Part(sym([(2.1, 9.5), (3.4, 11.8), (2.6, 13.2)]), 'gold', 'bevel', bevel=1.0))
    parts.append(Part(ell(0, 20, 7.7, 7.7), 'rock', 'dome'))
    cx, cy = -0.6, 20.8
    for ang, L, kink in ((20, 6.2, 18), (95, 6.6, -16), (165, 5.8, 20), (235, 6.4, -14), (305, 5.6, 16)):
        a1, a2 = math.radians(ang), math.radians(ang + kink)
        mid = (cx + math.cos(a1) * L * 0.5, cy + math.sin(a1) * L * 0.5)
        end = (mid[0] + math.cos(a2) * L * 0.5, mid[1] + math.sin(a2) * L * 0.5)
        parts.append(Part(stroke([(cx, cy), mid, end], 1.3, 0.55), 'energy', 'dome', weight=2.3, amb=0.4))
    parts.append(Part(ell(cx, cy, 1.9, 1.9), 'energy', 'dome', weight=2.6, amb=0.45))
    return parts, -38.3, 33.6, 10


DESIGNS = [
    # (키, 종류, 형태 번호, 한국어 이름, 함수)
    ('aw_sword_heaven',  0, 0, '천공의 성검',     sword_heaven),
    ('aw_sword_abyss',   0, 1, '심연의 마검',     sword_abyss),
    ('aw_sword_dragon',  0, 2, '창세의 용검',     sword_dragon),
    ('aw_axe_titan',     1, 0, '거신의 양날도끼', axe_titan),
    ('aw_axe_chaos',     1, 1, '혼돈의 처형도끼', axe_chaos),
    ('aw_axe_thunder',   1, 2, '뇌신의 도끼',     axe_thunder),
    ('aw_staff_star',    2, 0, '성좌의 지팡이',   staff_star),
    ('aw_staff_tree',    2, 1, '세계수의 지팡이', staff_tree),
    ('aw_staff_lich',    2, 2, '리치왕의 지팡이', staff_lich),
    ('aw_spear_sky',     3, 0, '천룡의 창',       spear_sky),
    ('aw_spear_trident', 3, 1, '해신의 삼지창',   spear_trident),
    ('aw_spear_reaper',  3, 2, '사신의 대낫',     spear_reaper),
    ('aw_mace_sun',      4, 0, '태양신의 철퇴',   mace_sun),
    ('aw_mace_doom',     4, 1, '파멸의 전투망치', mace_doom),
    ('aw_mace_meteor',   4, 2, '유성의 모닝스타', mace_meteor),
]


def blade_half(img, P, T, g):
    """g 부터 끝까지의 반폭 h 와 중심 오프셋 s (build_weapons.py 의 geometry 와 같은 계산)."""
    a = np.asarray(img)[..., 3] >= 128
    L = math.hypot(T[0] - P[0], T[1] - P[1])
    ux, uy = (T[0] - P[0]) / L, (T[1] - P[1]) / L
    nx, ny = -uy, ux
    bins = {}
    for y, x in zip(*np.nonzero(a)):
        px, py = x + .5, y + .5
        t = (px - P[0]) * ux + (py - P[1]) * uy
        s = (px - P[0]) * nx + (py - P[1]) * ny
        b = bins.setdefault(int(t), [s, s])
        b[0] = min(b[0], s); b[1] = max(b[1], s)
    blade = [bins[t] for t in bins if g + 2 <= t <= L - 1.5]
    halves = sorted((v[1] - v[0]) / 2 for v in blade) or [1.5]
    centers = sorted((v[0] + v[1]) / 2 for v in blade) or [0]
    return round(max(1.2, halves[len(halves) // 2] - .5), 2), round(centers[len(centers) // 2], 2)


def uri(img):
    b = io.BytesIO()
    img.save(b, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()


# 미리보기용 속성 색 (게임의 ELEMENTS 와 같은 값: 그림자 a · 본색 b · 하이라이트 c)
PREVIEW_EL = [('#5A1A08', '#FF7A2E', '#FFE08A'), ('#123A52', '#7FD4F5', '#F0FCFF'), ('#14081F', '#7A3FD6', '#E2C6FF'),
              ('#6E5212', '#FFE08A', '#FFFFFF'), ('#16380E', '#7FE83F', '#EEFFCC'), ('#3A060C', '#E8304A', '#FFB8C0')]


def tint_like_game(img, mask, el):
    """게임의 awakeTint 와 같은 계산: 마스크 픽셀의 밝기를 속성 색 단계(a → b → c → 흰빛)로 바꿉니다."""
    A, B, C = (np.array(hexrgb(h), float) for h in el)
    W = np.array([255.0, 255, 255])
    a = np.asarray(img).astype(float).copy()
    m = np.asarray(mask) > 127
    l = (a[..., 0] * .3 + a[..., 1] * .59 + a[..., 2] * .11) / 255
    out = np.where((l < .5)[..., None], A + (B - A) * (l / .5)[..., None],
          np.where((l < .85)[..., None], B + (C - B) * ((l - .5) / .35)[..., None], C + (W - C) * ((l - .85) / .15).clip(0, 1)[..., None]))
    a[..., :3] = np.where(m[..., None], out, a[..., :3])
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), 'RGBA')


def preview(sheet, z=4):
    cols = 1 + len(PREVIEW_EL)
    W = N * z
    im = Image.new('RGBA', (W * cols, W * len(sheet)), (24, 20, 17, 255))
    for i, (k, s, m) in enumerate(sheet):
        im.alpha_composite(s.resize((W, W), Image.NEAREST), (0, i * W))
        for j, el in enumerate(PREVIEW_EL):
            im.alpha_composite(tint_like_game(s, m, el).resize((W, W), Image.NEAREST), ((j + 1) * W, i * W))
    im.save(os.path.join(OUT, 'preview.png'))
    # 한눈에 보기: 5종류 × 3형태, 속성 하나씩 돌려 가며
    W2 = N * 5
    grid = Image.new('RGBA', (W2 * 3, W2 * 5), (24, 20, 17, 255))
    for i, (k, s, m) in enumerate(sheet):
        el = PREVIEW_EL[i % len(PREVIEW_EL)]
        grid.alpha_composite(tint_like_game(s, m, el).resize((W2, W2), Image.NEAREST), ((i % 3) * W2, (i // 3) * W2))
    grid.save(os.path.join(OUT, 'preview_grid.png'))


def build():
    os.makedirs(OUT, exist_ok=True)
    data, sheet = {}, []
    for key, kind, form, ko, fn in DESIGNS:
        parts, vmin, vmax, vg = fn()
        org, sc = place(parts, vmin, vmax)
        img, mask = render(parts, org, sc)
        img.save(os.path.join(OUT, key + '.png'), optimize=True)
        P = to_tile(0, vmin, org, sc); T = to_tile(0, vmax, org, sc)
        g = (vg - vmin) * sc
        h, s = blade_half(img, P, T, g)
        data[key] = {'P': [round(P[0], 2), round(P[1], 2)], 'T': [round(T[0], 2), round(T[1], 2)],
                     'g': round(g, 2), 'h': h, 's': s, 'n': N, 'ko': ko,
                     'src': uri(img), 'm': uri(mask.convert('1'))}
        sheet.append((key, img, mask))
        print('  %-17s %-9s 배율 %.2f  P=%s T=%s g=%.1f h=%.1f  %5d B' % (key, ko, sc, data[key]['P'], data[key]['T'], g, h,
                                                                        len(data[key]['src']) + len(data[key]['m'])))
    preview(sheet)
    return data


def inject(data):
    pools = [[None] * 3 for _ in range(5)]
    for key, kind, form, ko, fn in DESIGNS:
        pools[kind][form] = key
    block = ('/* AWAKEN-SPRITES:BEGIN */\n'
             '  /* +21 각성 무기 그림 — tools/build_awakened.py 가 만듭니다. 직접 고치지 마세요. */\n'
             '  var AWAKEN_DATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n'
             '  var AWAKEN_FORMS = ' + json.dumps(pools, separators=(',', ':')) + ';\n'
             '  /* AWAKEN-SPRITES:END */')
    p = os.path.join(ROOT, 'index.html')
    s = open(p, encoding='utf-8').read()
    pat = re.compile(r'/\* AWAKEN-SPRITES:BEGIN \*/.*?/\* AWAKEN-SPRITES:END \*/', re.S)
    if not pat.search(s):
        sys.exit('index.html 에 AWAKEN-SPRITES 표시가 없습니다.')
    s = pat.sub(lambda m: block, s, count=1)
    open(p, 'w', encoding='utf-8').write(s)
    print('index.html 갱신 (%d KB)' % (len(block) // 1024))


if __name__ == '__main__':
    d = build()
    if '--preview' not in sys.argv:
        inject(d)
