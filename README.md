# 미니 Redis 서버

## 개요

이 프로젝트는 Python으로 동작하는 mini Redis 스타일의 TCP key-value 서버다.

- `storage.py`: key-value 저장과 TTL 관리
- `parser.py`: 문자열 명령 파싱과 인자 검증
- `server.py`: TCP 연결 수락, parser 호출, storage 호출, 응답 전송

## 현재 구현 파일

```text
mini-redis/
├── storage.py
├── server.py
├── parser.py
├── tests/
└── README.md
```

## parser.py 설명

`parse_command(raw_command)`는 문자열 명령을 받아 `(command, args)` 형태로 반환한다.

처리 규칙:

- 앞뒤 공백 제거
- 공백 기준 분리
- 명령어를 대문자로 통일
- 지원하지 않는 명령어면 `ParseError`
- 인자 개수가 맞지 않으면 `ParseError`

예시:

```python
parse_command("PING")      # ("PING", [])
parse_command("SET a 1")   # ("SET", ["a", "1"])
parse_command(" del a ")   # ("DEL", ["a"])
```

지원 명령:

- `PING`
- `SET key value`
- `GET key`
- `DEL key`
- `EXPIRE key seconds`
- `TTL key`

MVP 필수 명령은 `PING`, `SET`, `GET`, `DEL`이다.

## server.py 설명

`MiniRedisServer`는 한 줄 단위 문자열 프로토콜로 동작하는 TCP 서버다.

흐름은 아래와 같다.

1. 클라이언트 연결 수락
2. 한 줄 읽기
3. `parse_command()` 호출
4. command에 따라 storage 메서드 호출
5. 결과를 문자열로 변환해서 응답

응답 규칙:

- `PING` -> `PONG`
- `SET` -> storage의 반환값 그대로 사용 (`OK` 예상)
- `GET` -> 값이 있으면 값, 없으면 `nil`
- `DEL` -> 성공 시 `1`, 실패 시 `0`
- 잘못된 명령 -> `ERROR ...`

선택 기능:

- `EXPIRE` -> 성공 시 `1`, 실패 시 `0`
- `TTL` -> 정수 문자열 반환

`EXPIRE`, `TTL`은 `storage.py`에 해당 메서드가 있을 때만 동작한다.

## storage.py와 연결 방식

서버는 아래 인터페이스를 기대한다.

```python
class Storage:
    def set(self, key, value) -> str: ...
    def get(self, key) -> str | None: ...
    def delete(self, key) -> bool: ...
```

선택 기능까지 붙이면 아래도 가능하다.

```python
    def expire(self, key, seconds) -> bool: ...
    def ttl(self, key) -> int: ...
```

## 실행 방법

`server.py`는 기본적으로 `storage.py`의 `Storage` 클래스를 사용한다.

예시:

```bash
cd /Users/gang-yeong-im/JUNGLE/Mini_Redis
python3 server.py
```

기본 주소:

- host: `127.0.0.1`
- port: `6380`

서버를 실행하면 아래처럼 대기 상태가 된다.

```text
Mini Redis server listening on 127.0.0.1:6380
Connect from another terminal: nc 127.0.0.1 6380
```

중요:

- `server.py`를 실행한 터미널에 `PING`를 직접 치는 방식은 동작하지 않는다.
- 그 터미널은 서버 대기용이다.
- 명령은 반드시 다른 터미널에서 보내야 한다.

예시:

```bash
nc 127.0.0.1 6380
```

그 다음 아래처럼 한 줄씩 입력해서 응답을 확인한다.

```text
PING
SET a 1
GET a
DEL a
GET a
```

예상 응답:

```text
PONG
OK
1
1
nil
```

TTL 예시:

```text
SET b 2
EXPIRE b 3
TTL b
GET b
```

## 서버 종료 방법

서버를 띄운 첫 번째 터미널에서 `Ctrl+C`를 누르면 서버가 종료된다.

정상 종료되면 아래 메시지가 보인다.

```text
Mini Redis server stopped.
```

주의:

- 두 번째 터미널의 `nc`에서 `Ctrl+C`를 누르면 클라이언트만 종료된다.
- 서버까지 끄려면 반드시 첫 번째 터미널에서 `Ctrl+C`를 눌러야 한다.
- `nc` 연결만 닫고 싶으면 두 번째 터미널에서 `Ctrl+C` 또는 `Ctrl+D`를 사용하면 된다.

즉:

- 첫 번째 터미널: `python3 server.py` 실행
- 두 번째 터미널: `nc 127.0.0.1 6380`로 명령 입력
- 클라이언트 종료: 두 번째 터미널에서 `Ctrl+C` 또는 `Ctrl+D`
- 서버 종료: 첫 번째 터미널에서 `Ctrl+C`

## 자주 나오는 상황

### `ERROR port 6380 is already in use.`

이미 다른 서버가 `127.0.0.1:6380`을 쓰고 있다는 뜻이다.

확인:

```bash
lsof -nP -iTCP:6380 -sTCP:LISTEN
```

기존 서버를 종료한 뒤 다시 `python3 server.py`를 실행하면 된다.

### `python3 storage.py`를 실행했는데 아무 일도 없음

정상이다. `storage.py`는 저장소 클래스만 정의한 파일이라서 직접 실행하는 용도가 아니다.

실행해야 하는 파일은 아래 둘 중 하나다.

- 서버 실행: `python3 server.py`
- 테스트 실행: `python3 -m pytest -q`

## 설계 포인트

- parser와 server 역할을 분리했다.
- server 안에 저장 로직을 넣지 않았다.
- parser 예외를 server에서 `ERROR ...` 응답으로 바꿨다.
- 지금은 단순한 구조를 위해 순차 처리 서버로 구현했다.

## 현재 한계

- 멀티 클라이언트 처리는 아직 넣지 않았다.
- RESP 프로토콜은 아직 지원하지 않는다.

## 다음 단계

- `feature/storage` 브랜치와 머지
- `PING / SET / GET / DEL` 실서버 동작 확인
- 이후 여유가 있으면 `EXPIRE / TTL` 연결
