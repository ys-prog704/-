"""firestore.rules 시험 — Firebase 에뮬레이터에 실제로 써 보며 허용/거부를 확인합니다.

    firebase emulators:start --only auth,firestore --project demo-sword-forge   # 저장소 폴더에서
    python3 tools/test_rules.py

에뮬레이터는 저장소의 firebase.json 을 따라 firestore.rules 를 읽습니다. 표준 라이브러리만 씁니다.
"""
import json, sys, urllib.request, urllib.error, datetime as dt

AUTH = 'http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1'
FS = 'http://127.0.0.1:8080/v1/projects/demo-sword-forge/databases/(default)/documents'
results = []

def call(url, body=None, token=None, method=None):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 method=method or ('POST' if body is not None else 'GET'))
    req.add_header('Content-Type', 'application/json')
    if token: req.add_header('Authorization', 'Bearer ' + token)
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')

def user():
    s, d = call(AUTH + '/accounts:signUp?key=fake', {'returnSecureToken': True})
    return d['localId'], d['idToken']

def val(v):
    if isinstance(v, bool): return {'booleanValue': v}
    if isinstance(v, int): return {'integerValue': str(v)}
    if isinstance(v, str): return {'stringValue': v}
    if isinstance(v, dt.datetime): return {'timestampValue': v.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
    raise TypeError(v)

def write(token, path, fields, server_time_fields=()):
    w = {'update': {'name': 'projects/demo-sword-forge/databases/(default)/documents/' + path,
                    'fields': {k: val(v) for k, v in fields.items()}}}
    if server_time_fields:
        w['updateTransforms'] = [{'fieldPath': f, 'setToServerValue': 'REQUEST_TIME'} for f in server_time_fields]
    s, d = call(FS + ':commit', {'writes': [w]}, token)
    return s

def read(token, path):
    s, d = call(FS + '/' + path, token=token)
    return s

def expect(name, status, ok):
    good = (status == 200) == ok
    results.append(('PASS' if good else 'FAIL', name, status))

utcnow = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
u1, t1 = user(); u2, t2 = user()

# ── 출석 ──
expect('첫 출석 (day=1,total=1,last=서버시간)', write(t1, 'attend/' + u1, {'day': 1, 'total': 1}, ['last']), True)
expect('첫 출석인데 day=3 → 거부', write(t2, 'attend/' + u2, {'day': 3, 'total': 1}, ['last']), False)
expect('같은 날 두 번째 출석 → 거부', write(t1, 'attend/' + u1, {'day': 2, 'total': 2}, ['last']), False)
write('owner', 'attend/' + u1, {'day': 1, 'total': 1, 'last': utcnow - dt.timedelta(hours=25)})
expect('다음 날 출석 → 허용', write(t1, 'attend/' + u1, {'day': 2, 'total': 2}, ['last']), True)
write('owner', 'attend/' + u1, {'day': 2, 'total': 2, 'last': utcnow - dt.timedelta(hours=25)})
expect('칸 건너뛰기(day 2→4) → 거부', write(t1, 'attend/' + u1, {'day': 4, 'total': 3}, ['last']), False)
expect('total 부풀리기 → 거부', write(t1, 'attend/' + u1, {'day': 3, 'total': 9}, ['last']), False)
expect('last 를 서버시간 대신 직접 지정 → 거부', write(t1, 'attend/' + u1, {'day': 3, 'total': 3, 'last': utcnow}), False)
expect('모르는 필드 추가 → 거부', write(t1, 'attend/' + u1, {'day': 3, 'total': 3, 'gold': 999}, ['last']), False)
expect('정상 다음 칸 → 허용', write(t1, 'attend/' + u1, {'day': 3, 'total': 3}, ['last']), True)
write('owner', 'attend/' + u1, {'day': 6, 'total': 13, 'last': utcnow - dt.timedelta(hours=25)})
expect('7칸 주기 순환(day 6→0) → 허용', write(t1, 'attend/' + u1, {'day': 0, 'total': 14}, ['last']), True)
# 한국 시간 자정 경계
kst_today0 = (utcnow + dt.timedelta(hours=9)).replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(hours=9)
write('owner', 'attend/' + u1, {'day': 0, 'total': 14, 'last': kst_today0 - dt.timedelta(minutes=1)})
expect('마지막 수령이 어제 23:59 (한국시간) → 오늘 허용', write(t1, 'attend/' + u1, {'day': 1, 'total': 15}, ['last']), True)
write('owner', 'attend/' + u1, {'day': 1, 'total': 15, 'last': kst_today0 + dt.timedelta(minutes=1)})
expect('마지막 수령이 오늘 00:01 (한국시간) → 거부', write(t1, 'attend/' + u1, {'day': 2, 'total': 16}, ['last']), False)
expect('남의 출석 쓰기 → 거부', write(t2, 'attend/' + u1, {'day': 2, 'total': 16}, ['last']), False)
expect('남의 출석 읽기 → 거부', read(t2, 'attend/' + u1), False)
expect('내 출석 읽기 → 허용', read(t1, 'attend/' + u1), True)

# ── 저장 ──
expect('내 저장 쓰기 → 허용', write(t1, 'saves/' + u1, {'code': 'SWORD4-abc-00'}, ['at']), True)
expect('내 저장 읽기 → 허용', read(t1, 'saves/' + u1), True)
expect('남의 저장 읽기 → 거부', read(t2, 'saves/' + u1), False)
expect('남의 저장 덮어쓰기 → 거부', write(t2, 'saves/' + u1, {'code': 'x'}, ['at']), False)
expect('너무 긴 저장(4001자) → 거부', write(t1, 'saves/' + u1, {'code': 'x' * 4001}, ['at']), False)
expect('로그인 안 한 사람 읽기 → 거부', read(None, 'saves/' + u1), False)

# ── 랭킹 ──
rk = lambda best, peak, **kw: dict({'name': '성연', 'best': best, 'peak': peak, 'score': best * 10**12 + peak,
                                    'sword': '종말의 화염도', 'rar': 4, 'el': 0}, **kw)
expect('정상 랭킹 기록 → 허용', write(t1, 'ranking/' + u1, rk(17, 5200000), ['at']), True)
expect('로그인 안 해도 랭킹 읽기 → 허용', read(None, 'ranking/' + u1), True)
expect('점수 계산 조작 → 거부', write(t1, 'ranking/' + u1, rk(17, 5200000, score=99 * 10**12), ['at']), False)
expect('합성 +21 → 허용', write(t1, 'ranking/' + u1, rk(21, 1000), ['at']), True)
expect('최고 강화 +22 → 거부', write(t1, 'ranking/' + u1, rk(22, 0), ['at']), False)
expect('이름 13자 → 거부', write(t1, 'ranking/' + u1, rk(5, 0, name='가' * 13), ['at']), False)
expect('남의 랭킹 쓰기 → 거부', write(t2, 'ranking/' + u1, rk(20, 0), ['at']), False)
expect('알 수 없는 컬렉션 쓰기 → 거부', write(t1, 'cheat/' + u1, {'gold': 1}), False)

# ── 결투장 ──
def update_c(token, path, value=True, extra=None):
    fields = {'c': value}
    fields.update(extra or {})
    w = {'update': {'name': 'projects/demo-sword-forge/databases/(default)/documents/' + path,
                    'fields': {k: val(v) for k, v in fields.items()}},
         'updateMask': {'fieldPaths': list(fields)}, 'currentDocument': {'exists': True}}
    st, d = call(FS + ':commit', {'writes': [w]}, token)
    return st

def query(token, coll, eqs):
    q = {'structuredQuery': {'from': [{'collectionId': coll}], 'where': {'compositeFilter': {'op': 'AND', 'filters': [
        {'fieldFilter': {'field': {'fieldPath': f}, 'op': 'EQUAL', 'value': val(v)}} for f, v in eqs]}}, 'limit': 50}}
    st, d = call(FS + ':runQuery', q, token)
    return st

ar = lambda lv, rar, **kw: dict({'name': '성연', 'lv': lv, 'rar': rar, 'el': 3, 'kind': 1, 'seed': 4242,
                                 'pw': lv + rar + (2 if lv > 20 else 0)}, **kw)
u3, t3 = user()
expect('대표 무기 올리기 → 허용', write(t1, 'arena/' + u1, ar(15, 2), ['at']), True)
expect('+21 각성 대표 무기 (힘 = 21 + 등급 + 2) → 허용', write(t2, 'arena/' + u2, ar(21, 4), ['at']), True)
expect('힘 부풀리기 → 거부', write(t1, 'arena/' + u1, ar(15, 2, pw=30), ['at']), False)
expect('단계 +22 → 거부', write(t1, 'arena/' + u1, ar(22, 0), ['at']), False)
expect('씨앗이 32비트를 넘음 → 거부', write(t1, 'arena/' + u1, ar(5, 0, seed=4294967296), ['at']), False)
expect('남의 대표 무기 쓰기 → 거부', write(t2, 'arena/' + u1, ar(1, 0), ['at']), False)
expect('모르는 필드 → 거부', write(t1, 'arena/' + u1, ar(5, 0, gold=1), ['at']), False)
expect('특수 무기(종류 5) 대표 무기 → 허용', write(t1, 'arena/' + u1, ar(9, 1, kind=5), ['at']), True)
expect('없는 종류(6) → 거부', write(t1, 'arena/' + u1, ar(9, 1, kind=6), ['at']), False)
expect('로그인 안 해도 대표 무기 보기 → 허용', read(None, 'arena/' + u2), True)

du = lambda a, d, win=True, **kw: dict({'a': a, 'd': d, 'an': '성연', 'dn': '상대', 'ap': 17, 'dp': 27, 'aw': '+15 얼음달 도끼',
                                       'win': win, 'gold': 1200000, 'def': 0, 'c': False}, **kw)
expect('결투 기록 남기기 (도전한 사람 = 나) → 허용', write(t1, 'duels/d1', du(u1, u2), ['at']), True)
expect('진 결투 기록 (방어 보상 def) → 허용', write(t1, 'duels/d2', du(u1, u2, win=False, gold=0, **{'def': 360000}), ['at']), True)
expect('남인 척 기록 (a ≠ 나) → 거부', write(t3, 'duels/d3', du(u1, u2), ['at']), False)
expect('나에게 도전 → 거부', write(t1, 'duels/d4', du(u1, u1), ['at']), False)
expect('결투장에 없는 사람에게 도전 → 거부', write(t1, 'duels/d5', du(u1, u3), ['at']), False)
expect('보상 받음으로 만들기(c=true) → 거부', write(t1, 'duels/d6', du(u1, u2, c=True), ['at']), False)
expect('보상 부풀리기(1억 초과) → 거부', write(t1, 'duels/d7', du(u1, u2, gold=100000001), ['at']), False)
expect('도전한 사람은 기록을 볼 수 있음', read(t1, 'duels/d1'), True)
expect('방어한 사람도 볼 수 있음', read(t2, 'duels/d1'), True)
expect('다른 사람은 못 봄', read(t3, 'duels/d1'), False)
expect('방어한 사람: 내게 온 안 받은 도전 목록 → 허용', query(t2, 'duels', [('d', u2), ('c', False)]), True)
expect('남에게 온 도전 목록 → 거부', query(t3, 'duels', [('d', u2), ('c', False)]), False)
expect('도전한 사람은 보상 받음(c)을 못 바꿈', update_c(t1, 'duels/d2'), False)
expect('방어한 사람이 다른 값까지 바꾸기 → 거부', update_c(t2, 'duels/d2', True, {'def': 9000000}), False)
expect('방어한 사람이 보상 받음(c) 켜기 → 허용', update_c(t2, 'duels/d2'), True)
expect('이미 받은 보상 다시 받기 → 거부', update_c(t2, 'duels/d2'), False)

# ── 단톡방 ──
def commit(token, writes):
    st, d = call(FS + ':commit', {'writes': writes}, token)
    return st

def wr(path, fields, server_time=()):
    w = {'update': {'name': 'projects/demo-sword-forge/databases/(default)/documents/' + path,
                    'fields': {k: val(v) for k, v in fields.items()}}}
    if server_time:
        w['updateTransforms'] = [{'fieldPath': f, 'setToServerValue': 'REQUEST_TIME'} for f in server_time]
    return w

def delete(token, path):
    return commit(token, [{'delete': 'projects/demo-sword-forge/databases/(default)/documents/' + path}])

def room_query(token, room):
    q = {'structuredQuery': {'from': [{'collectionId': 'msgs'}], 'orderBy': [{'field': {'fieldPath': 'at'}, 'direction': 'DESCENDING'}], 'limit': 50}}
    st, d = call(FS + '/rooms/' + room + ':runQuery', q, token)
    return st

mem = lambda **kw: dict({'name': '성연', 'lv': 12, 'rar': 1, 'el': 2, 'kind': 1, 'seed': 21, 'pw': 13, 'best': 15}, **kw)
msg = lambda uid, **kw: dict({'uid': uid, 'name': '성연', 'text': '안녕!', 'kind': 'chat'}, **kw)
u4, t4 = user()
expect('방 만들기 (만든 사람 = 나)', write(t1, 'rooms/r1', {'name': '우리 대장간', 'owner': u1}, ['at']), True)
expect('남을 만든 사람으로 → 거부', write(t1, 'rooms/r2', {'name': '가짜', 'owner': u2}, ['at']), False)
expect('방 이름 21자 → 거부', write(t1, 'rooms/r3', {'name': '가' * 21, 'owner': u1}, ['at']), False)
expect('로그인한 사람은 방 이름 보기 (초대 링크)', read(t2, 'rooms/r1'), True)
expect('로그인 안 하면 방 못 봄', read(None, 'rooms/r1'), False)
expect('방 만들기 + 내 자리 + 첫 메시지를 한 번에 → 허용',
       commit(t1, [wr('rooms/r9', {'name': '한 번에', 'owner': u1}, ['at']), wr('rooms/r9/members/' + u1, mem(), ['at']),
                   wr('rooms/r9/msgs/m0', msg(u1, kind='bot', text='방을 만들었어요'), ['at'])]), True)
expect('방장 자리 → 허용', write(t1, 'rooms/r1/members/' + u1, mem(), ['at']), True)
expect('초대받은 사람 들어가기 → 허용', write(t2, 'rooms/r1/members/' + u2, mem(name='민수', pw=13), ['at']), True)
expect('없는 방에 들어가기 → 거부', write(t2, 'rooms/nope/members/' + u2, mem(), ['at']), False)
expect('남의 자리 만들기 → 거부', write(t2, 'rooms/r1/members/' + u3, mem(), ['at']), False)
expect('힘 부풀린 자리 → 거부', write(t2, 'rooms/r1/members/' + u2, mem(pw=30), ['at']), False)
expect('최고 단계 +22 → 거부', write(t2, 'rooms/r1/members/' + u2, mem(best=22), ['at']), False)
expect('방 사람은 방 사람 목록 보기', read(t2, 'rooms/r1/members/' + u1), True)
expect('방 밖 사람은 방 사람 못 봄', read(t4, 'rooms/r1/members/' + u1), False)
expect('방 사람 메시지 쓰기 → 허용', write(t2, 'rooms/r1/msgs/a1', msg(u2, name='민수'), ['at']), True)
expect('대장간봇 메시지(kind=bot) → 허용', write(t1, 'rooms/r1/msgs/a2', msg(u1, kind='bot', text='성연님 +13 강화 성공!'), ['at']), True)
expect('방 밖 사람 메시지 → 거부', write(t4, 'rooms/r1/msgs/a3', msg(u4), ['at']), False)
expect('남인 척 메시지 (uid ≠ 나) → 거부', write(t2, 'rooms/r1/msgs/a4', msg(u1), ['at']), False)
expect('메시지 301자 → 거부', write(t2, 'rooms/r1/msgs/a5', msg(u2, text='가' * 301), ['at']), False)
expect('모르는 종류(kind) → 거부', write(t2, 'rooms/r1/msgs/a6', msg(u2, kind='admin'), ['at']), False)
expect('시간을 직접 지정 → 거부', write(t2, 'rooms/r1/msgs/a7', dict(msg(u2), at=utcnow)), False)
expect('메시지 고치기 → 거부', write(t2, 'rooms/r1/msgs/a1', msg(u2, text='고침'), ['at']), False)
expect('방 사람은 메시지 목록 보기', room_query(t2, 'r1'), True)
expect('방 밖 사람은 메시지 목록 못 봄', room_query(t4, 'r1'), False)
expect('방장은 방 이름 바꾸기', commit(t1, [dict(wr('rooms/r1', {'name': '새 이름'}), updateMask={'fieldPaths': ['name']})]), True)
expect('방장이 아니면 이름 못 바꿈', commit(t2, [dict(wr('rooms/r1', {'name': '뺏기'}), updateMask={'fieldPaths': ['name']})]), False)
expect('나가기 (내 자리 지우기) → 허용', delete(t2, 'rooms/r1/members/' + u2), True)
expect('나간 뒤에는 메시지 못 씀', write(t2, 'rooms/r1/msgs/a8', msg(u2), ['at']), False)
expect('남의 자리 지우기 → 거부', delete(t2, 'rooms/r1/members/' + u1), False)

# ── 운영자 ── (admins/{uid} 는 콘솔에서 만드는 것이라 시험에서는 규칙을 건너뛰는 owner 로 만듦)
ua, ta = user()
write('owner', 'admins/' + ua, {'name': '운영자'})
expect('운영자는 자기가 운영자인지 확인', read(ta, 'admins/' + ua), True)
expect('남의 운영자 문서 보기 → 거부', read(t1, 'admins/' + ua), False)
expect('게임에서 운영자 문서 만들기 → 거부', write(t1, 'admins/' + u1, {'name': '나'}), False)
expect('운영자도 게임에서 운영자를 늘릴 수 없음', write(ta, 'admins/' + u4, {'name': '부운영자'}), False)

# 공지
expect('운영자 공지 올리기', write(ta, 'notice/main', {'text': '추석 이벤트!'}, ['at']), True)
expect('로그인 안 해도 공지 보기', read(None, 'notice/main'), True)
expect('일반 사람 공지 쓰기 → 거부', write(t1, 'notice/main', {'text': '가짜 공지'}, ['at']), False)
expect('공지 201자 → 거부', write(ta, 'notice/main', {'text': '가' * 201}, ['at']), False)
expect('notice/main 말고 다른 공지 → 거부', write(ta, 'notice/other', {'text': 'x'}, ['at']), False)
expect('일반 사람 공지 내리기 → 거부', delete(t1, 'notice/main'), False)
expect('운영자 공지 내리기', delete(ta, 'notice/main'), True)

# 선물
gf = lambda to, **kw: dict({'to': to, 'toName': '', 'gold': 1000000, 'item': 'bless', 'n': 2, 'msg': '추석 선물'}, **kw)
expect('운영자 선물 (모두에게)', write(ta, 'gifts/g1', gf('all'), ['at']), True)
expect('운영자 선물 (한 사람에게)', write(ta, 'gifts/g2', gf(u2, toName='민수'), ['at']), True)
expect('일반 사람 선물 만들기 → 거부', write(t1, 'gifts/g3', gf(u1), ['at']), False)
expect('없어진 파괴 방지권 선물 → 거부', write(ta, 'gifts/g4', gf('all', item='protect'), ['at']), False)
expect('골드 1000억 초과 → 거부', write(ta, 'gifts/g5', gf('all', gold=100000000001), ['at']), False)
expect('모두에게 온 선물 보기', read(t1, 'gifts/g1'), True)
expect('나에게 온 선물 보기', read(t2, 'gifts/g2'), True)
expect('남에게 온 선물 보기 → 거부', read(t1, 'gifts/g2'), False)
expect('나에게 온 선물 목록', query(t2, 'gifts', [('to', u2)]), True)
expect('모두에게 온 선물 목록', query(t1, 'gifts', [('to', 'all')]), True)
expect('남에게 온 선물 목록 → 거부', query(t1, 'gifts', [('to', u2)]), False)
expect('선물 받기 (한 번)', write(t1, 'gifts/g1/got/' + u1, {}, ['at']), True)
expect('같은 선물 두 번 받기 → 거부', write(t1, 'gifts/g1/got/' + u1, {}, ['at']), False)
expect('남에게 온 선물 받기 → 거부', write(t1, 'gifts/g2/got/' + u1, {}, ['at']), False)
expect('남 대신 받기 → 거부', write(t1, 'gifts/g1/got/' + u3, {}, ['at']), False)
expect('받은 기록 지우기 (다시 받으려고) → 거부', delete(t1, 'gifts/g1/got/' + u1), False)
expect('운영자는 받은 기록 보기', read(ta, 'gifts/g1/got/' + u1), True)
expect('운영자는 선물 거두기', delete(ta, 'gifts/g2'), True)

# 막기
expect('일반 사람이 막기 → 거부', write(t1, 'bans/' + u3, {'name': 'x'}, ['at']), False)
expect('운영자가 막기', write(ta, 'bans/' + u3, {'name': '치트맨'}, ['at']), True)
expect('막힌 사람은 자기가 막힌 걸 봄', read(t3, 'bans/' + u3), True)
expect('남의 막힘 보기 → 거부', read(t1, 'bans/' + u3), False)
expect('막힌 사람 랭킹 쓰기 → 거부', write(t3, 'ranking/' + u3, rk(5, 100), ['at']), False)
expect('막힌 사람 결투장 → 거부', write(t3, 'arena/' + u3, ar(5, 0), ['at']), False)
expect('막힌 사람 결투 기록 → 거부', write(t3, 'duels/d9', du(u3, u2), ['at']), False)
expect('막힌 사람 단톡방 들어가기 → 거부', write(t3, 'rooms/r1/members/' + u3, mem(), ['at']), False)
expect('막힌 사람 선물 받기 → 거부', write(t3, 'gifts/g1/got/' + u3, {}, ['at']), False)
expect('일반 사람이 남의 랭킹 지우기 → 거부', delete(t2, 'ranking/' + u1), False)
expect('운영자가 남의 랭킹 지우기', delete(ta, 'ranking/' + u1), True)
expect('운영자가 남의 결투장 지우기', delete(ta, 'arena/' + u2), True)
expect('운영자가 막기 풀기', delete(ta, 'bans/' + u3), True)
expect('풀린 뒤 랭킹 쓰기 → 허용', write(t3, 'ranking/' + u3, rk(5, 100), ['at']), True)

# 단톡방 관리 (r1 에는 방장 u1 이 있음)
expect('운영자는 방 밖에서도 메시지 목록 보기', room_query(ta, 'r1'), True)
expect('운영자는 방 사람 보기', read(ta, 'rooms/r1/members/' + u1), True)
expect('운영자 메시지(kind=admin) 쓰기', write(ta, 'rooms/r1/msgs/z1', msg(ua, kind='admin', name='운영자', text='공지예요'), ['at']), True)
expect('운영자도 남인 척은 → 거부', write(ta, 'rooms/r1/msgs/z2', msg(u1, kind='admin'), ['at']), False)
expect('일반 사람이 메시지 지우기 → 거부', delete(t1, 'rooms/r1/msgs/a2'), False)
expect('운영자가 메시지 지우기', delete(ta, 'rooms/r1/msgs/a2'), True)
expect('운영자가 방 사람 내보내기', delete(ta, 'rooms/r1/members/' + u1), True)

# 출석 되돌리기 (운영자 시험용)
expect('운영자는 자기 출석을 되돌릴 수 있음', write(ta, 'attend/' + ua, {'day': 3, 'total': 3, 'last': utcnow - dt.timedelta(days=1)}), True)
expect('운영자도 남의 출석은 못 고침', write(ta, 'attend/' + u1, {'day': 0, 'total': 0, 'last': utcnow}), False)

for r, n, s in results: print('%s  %s  (HTTP %d)' % (r, n, s))
fails = [n for r, n, _ in results if r == 'FAIL']
print('\n%d/%d 통과' % (len(results) - len(fails), len(results)) + ('' if not fails else '  실패: ' + ', '.join(fails)))
sys.exit(1 if fails else 0)
