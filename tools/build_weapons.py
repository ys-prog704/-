#!/usr/bin/env python3
"""무기 그림 빌드 스크립트.

Dungeon Crawl Stone Soup 의 CC0 타일 배포본(https://github.com/crawl/tiles 의
releases/Nov-2015)에서 검·도끼·지팡이·창·철퇴 그림을 골라
  1) 바닥 그림자를 지우고
  2) 끝·손잡이 끝·이펙트가 시작될 자리(검은 코등이, 나머지는 머리 부분)·폭을 계산해서
  3) assets/weapons/*.png 로 저장하고
  4) index.html 의 /* WEAPON-SPRITES:BEGIN */ ~ /* WEAPON-SPRITES:END */ 사이를
     data: URI 와 위치 정보로 다시 씁니다.

쓰기 전에 crawl/tiles 의 TILES_UNDER_UNKNOWN_LICENSE.md 와 파일 이름을 대조해서,
목록에 오른 그림이 하나라도 섞이면 멈춥니다.

사용법:  python3 tools/build_weapons.py /path/to/crawl/tiles
"""
import base64, io, json, math, os, re, subprocess, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = 'releases/Nov-2015'

# 키: (폴더, 파일 이름, 한국어 이름). 키는 모든 종류를 통틀어 겹치지 않아야 합니다.
SWORDS = {
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
U, W, A = 'UNUSED/weapons', 'item/weapon', 'item/weapon/artefact'
AXES = {
    'handAxe1': (W, 'hand_axe1', '손도끼'), 'handAxe2': (W, 'hand_axe2', '손도끼'), 'handAxe3': (W, 'hand_axe3', '손도끼'),
    'warAxe4': (U, 'war_axe4', '전투도끼'), 'warAxe5': (U, 'war_axe5', '전투도끼'),
    'warAxe6': (U, 'war_axe6', '전투도끼'), 'warAxe7': (U, 'war_axe7', '전투도끼'),
    'broadAxe4': (U, 'broad_axe4', '대도끼'), 'broadAxe5': (U, 'broad_axe5', '대도끼'),
    'broadAxe6': (U, 'broad_axe6', '대도끼'), 'broadAxe7': (U, 'broad_axe7', '대도끼'),
    'battleAxe4': (U, 'battle_axe4', '양날도끼'), 'battleAxe5': (U, 'battle_axe5', '양날도끼'),
    'battleAxe6': (U, 'battle_axe6', '양날도끼'), 'battleAxe7': (U, 'battle_axe7', '양날도끼'),
    'execAxe4': (U, 'executioner_axe4', '처형도끼'), 'execAxe5': (U, 'executioner_axe5', '처형도끼'),
    'execAxe6': (U, 'executioner_axe6', '처형도끼'), 'execAxe7': (U, 'executioner_axe7', '처형도끼'),
    'arga':      (A, 'urand_arga', '얼음달 도끼'),
    'woe':       (A, 'urand_axe_of_woe', '불꽃 군주의 도끼'),
    'trog':      (A, 'spwpn_wrath_of_trog', '광전사의 분노'),
    'trog2':     (U, 'spwpn_wrath_of_trog2', '피의 군주 쌍도끼'),
}
STAVES = {
    'qstaff1': (W, 'quarterstaff', '지팡이'), 'qstaff2': (W, 'quarterstaff2', '마법 지팡이'),
    'qstaff3': (W, 'quarterstaff3', '마법 지팡이'), 'mummyStaff': (W, 'staff_mummy', '황금 지팡이'),
    'dispater': (A, 'spwpn_staff_of_dispater', '태양신의 황금 지팡이'),
    'olgreb':   (A, 'spwpn_staff_of_olgreb', '독초 마녀의 지팡이'),
    'majin':    (A, 'spwpn_majin', '그림자 마왕의 지팡이'),
    'wucadMu':  (A, 'spwpn_wucad_mu', '폭풍 현자의 지팡이'),
}
SPEARS = {
    'spear1': (W, 'spear1', '창'), 'spear2': (W, 'spear2', '창'), 'spear3': (W, 'spear3', '창'),
    'spear4': (U, 'spear4', '창'), 'spear5': (U, 'spear5', '창'), 'spear6': (U, 'spear6', '창'), 'spear7': (U, 'spear7', '창'),
    'halberd4': (U, 'halberd4', '미늘창'), 'halberd5': (U, 'halberd5', '미늘창'),
    'bardiche4': (U, 'bardiche4', '도끼창'), 'bardiche5': (U, 'bardiche5', '도끼창'),
    'scythe1': (W, 'scythe1', '큰 낫'), 'scythe2': (W, 'scythe2', '큰 낫'), 'scythe3': (W, 'scythe3', '큰 낫'),
    'crystalSpear': (A, 'urand_crystal_spear', '얼음 수정창'),
    'curseScythe':  (A, 'spwpn_scythe_of_curses', '저주받은 사신의 낫'),
    'prune':        (A, 'spwpn_glaive_of_prune', '은하를 휘감는 창'),
    'guard':        (A, 'urand_guard', '수호 기사의 미늘창'),
    'wyrmbane':     (A, 'urand_wyrmbane', '용 사냥꾼의 창'),
    'octopus':      (A, 'urand_octopus_king', '심해 군주의 삼지창'),
}
MACES = {
    'club': (W, 'club', '몽둥이'), 'club2': (W, 'club2', '몽둥이'),
    'mace1': (W, 'mace1', '철퇴'), 'mace2': (W, 'mace2', '철퇴'), 'mace3': (W, 'mace3', '철퇴'),
    'maceL1': (W, 'mace_large1', '큰 철퇴'), 'maceL2': (W, 'mace_large2', '큰 철퇴'), 'maceL3': (W, 'mace_large3', '큰 철퇴'),
    'mace7': (U, 'mace7', '돌기 철퇴'),
    'mstar1': (W, 'morningstar1', '가시철퇴'), 'mstar2': (W, 'morningstar2', '가시철퇴'), 'mstar3': (W, 'morningstar3', '가시철퇴'),
    'mstar4': (U, 'morningstar4', '가시철퇴'), 'mstar5': (U, 'morningstar5', '가시철퇴'), 'mstar7': (U, 'morningstar7', '가시철퇴'),
    'estar1': (W, 'eveningstar1', '큰 가시철퇴'), 'estar2': (W, 'eveningstar2', '큰 가시철퇴'),
    'estar3': (W, 'eveningstar3', '큰 가시철퇴'), 'estar4': (U, 'eveningstar4', '큰 가시철퇴'),
    'estar7': (U, 'eveningstar7', '큰 가시철퇴'),
    'hammer1': (U, 'hammer1', '전투망치'), 'hammer2': (U, 'hammer2', '전투망치'), 'hammer3': (U, 'hammer3', '전투망치'),
    'spikedClub': (W, 'giant_spiked_club', '가시 곤봉'),
    'firestarter': (A, 'urand_firestarter', '불씨의 철퇴'),
    'asmodeus':    (A, 'spwpn_sceptre_of_asmodeus', '지옥 군주의 홀'),
    'brilliance':  (A, 'urand_brilliance', '광휘의 철퇴'),
    'undeadhunter': (A, 'urand_undeadhunter', '망자 사냥꾼의 철퇴'),
    'skullcrusher': (A, 'urand_skullcrusher', '해골 분쇄기'),
    'torment':     (A, 'spwpn_sceptre_of_torment', '고통의 홀'),
    'variability': (A, 'spwpn_mace_of_variability', '변덕쟁이 무지개 망치'),
    'eos':         (A, 'urand_eos', '새벽별 철퇴'),
}
# 무기 종류 — index.html 의 KINDS 와 순서가 같아야 합니다 (0 검 · 1 도끼 · 2 지팡이 · 3 창 · 4 철퇴)
KINDS = [SWORDS, AXES, STAVES, SPEARS, MACES]

# [종류][등급] — 일반 · 희귀 · 영웅 등급에서 seed 로 고르는 그림
POOLS = [
    [['dagger', 'short1', 'short6', 'long1', 'long6', 'great1', 'falchion1', 'falchion4',
      'scimitar1', 'rapier1', 'cutlass1', 'cutlass5', 'claymore'],
     ['short2', 'short3', 'short5', 'long3', 'falchion2', 'falchion3', 'rapier3', 'cutlass3',
      'cutlass9', 'great3u', 'double1', 'katana2', 'dagger3'],
     ['great3', 'long5', 'long7', 'claymore2', 'claymoreB', 'falchion5', 'falchion7',
      'triple1', 'triple2', 'double2']],
    [['handAxe1', 'warAxe4', 'warAxe6', 'broadAxe4', 'broadAxe6', 'battleAxe4', 'battleAxe6', 'execAxe4', 'execAxe6'],
     ['handAxe2', 'warAxe5', 'broadAxe5', 'battleAxe5', 'execAxe5'],
     ['handAxe3', 'warAxe7', 'broadAxe7', 'battleAxe7', 'execAxe7']],
    [['qstaff1'], ['qstaff2', 'qstaff3'], ['mummyStaff', 'qstaff3']],
    [['spear1', 'spear4', 'spear6', 'halberd4', 'bardiche4', 'scythe1'],
     ['spear5', 'halberd5', 'bardiche5', 'scythe2'],
     ['spear2', 'spear3', 'spear7', 'scythe3']],
    [['club', 'mace1', 'maceL1', 'mstar1', 'mstar4', 'estar1', 'hammer1', 'spikedClub'],
     ['club2', 'mace2', 'maceL2', 'mstar2', 'mstar5', 'estar4', 'hammer2', 'mace7'],
     ['mace3', 'maceL3', 'mstar3', 'mstar7', 'estar2', 'estar3', 'estar7', 'hammer3']],
]
# [종류][속성] = [전설, 신화] — 속성마다 정해진 이름 있는 무기. None 이면 그 종류는 그 등급에 나오지 않습니다.
# 속성 순서: 화염 서리 뇌전 암흑 성광 맹독 질풍 대지 성운 혈염. 검은 모든 칸이 차 있어야 합니다.
_ = None
SIGNATURE = [
    [['power', 'flamingDeath'], ['chillyDeath', 'winter'], ['great4', 'arcBlade'],
     ['doomKnight', 'zonguldrok'], ['golden', 'order'], ['scimitar3', 'plutonium'],
     ['galeCutlass', 'gyre'], ['morg', 'ancient'], ['katana1', 'claymore3'],
     ['bloodbane', 'cerebov']],
    [[_, 'woe'], ['arga', _], [_, _], [_, _], [_, _], [_, _], [_, _], [_, _], [_, _], ['trog', 'trog2']],
    [[_, _], [_, _], ['wucadMu', _], [_, 'majin'], [_, 'dispater'], ['olgreb', _], [_, _], [_, _], [_, _], [_, _]],
    [[_, _], ['crystalSpear', _], [_, _], ['curseScythe', _], ['guard', _], ['wyrmbane', _], [_, _], [_, _],
     [_, 'prune'], ['octopus', _]],
    [['firestarter', 'asmodeus'], [_, _], [_, _], ['torment', _], ['brilliance', 'undeadhunter'], [_, _], [_, _],
     [_, _], ['eos', 'variability'], ['skullcrusher', _]],
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


def geometry(im, kind=0):
    """손잡이 끝 P, 끝 T, 이펙트가 시작될 자리 g(P에서 축을 따라 잰 거리), 반폭 h, 중심 오프셋 s.

    검은 g 가 코등이(손잡이 쪽에서 가장 넓은 곳)이고, 도끼·지팡이·창·철퇴는 자루보다 눈에 띄게 넓어지는
    머리가 시작되는 곳입니다(머리가 따로 없으면 끝에서 38% 지점). 불꽃·번개·룬·빛의 흐름이 g 부터 T 까지 나옵니다."""
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
    if kind == 0:
        lo, hi = int(L * .12), int(L * .62)
        g = max(range(lo, hi + 1), key=lambda t: (width.get(t, 0), -t))
    else:
        shaft = sorted(width.get(t, 0) for t in range(int(L * .15), int(L * .5) + 1)) or [2]
        thick = shaft[len(shaft) // 2]
        head = next((t for t in range(int(L * .4), int(L * .92) + 1) if width.get(t, 0) > thick + 2), int(L * .62))
        g = head - 1
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
    out_dir = os.path.join(ROOT, 'assets', 'weapons')
    os.makedirs(out_dir, exist_ok=True)
    data, credits = {}, []
    sprites = [(key, spec, kind) for kind, group in enumerate(KINDS) for key, spec in group.items()]
    keys = [k for k, _, _ in sprites]
    assert len(keys) == len(set(keys)), '키가 겹칩니다'
    for key, (folder, name, ko), kind in sprites:
        if name + '.png' in banned:
            sys.exit('라이선스 불명 목록에 있는 그림입니다: %s/%s.png' % (folder, name))
        src = os.path.join(tiles, REL, folder, name + '.png')
        im, removed = clean(Image.open(src))
        geo = geometry(im, kind)
        im.save(os.path.join(out_dir, key + '.png'), optimize=True)
        buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True)
        geo.update(src='data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode(), ko=ko)
        data[key] = geo
        credits.append('| `%s.png` | `%s/%s/%s.png` | %s |' % (key, REL, folder, name, ko))
        print('%-13s %-40s 그림자 %3d px 제거  P=%s T=%s g=%.1f h=%.1f' %
              (key, folder + '/' + name, removed, geo['P'], geo['T'], geo['g'], geo['h']))
    assert len(POOLS) == len(SIGNATURE) == len(KINDS)
    for kind, (pools, sig) in enumerate(zip(POOLS, SIGNATURE)):
        assert len(pools) == 3 and len(sig) == 10, kind
        for pool in pools:
            assert pool, kind
            for k in pool: assert k in KINDS[kind], k
        for pair in sig:
            for k in pair:
                assert (k is not None) or kind > 0, '검은 모든 속성에 전설·신화가 있어야 합니다'
                assert k is None or k in KINDS[kind], k

    js = ('/* WEAPON-SPRITES:BEGIN — tools/build_weapons.py 가 만든 구역입니다. 손으로 고치지 마세요.\n'
          '   그림: Dungeon Crawl Stone Soup 타일 (CC0), github.com/crawl/tiles @ %s */\n'
          '  var SPRITE_DATA = %s;\n'
          '  var SPRITE_POOLS = %s;\n'
          '  var SPRITE_SIGNATURE = %s;\n'
          '  /* WEAPON-SPRITES:END */') % (commit[:7], json.dumps(data, ensure_ascii=False, separators=(',', ':')),
                                          json.dumps(POOLS), json.dumps(SIGNATURE))
    page = os.path.join(ROOT, 'index.html')
    html = open(page, encoding='utf-8').read()
    a, b = html.find('/* WEAPON-SPRITES:BEGIN'), html.find('/* WEAPON-SPRITES:END */')
    if a < 0 or b < 0:
        sys.exit('index.html 에 WEAPON-SPRITES 표식이 없습니다.')
    html = html[:a] + js + html[b + len('/* WEAPON-SPRITES:END */'):]
    open(page, 'w', encoding='utf-8').write(html)

    with open(os.path.join(out_dir, 'CREDITS.md'), 'w', encoding='utf-8') as f:
        f.write('# 무기 그림 출처\n\n'
                '+21 각성 그림(`awakened/`)을 뺀 모든 무기 그림은 [Dungeon Crawl Stone Soup](https://github.com/crawl/crawl) 의 타일을\n'
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
