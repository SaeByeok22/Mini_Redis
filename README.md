# Mini Redis

Python 3.11 표준 라이브러리만으로 만든 asyncio 기반 mini Redis 서버다.

## 현재 구현

- `asyncio.start_server()` 기반 TCP 서버
- inline 명령 + RESP 명령 처리
- in-memory key-value 저장소
- TTL (`EXPIRE`, `TTL`, `PERSIST`)
- Snapshot + AOF 기반 영속성
- `asyncio.Lock`으로 코루틴 간 DB 접근 보호

## 지원 명령

- `PING`
- `SET key value`
- `GET key`
- `DEL key`
- `EXPIRE key seconds`
- `TTL key`
- `PERSIST key`
- `EXISTS key`
- `FLUSH`
- `KEYS`

## 파일 역할

- `server.py`: asyncio TCP 서버
- `storage.py`: 메모리 저장소, TTL, `asyncio.Lock`
- `parser.py`: inline / RESP 파싱
- `persistence.py`: snapshot 저장/로드, AOF append/replay
- `client.py`: RESP 클라이언트

## 실행

```bash
cd /Users/gang-yeong-im/JUNGLE/Mini_Redis
source /Users/gang-yeong-im/JUNGLE/.venv/bin/activate
python -m pip install -r requirements.txt
python server.py
```

정상 실행 시:

```text
Mini Redis server listening on 127.0.0.1:6380
Connect from another terminal: nc 127.0.0.1 6380
```

## 확인 방법

### inline 확인

```bash
nc 127.0.0.1 6380
```

입력:

```text
PING
SET a 1
GET a
DEL a
GET a
```

### RESP 확인

```bash
python client.py
```

입력:

```text
PING
SET a 1
GET a
```

## Persistence

서버는 `data/` 아래 파일을 사용한다.

- snapshot: `data/snapshot.json`
- AOF: `data/appendonly.aof`

### Snapshot

- 300초(5분)마다 백그라운드 태스크가 실행된다.
- `asyncio.Lock`을 잡고 현재 메모리 상태를 복사한다.
- lock을 푼 뒤 임시 파일에 저장하고 `os.replace()`로 교체한다.

### AOF

- `SET`, `DEL`, `EXPIREAT`, `PERSIST`, `FLUSH` 같은 변경 명령만 기록한다.
- append 방식으로 파일 끝에 계속 추가한다.
- 각 명령은 순서대로 기록된다.

## 복구 순서

서버 시작 시 아래 순서로 복구한다.

1. snapshot 로드
2. snapshot 안에 기록된 AOF offset 확인
3. 그 offset 이후의 AOF만 replay
4. 복구 완료 후 서버 시작

즉 snapshot이 기준 상태가 되고, 그 이후 변경분만 AOF로 다시 반영한다.

## 동기화

- 공유 DB 접근: `asyncio.Lock`
- snapshot 저장: copy 후 파일 write
- 파일 I/O: `asyncio.to_thread()` 사용

그래서 코루틴 여러 개가 들어와도 DB 상태가 꼬이지 않도록 막는다.

## 테스트

```bash
cd /Users/gang-yeong-im/JUNGLE/Mini_Redis
source /Users/gang-yeong-im/JUNGLE/.venv/bin/activate
python -m pytest -q
```
