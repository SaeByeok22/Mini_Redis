# Mini Redis

## 1. 어느 정도 구현했는가

- asyncio 기반 TCP 서버
- inline 명령 + RESP 명령 처리
- 부가 명령 구현 (`EXISTS`, `FLUSH`, `KEYS`)
- `asyncio.Lock` 기반 동기화
- 5분 주기 Snapshot
- 변경 명령 AOF 기록
- 서버 재시작 시 `Snapshot -> AOF replay` 복구

즉, 단순히 `SET/GET`만 되는 서버가 아니라  
"동시 요청 + 만료 시간 + 영속성 + 복구"까지 포함한 mini Redis 형태로 구현.

## 2. 역할

- storage, socket-bridge, 시연 웹페이지 담당 : 고윤서
- server - parser, resp protocol 담당 : 황선호
- merge, 단위 및 기능 테스트 담당 : 이준희

## 3. 실제 동작 방식

1. 클라이언트가 `PING`, `SET a 1`, `GET a` 같은 명령을 보낸다.
2. 서버가 요청을 파싱한다.
3. Storage가 메모리에서 값을 읽거나 수정한다.
4. 수정 명령이면 AOF에 순서대로 기록한다.
5. 5분마다 현재 상태를 Snapshot 파일로 저장한다.
6. 서버가 재시작되면 Snapshot을 먼저 읽고, 그 뒤 AOF를 replay 해서 복구한다.

## 4. 지원 명령

- `PING` : 연결 확인
- `SET` : 데이터 저장
- `GET` : 데이터 조회
- `DEL` : 데이터 삭제
- `EXPIRE` : TTL 설정
- `TTL` : 남은 TTL 조회
- `PERSIST` : TTL 제거
- `EXISTS` : 데이터 존재 여부 확인
- `FLUSH` : 데이터 전체 삭제
- `KEYS` : 데이터 전체 key 조회

## 5. 기능 검증 결과

검증한 범위:

- parser 단위 테스트
- storage 단위 테스트
- server 단위 테스트
- RESP 클라이언트 테스트
- snapshot 저장 / load / AOF replay 복구 테스트

실행한 테스트 코드:

```bash
python -m pytest -q tests/test_parser.py
python -m pytest -q tests/test_storage.py
python -m pytest -q tests/test_server.py
python -m pytest -q tests/test_client.py
python -m pytest -q
```

테스트 파일 기준으로 보면:

- `tests/test_parser.py` : inline / RESP 명령 파싱, 인자 개수 검증, 잘못된 명령 처리
- `tests/test_storage.py` : `SET/GET/DEL`, TTL, `PERSIST`, `EXISTS`, `FLUSH`, `KEYS`, snapshot / AOF 복구
- `tests/test_server.py` : 서버 명령 처리 결과와 응답 포맷 검증
- `tests/test_client.py` : RESP 클라이언트 요청 / 응답 처리 검증

실제로 확인한 항목:

- `PING -> PONG`
- `SET -> GET -> DEL`
- TTL 만료 후 key 삭제
- RESP 요청 처리
- 서버 재시작 후 데이터 복구

## 6. 실제 사용 시나리오

### Mini Redis API로 직접 사용

서버를 실행합니다:

```bash
cd C:\krafton_jungle\mini_redis
python server.py
```

RESP 클라이언트 실행:

```bash
python client.py
```

입력:

```text
PING
SET user:1 kim
GET user:1
EXPIRE user:1 10
TTL user:1
```

이 시나리오는 "외부 클라이언트가 mini Redis API를 호출해서 세션이나 캐시 데이터를 저장하는 경우"에 해당한다.

직접 명령을 한 번에 보내서 확인할 수도 있다:

```bash
python client.py PING
python client.py SET user:1 kim
python client.py GET user:1
python client.py EXPIRE user:1 10
python client.py TTL user:1
```

Storage 코드 단위로 확인하고 싶다면 아래처럼 바로 호출해 볼 수 있다:

```python
import asyncio
from storage import Storage

async def main():
    storage = Storage()
    print(await storage.set("user:1", "kim"))
    print(await storage.get("user:1"))
    print(await storage.exists("user:1"))
    print(await storage.delete("user:1"))

asyncio.run(main())
```

## 7. 엣지 케이스 테스트

이번 구현에서 중요하게 본 엣지 케이스는 아래와 같다.

- 없는 key `GET` 시 `nil`
- 없는 key `DEL` 시 `0`
- 잘못된 명령 입력 시 `ERROR ...`
- TTL 지난 key 조회 시 자동 삭제
- `PERSIST`로 TTL 제거 가능
- `FLUSH` 후 전체 데이터 삭제
- Snapshot 파일이 없을 때 빈 DB로 시작
- AOF 파일이 없을 때도 안전하게 시작
- 일부 파일이 깨져 있어도 빈 상태로 fallback 가능

확인에 사용한 테스트 예시는 아래와 같다:

```python
import asyncio
from storage import Storage

async def edge_case_demo():
    storage = Storage()

    print(await storage.get("missing"))      # None
    print(await storage.delete("missing"))   # False
    print(await storage.exists("missing"))   # False

    await storage.set("session:1", "token")
    await storage.expire("session:1", 1)
    await asyncio.sleep(1.1)
    print(await storage.get("session:1"))    # None
    print(await storage.ttl("session:1"))    # -2

asyncio.run(edge_case_demo())
```

또는 pytest 기준으로는 아래 테스트로 검증했다:

```bash
python -m pytest -q tests/test_storage.py -k "ttl or persist or exists or flush or keys"
```

### No Redis

- 요청이 올 때마다 원본 DB를 직접 조회
- 같은 데이터라도 계속 DB까지 내려감
- 응답 속도가 느려지고 DB 부하가 커짐

### With Redis Cache

- 자주 쓰는 데이터를 메모리에 저장
- 캐시 hit면 DB를 거치지 않고 바로 응답
- 응답 속도가 빨라지고 DB 부하가 줄어듦

즉 핵심은:

- No Redis: 매번 원본 DB 조회
- Redis 사용: 자주 쓰는 값은 메모리에서 바로 반환

이 기능은, 캐시 계층이 어떤 원리로 동작하는지 직접 구현해 본 것에 의미가 있었다!

## 8. 복구 순서

서버 시작 및 재시작 시 복구

1. Snapshot 로드
2. Snapshot 시점 이후 AOF replay
3. 메모리 상태 복원
4. 서버 시작

## 9. 결론

- TCP 서버
- RESP 파싱
- 메모리 저장소
- TTL
- 동시성 제어
- Snapshot
- AOF
- 복구

비록 큰 규모는 아니지만,, Redis의 핵심 기능을 따라가며 구현해 보았다!

## 10. AI를 어떻게 사용했는지?

AI는 전체를 한 번에 맡기는 방식이 아니라,  
"파일 단위, 기능 단위"로 잘라서 독립적으로 사용했다.

사용 방식:

- parser / server / storage 구조 정리
- RESP 파싱 보완
- asyncio 리팩토링
- Snapshot / AOF 설계 초안 정리
- README 초안 작성

중요한 점은:

- 실제 실행과 테스트로 최종적으로는 .aof에 로그가 잘 뜨는지 확인하며 검증했다.
- 요구사항과 맞지 않는 부분은 다시 수정했다.
