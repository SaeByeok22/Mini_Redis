# Mini Redis

Python으로 만든 작은 Redis 스타일 TCP key-value 서버다.

## 지원 기능

- `PING`
- `SET key value`
- `GET key`
- `DEL key`
- `EXPIRE key seconds`
- `TTL key`

## 파일 역할

- `storage.py`: 데이터 저장, 삭제, TTL 처리
- `parser.py`: inline 명령과 RESP 명령 파싱
- `server.py`: TCP 서버 실행, 요청 처리, 응답 전송
- `client.py`: RESP 방식으로 서버에 명령 전송
- `tests/`: storage, parser, server 테스트

## 실행

가상환경이 있으면 먼저 활성화한다.

```bash
source /Users/gang-yeong-im/JUNGLE/.venv/bin/activate
```

프로젝트 의존성 설치:

```bash
cd /Users/gang-yeong-im/JUNGLE/Mini_Redis
python -m pip install -r requirements.txt
```

서버 실행:

```bash
cd /Users/gang-yeong-im/JUNGLE/Mini_Redis
python server.py
```

정상 실행 시:

```text
Mini Redis server listening on 127.0.0.1:6380
Connect from another terminal: nc 127.0.0.1 6380
```

중요:

- `server.py`를 실행한 터미널에 `PING`를 직접 치는 방식은 동작하지 않는다.
- 서버는 TCP 연결만 기다린다.
- 명령은 반드시 다른 터미널에서 보내야 한다.

## 확인 방법

### 1. 가장 쉬운 방법: `nc`

다른 터미널에서:

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

예상 응답:

```text
PONG
OK
1
1
nil
```

이 방식은 사람이 직접 확인하기 쉬운 inline 문자열 모드다.

### 2. RESP 방식 확인

`client.py`를 쓰면 `redis-cli` 없이도 RESP로 바로 확인할 수 있다.

```bash
python client.py PING
python client.py SET a 1
python client.py GET a
python client.py DEL a
python client.py TTL a
```

서버는 RESP 요청을 읽고 RESP 형식으로 응답한다.

포트를 바꾸고 싶으면:

```bash
python client.py --port 6380 PING
```

`nc`는 inline 모드 확인용이고, `client.py`는 RESP 확인용이다.

## 서버 종료

서버를 실행한 터미널에서 `Control + C`

정상 종료 시:

```text
Mini Redis server stopped.
```

주의:

- `Command + C`는 macOS 터미널 복사 단축키라서 서버 종료 신호가 아니다.
- 클라이언트 터미널에서 `Control + C`를 누르면 클라이언트만 닫힌다.

## 테스트

```bash
cd /Users/gang-yeong-im/JUNGLE/Mini_Redis
python -m pip install -r requirements.txt
python -m pytest -q
```

## Homebrew와 redis-cli

macOS에서 `redis-cli`를 쓰려면 보통 Homebrew가 필요하다.

공식 Homebrew 설치 명령:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

설치 후:

```bash
brew install redis
```

주의:

- Apple Silicon Mac에서는 기본 설치 위치가 `/opt/homebrew`다.
- 이 경로 설치에는 macOS 관리자 권한이 필요할 수 있다.
- 관리자 권한이 없으면 Homebrew 설치가 실패할 수 있다.

## 자주 나오는 상황

### `ERROR port 6380 is already in use.`

이미 다른 프로세스가 6380 포트를 쓰는 중이다.

확인:

```bash
lsof -nP -iTCP:6380 -sTCP:LISTEN
```

기존 프로세스를 종료한 뒤 다시 실행하면 된다.

### `python storage.py`를 실행했는데 아무 반응이 없음

정상이다.

- `storage.py`는 실행 파일이 아니라 클래스 정의 파일이다.
- 실제 실행 파일은 `server.py`다.
