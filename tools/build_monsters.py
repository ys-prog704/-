#!/usr/bin/env python3
"""사냥터 몬스터 그림 빌드 스크립트.

Dungeon Crawl Stone Soup 의 CC0 타일 배포본(https://github.com/crawl/tiles 의 releases/Nov-2015/mon)에서
몬스터 그림을 골라 바닥 그림자를 지우고(build_weapons.py 와 같은 방법)
  1) assets/monsters/*.png 와 CREDITS.md 를 저장하고
  2) index.html 의 /* MONSTER-SPRITES:BEGIN */ ~ /* MONSTER-SPRITES:END */ 사이를 data: URI 로 다시 씁니다.
몬스터의 힘·보상·약점 속성은 index.html 의 MONSTERS 배열에서 정합니다.

쓰기 전에 TILES_UNDER_UNKNOWN_LICENSE.md 와 파일 이름을 대조해서, 목록에 오른 그림이 섞이면 멈춥니다.

사용법:  python3 tools/build_monsters.py /path/to/crawl/tiles
"""
import base64, io, json, os, re, subprocess, sys
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_weapons import clean, unknown_license_names, ROOT, REL   # noqa: E402

# 키: (폴더, 파일 이름, 한국어 이름) — 약한 순서
MONSTERS = {
    'slime':     ('mon/amorphous', 'azure_jelly', '슬라임'),
    'goblin':    ('mon', 'goblin', '고블린'),
    'wolf':      ('mon/animals', 'wolf', '늑대'),
    'orc':       ('mon', 'orc_warrior', '오크 전사'),
    'troll':     ('mon', 'deep_troll', '트롤'),
    'ogre':      ('mon', 'two_headed_ogre', '쌍두 오우거'),
    'cyclops':   ('mon', 'cyclops', '사이클롭스'),
    'lich':      ('mon/undead', 'lich', '리치'),
    'hydra':     ('mon/dragons', 'hydra5', '히드라'),
    'firegiant': ('mon', 'fire_giant', '화염 거인'),
    'dragon':    ('mon/dragons', 'golden_dragon', '황금 드래곤'),
    'demonlord': ('mon/demons', 'balrug', '마왕'),
}


def main():
    tiles = sys.argv[1] if len(sys.argv) > 1 else '/home/user/crawl/tiles'
    banned = unknown_license_names(tiles)
    commit = subprocess.run(['git', '-C', tiles, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    out_dir = os.path.join(ROOT, 'assets', 'monsters')
    os.makedirs(out_dir, exist_ok=True)
    data, credits = {}, []
    for key, (folder, name, ko) in MONSTERS.items():
        if name + '.png' in banned:
            sys.exit('라이선스 불명 목록에 있는 그림입니다: %s/%s.png' % (folder, name))
        src = os.path.join(tiles, REL, folder, name + '.png')
        im, removed = clean(Image.open(src))
        im.save(os.path.join(out_dir, key + '.png'), optimize=True)
        buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True)
        data[key] = {'src': 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode(), 'ko': ko}
        credits.append('| `%s.png` | `%s/%s/%s.png` | %s |' % (key, REL, folder, name, ko))
        print('%-10s %-28s 그림자 %3d px 제거' % (key, folder + '/' + name, removed))
    with open(os.path.join(out_dir, 'CREDITS.md'), 'w', encoding='utf-8') as f:
        f.write('# 몬스터 그림 출처\n\n'
                '모든 몬스터 그림은 [Dungeon Crawl Stone Soup](https://github.com/crawl/crawl) 의 타일을\n'
                '재사용 가능한 것만 골라 묶은 공식 배포본 [crawl/tiles](https://github.com/crawl/tiles)\n'
                '(커밋 `%s`, 폴더 `%s/mon`)에서 가져왔습니다. 이 배포본은 작가들이 권리를 포기한\n'
                '[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) 그림만 담고 있으며,\n'
                '빌드 스크립트가 `TILES_UNDER_UNKNOWN_LICENSE.md` 목록과 파일 이름을 대조해 확인합니다.\n\n'
                '작가 목록: https://github.com/crawl/tiles/blob/master/ARTISTS.md\n\n'
                '바뀐 점: 바닥 그림자를 지웠습니다.\n\n'
                '| 파일 | 원본 | 게임 속 이름 |\n| --- | --- | --- |\n' % (commit, REL) + '\n'.join(credits) + '\n')
    block = ('/* MONSTER-SPRITES:BEGIN — tools/build_monsters.py 가 만든 구역입니다. 손으로 고치지 마세요. */\n'
             '  var MONSTER_DATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n'
             '  /* MONSTER-SPRITES:END */')
    p = os.path.join(ROOT, 'index.html')
    s = open(p, encoding='utf-8').read()
    pat = re.compile(r'/\* MONSTER-SPRITES:BEGIN.*?/\* MONSTER-SPRITES:END \*/', re.S)
    if not pat.search(s):
        sys.exit('index.html 에 MONSTER-SPRITES 표시가 없습니다.')
    s = pat.sub(lambda m: block, s, count=1)
    open(p, 'w', encoding='utf-8').write(s)
    print('index.html 갱신 (%d KB)' % (len(block) // 1024))


if __name__ == '__main__':
    main()
