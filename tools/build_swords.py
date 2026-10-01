#!/usr/bin/env python3
"""검 그림 빌드 스크립트.

Dungeon Crawl Stone Soup 의 CC0 타일 배포본(https://github.com/crawl/tiles 의
releases/Nov-2015)에서 검 그림을 골라
  1) 바닥 그림자를 지우고
  2) 칼끝·손잡이 끝·코등이 위치·칼날 폭을 계산해서
  3) assets/swords/*.png 로 저장하고
  4) index.html 의 /* SWORD-SPRITES:BEGIN */ ~ /* SWORD-SPRITES:END */ 사이를
     data: URI 와 위치 정보로 다시 씁니다.

쓰기 전에 crawl/tiles 의 TILES_UNDER_UNKNOWN_LICENSE.md 와 파일 이름을 대조해서,
목록에 오른 그림이 하나라도 섞이면 멈춥니다.

사용법:  python3 tools/build_swords.py /path/to/crawl/tiles
"""
import base64, io, json, math, os, re, subprocess, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = 'releases/Nov-2015'

# 키: (폴더, 파일 이름, 한국어 이름)
SPRITES = {
    # 일반
    'dagger':        ('item/weapon', 'dagger', '단검'),
    'short1':        ('item/weapon', 'short_sword1', '소검'),
    'short6':        ('UNUSED/weapons', 'short_sword6', '소검'),
    'long1':         ('item/weapon', 'long_sword1', '장검'),
    'long6':         ('UNUSED/weapons', 'long_sword6', '장검'),
    'great1':        ('item/weapon', 'greatsword1', '대검'),
    'falchion1':     ('item/weapon', 'falchion1', '언월도'),
    'falchion4':     ('UNUSED/weapons', 'falchion4', '언월도'),
    'scimitar1':     ('item/weapon', 'scimitar1', '곡검'),
    'rapier1':       ('item/weapon', 'rapier1', '세검'),
    'cutlass1':      ('UNUSED/weapons', 'cutlass1', '해적검'),
    'cutlass5':      ('UNUSED/weapons', 'cutlass5', '해적검'),
    'claymore':      ('UNUSED/weapons', 'claymore', '양손검'),
    # 희귀
    'short2':        ('item/weapon', 'short_sword2', '소검'),
    'short3':        ('item/weapon', 'short_sword3', '소검'),
    'short5':        ('UNUSED/weapons', 'short_sword5', '소검'),
    'long3':         ('item/weapon', 'long_sword3', '장검'),
    'falchion2':     ('item/weapon', 'falchion2', '언월도'),
    'falchion3':     ('item/weapon', 'falchion3', '언월도'),
    'rapier3':       ('item/weapon', 'rapier3', '세검'),
    'cutlass3':      ('UNUSED/weapons', 'cutlass3', '해적검'),
    'cutlass9':      ('UNUSED/weapons', 'cutlass9', '해적검'),
    'great3u':       ('UNUSED/weapons', 'greatsword3', '대검'),
    'double1':       ('item/weapon', 'double_sword', '쌍날검'),
    'katana2':       ('UNUSED/weapons', 'katana2', '태도'),
    'dagger3':       ('item/weapon', 'dagger3', '단검'),
    # 영웅
    'great3':        ('item/weapon', 'greatsword3', '대검'),
    'long5':         ('UNUSED/weapons', 'long_sword5', '장검'),
    'long7':         ('UNUSED/weapons', 'long_sword7', '장검'),
    'claymore2':     ('UNUSED/weapons', 'claymore2', '양손검'),
    'claymoreB':     ('UNUSED/weapons', 'claymore_blessed', '양손검'),
    'falchion5':     ('UNUSED/weapons', 'falchion5', '언월도'),
    'falchion7':     ('UNUSED/weapons', 'falchion7', '언월도'),
    'triple1':       ('item/weapon', 'triple_sword', '삼날검'),
    'triple2':       ('item/weapon', 'triple_sword2', '삼날검'),
    'double2':       ('item/weapon', 'double_sword2', '쌍날검'),
    # 전설 · 신화 (속성마다 한 자루씩 정해진 이름 있는 검)
    'power':         ('item/weapon/artefact', 'spwpn_sword_of_power', '작열하는 왕검'),
    'flamingDeath':  ('item/weapon/artefact', 'urand_flaming_death', '종말의 화염도'),
    'chillyDeath':   ('item/weapon/artefact', 'urand_chilly_death', '서리 송곳니'),
    'winter':        ('item/weapon/artefact', 'urand_jihad', '영원한 겨울의 검'),
    'great4':        ('UNUSED/weapons', 'greatsword4', '청뢰 대검'),
    'arcBlade':      ('item/weapon/artefact', 'urand_arc_blade', '번개를 가르는 검'),
    'doomKnight':    ('item/weapon/artefact', 'urand_doom_knight', '멸망 기사의 검'),
    'zonguldrok':    ('item/weapon/artefact', 'spwpn_sword_of_zonguldrok', '망자 군주의 검'),
    'golden':        ('UNUSED/weapons', 'golden_sword', '황금 성검'),
    'order':         ('item/weapon/artefact', 'urand_order', '질서의 별검'),
    'scimitar3':     ('item/weapon', 'scimitar3', '독뼈 곡검'),
    'plutonium':     ('item/weapon/artefact', 'urand_plutonium', '맹독 수정검'),
    'galeCutlass':   ('item/weapon/artefact', 'urand_cutlass', '바람 해적검'),
    'gyre':          ('item/weapon/artefact', 'urand_gyre', '회오리 쌍월도'),
    'morg':          ('item/weapon/artefact', 'urand_morg', '대지의 곡도'),
    'ancient':       ('UNUSED/weapons', 'ancient_sword', '태고의 대검'),
    'katana1':       ('UNUSED/weapons', 'katana1', '별그림자 태도'),
    'claymore3':     ('UNUSED/weapons', 'claymore3', '성운 양손검'),
    'bloodbane':     ('item/weapon/artefact', 'urand_bloodbane', '피의 저주검'),
    'cerebov':       ('item/weapon/artefact', 'spwpn_sword_of_cerebov', '혈귀의 파동검'),
}
POOLS = [
    ['dagger', 'short1', 'short6', 'long1', 'long6', 'great1', 'falchion1', 'falchion4',
     'scimitar1', 'rapier1', 'cutlass1', 'cutlass5', 'claymore'],
    ['short2', 'short3', 'short5', 'long3', 'falchion2', 'falchion3', 'rapier3', 'cutlass3',
     'cutlass9', 'great3u', 'double1', 'katana2', 'dagger3'],
    ['great3', 'long5', 'long7', 'claymore2', 'claymoreB', 'falchion5', 'falchion7',
     'triple1', 'triple2', 'double2'],
]
# 속성 순서: 화염 서리 뇌전 암흑 성광 맹독 질풍 대지 성운 혈염 — [전설, 신화]
SIGNATURE = [
    ['power', 'flamingDeath'], ['chillyDeath', 'winter'], ['great4', 'arcBlade'],
    ['doomKnight', 'zonguldrok'], ['golden', 'order'], ['scimitar3', 'plutonium'],
    ['galeCutlass', 'gyre'], ['morg', 'ancient'], ['katana1', 'claymore3'],
    ['bloodbane', 'cerebov'],
]


