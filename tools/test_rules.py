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
expect('최고 강화 +21 → 거부', write(t1, 'ranking/' + u1, rk(21, 0), ['at']), False)
expect('이름 13자 → 거부', write(t1, 'ranking/' + u1, rk(5, 0, name='가' * 13), ['at']), False)
expect('남의 랭킹 쓰기 → 거부', write(t2, 'ranking/' + u1, rk(20, 0), ['at']), False)
expect('알 수 없는 컬렉션 쓰기 → 거부', write(t1, 'cheat/' + u1, {'gold': 1}), False)

for r, n, s in results: print('%s  %s  (HTTP %d)' % (r, n, s))
fails = [n for r, n, _ in results if r == 'FAIL']
print('\n%d/%d 통과' % (len(results) - len(fails), len(results)) + ('' if not fails else '  실패: ' + ', '.join(fails)))
sys.exit(1 if fails else 0)
