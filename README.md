# 미니 Redis 서버: parser + server 정리

## 개요

이 브랜치는 2번 팀원 작업 기준으로 `parser.py`와 `server.py`를 구현한 상태다.

- `parser.py`: 클라이언트가 보낸 문자열 명령을 해석한다.
- `server.py`: TCP 연결을 받고, parser 결과를 storage 호출로 연결한 뒤 응답을 돌려준다.

저장 로직은 일부러 `server.py` 안에 넣지 않았다. 실제 데이터 저장은 `storage.py`의 `Storage` 클래스가 담당해야 한다.

## 현재 구현 파일

```text
mini-redis/
├── server.py
├── parser.py
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

즉, 1번 팀원의 `storage.py`가 머지되면 바로 연결할 수 있게 구성했다.

## 실행 방법

`server.py`는 기본적으로 `storage.py`에서 `Storage` 클래스를 가져오도록 되어 있다.

따라서 실제 서버 실행은 `storage.py`가 있어야 가능하다.

예시:

```bash
python3 server.py
```

기본 주소:

- host: `127.0.0.1`
- port: `6380`

## 설계 포인트

- parser와 server 역할을 분리했다.
- server 안에 저장 로직을 넣지 않았다.
- parser 예외를 server에서 `ERROR ...` 응답으로 바꿨다.
- 지금은 단순한 구조를 위해 순차 처리 서버로 구현했다.

## 현재 한계

- `storage.py`가 아직 이 브랜치에는 없으면 실제 실행은 불가하다.
- 멀티 클라이언트 처리는 아직 넣지 않았다.
- RESP 프로토콜은 아직 지원하지 않는다.

## 다음 단계

- `feature/storage` 브랜치와 머지
- `PING / SET / GET / DEL` 실서버 동작 확인
- 이후 여유가 있으면 `EXPIRE / TTL` 연결