def unknown_license_names(tiles):
    txt = open(os.path.join(tiles, 'TILES_UNDER_UNKNOWN_LICENSE.md'), encoding='utf-8').read()
    return {os.path.basename(p) for p in re.findall(r'([\w./-]+\.png)', txt)}


def clean(im):
    """바닥 그림자 지우기: 반투명한 검정, 그리고 색 있는 픽셀과 닿지 않은 검정."""
    im = im.convert('RGBA')
    w, h = im.size
    px = im.load()
    def black(c): return c[3] > 0 and c[0] + c[1] + c[2] < 40
    def colored(x, y):
        if not (0 <= x < w and 0 <= y < h): return False
        c = px[x, y]
        return c[3] >= 128 and not black(c)
    drop = []
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            if not black(c): continue
            if c[3] < 255:
                drop.append((x, y)); continue
            if not any(colored(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                drop.append((x, y))
    for x, y in drop: px[x, y] = (0, 0, 0, 0)
    return im, len(drop)


def geometry(im):
    """손잡이 끝 P, 칼끝 T, 코등이 위치 g(P에서 축을 따라 잰 거리), 칼날 반폭 h, 칼날 중심 오프셋 s."""
    w, h = im.size
    px = im.load()
    pts = [(x + .5, y + .5) for y in range(h) for x in range(w) if px[x, y][3] >= 128]
    T = max(pts, key=lambda p: (p[0] - p[1], -p[1]))
    P = min(pts, key=lambda p: (p[0] - p[1], p[1]))
    L = math.hypot(T[0] - P[0], T[1] - P[1])
    ux, uy = (T[0] - P[0]) / L, (T[1] - P[1]) / L
    nx, ny = -uy, ux
    bins = {}
    for x, y in pts:
        t = (x - P[0]) * ux + (y - P[1]) * uy
        s = (x - P[0]) * nx + (y - P[1]) * ny
        b = bins.setdefault(int(t), [s, s])
        b[0] = min(b[0], s); b[1] = max(b[1], s)
    width = {t: v[1] - v[0] for t, v in bins.items()}
    lo, hi = int(L * .12), int(L * .62)
    g = max(range(lo, hi + 1), key=lambda t: (width.get(t, 0), -t))
    blade = [bins[t] for t in bins if g + 2 <= t <= L - 1.5]
    halves = sorted((v[1] - v[0]) / 2 for v in blade) or [1.5]
    centers = sorted((v[0] + v[1]) / 2 for v in blade) or [0]
    return {'P': [round(P[0], 2), round(P[1], 2)], 'T': [round(T[0], 2), round(T[1], 2)],
            'g': round(g + 1, 2), 'h': round(max(1.2, halves[len(halves) // 2] + .5), 2),
            's': round(centers[len(centers) // 2], 2)}


def main():
    tiles = sys.argv[1] if len(sys.argv) > 1 else '/home/user/crawl/tiles'
    banned = unknown_license_names(tiles)
    commit = subprocess.run(['git', '-C', tiles, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    out_dir = os.path.join(ROOT, 'assets', 'swords')
    os.makedirs(out_dir, exist_ok=True)
    data, credits = {}, []
    for key, (folder, name, ko) in SPRITES.items():
        if name + '.png' in banned:
            sys.exit('라이선스 불명 목록에 있는 그림입니다: %s/%s.png' % (folder, name))
        src = os.path.join(tiles, REL, folder, name + '.png')
        im, removed = clean(Image.open(src))
        geo = geometry(im)
        im.save(os.path.join(out_dir, key + '.png'), optimize=True)
        buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True)
        geo.update(src='data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode(), ko=ko)
        data[key] = geo
        credits.append('| `%s.png` | `%s/%s/%s.png` | %s |' % (key, REL, folder, name, ko))
        print('%-13s %-40s 그림자 %3d px 제거  P=%s T=%s g=%.1f h=%.1f' %
              (key, folder + '/' + name, removed, geo['P'], geo['T'], geo['g'], geo['h']))
    for pool in POOLS:
        for k in pool: assert k in data, k
    for pair in SIGNATURE:
        for k in pair: assert k in data, k

    js = ('/* SWORD-SPRITES:BEGIN — tools/build_swords.py 가 만든 구역입니다. 손으로 고치지 마세요.\n'
          '   그림: Dungeon Crawl Stone Soup 타일 (CC0), github.com/crawl/tiles @ %s */\n'
          '  var SPRITE_DATA = %s;\n'
          '  var SPRITE_POOLS = %s;\n'
          '  var SPRITE_SIGNATURE = %s;\n'
          '  /* SWORD-SPRITES:END */') % (commit[:7], json.dumps(data, ensure_ascii=False, separators=(',', ':')),
                                          json.dumps(POOLS), json.dumps(SIGNATURE))
    page = os.path.join(ROOT, 'index.html')
    html = open(page, encoding='utf-8').read()
    a, b = html.find('/* SWORD-SPRITES:BEGIN'), html.find('/* SWORD-SPRITES:END */')
    if a < 0 or b < 0:
        sys.exit('index.html 에 SWORD-SPRITES 표식이 없습니다.')
    html = html[:a] + js + html[b + len('/* SWORD-SPRITES:END */'):]
    open(page, 'w', encoding='utf-8').write(html)

    with open(os.path.join(out_dir, 'CREDITS.md'), 'w', encoding='utf-8') as f:
        f.write('# 검 그림 출처\n\n'
                '모든 그림은 [Dungeon Crawl Stone Soup](https://github.com/crawl/crawl) 의 타일을\n'
                '재사용 가능한 것만 골라 묶은 공식 배포본 [crawl/tiles](https://github.com/crawl/tiles)\n'
                '(커밋 `%s`, 폴더 `%s`)에서 가져왔습니다. 이 배포본은 작가들이 권리를 포기한\n'
                '[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) 그림만 담고 있으며,\n'
                '빌드 스크립트가 `TILES_UNDER_UNKNOWN_LICENSE.md` 목록과 파일 이름을 대조해 확인합니다.\n\n'
                'CC0 는 출처 표기를 요구하지 않지만, 고마운 작가들을 위해 남겨 둡니다.\n'
                '작가 목록: https://github.com/crawl/tiles/blob/master/ARTISTS.md\n\n'
                '바뀐 점: 바닥 그림자를 지웠습니다(반투명 검정, 외곽선 바깥의 검정).\n\n'
                '| 파일 | 원본 | 게임 속 이름 |\n| --- | --- | --- |\n%s\n' % (commit, REL, '\n'.join(credits)))
    print('\n%d 개 그림 처리, index.html 갱신' % len(data))


if __name__ == '__main__':
    main()
