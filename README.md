# Mini Redis

## 1. 프로젝트 한 줄 소개

Python 3.11 표준 라이브러리만으로 만든 asyncio 기반 mini Redis 서버다.  
TCP 소켓으로 요청을 받고, 메모리에 데이터를 저장하고, Snapshot + AOF 방식으로 복구할 수 있다.

## 2. 어느 정도 구현했는가

이번 구현 범위는 단순 MVP를 넘어서 아래까지 포함한다.

- asyncio 기반 TCP 서버
- inline 명령 + RESP 명령 처리
- key-value 저장소
- TTL (`EXPIRE`, `TTL`, `PERSIST`)
- 부가 명령 (`EXISTS`, `FLUSH`, `KEYS`)
- `asyncio.Lock` 기반 동기화
- 5분 주기 Snapshot
- 변경 명령 AOF 기록
- 서버 재시작 시 `Snapshot -> AOF replay` 복구

즉, 단순히 `SET/GET`만 되는 서버가 아니라,  
"동시 요청 + 만료 시간 + 영속성 + 복구"까지 포함한 mini Redis 형태로 구현했다.

## 3. 역할

- [server.py](/Users/gang-yeong-im/JUNGLE/Mini_Redis/server.py)
  asyncio 서버 실행, 클라이언트 연결 처리, 명령 실행
- [parser.py](/Users/gang-yeong-im/JUNGLE/Mini_Redis/parser.py)
  inline / RESP 요청 파싱
- [storage.py](/Users/gang-yeong-im/JUNGLE/Mini_Redis/storage.py)
  메모리 저장소, TTL 처리, `asyncio.Lock` 기반 보호
- [persistence.py](/Users/gang-yeong-im/JUNGLE/Mini_Redis/persistence.py)
  Snapshot 저장, AOF append, 서버 시작 시 load
- [client.py](/Users/gang-yeong-im/JUNGLE/Mini_Redis/client.py)
  RESP 방식으로 서버를 호출하는 간단한 클라이언트

## 4. 실제 동작 방식

흐름은 아주 단순하다.

1. 클라이언트가 `PING`, `SET a 1`, `GET a` 같은 명령을 보낸다.
2. 서버가 요청을 파싱한다.
3. Storage가 메모리에서 값을 읽거나 수정한다.
4. 수정 명령이면 AOF에 순서대로 기록한다.
5. 5분마다 현재 상태를 Snapshot 파일로 저장한다.
6. 서버가 재시작되면 Snapshot을 먼저 읽고, 그 뒤 AOF를 replay 해서 복구한다.

## 5. 지원 명령

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

## 6. 기능 검증 결과

테스트 결과:

- `38 passed in 0.10s`

검증한 범위:

- parser 단위 테스트
- storage 단위 테스트
- server 단위 테스트
- RESP 클라이언트 테스트
- snapshot 저장 / load / AOF replay 복구 테스트

실제로 확인한 항목:

- `PING -> PONG`
- `SET -> GET -> DEL`
- TTL 만료 후 key 삭제
- RESP 요청 처리
- 서버 재시작 후 데이터 복구

## 7. 실제 사용 시나리오

### Mini Redis API로 직접 사용

서버 실행:

```bash
cd /Users/gang-yeong-im/JUNGLE/Mini_Redis
source /Users/gang-yeong-im/JUNGLE/.venv/bin/activate
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

### 서비스 API + Mini Redis

발표용으로 가장 쉬운 예시는 로그인 세션 캐시다.

1. 서비스 API가 DB에서 사용자 정보를 읽는다.
2. 자주 조회되는 데이터는 Mini Redis에 저장한다.
3. 다음 요청부터는 DB 대신 Mini Redis에서 빠르게 꺼낸다.
4. TTL이 끝나면 자동으로 사라지고, 필요하면 다시 DB에서 읽는다.

즉, Mini Redis는 원본 DB를 대신하는 것이 아니라,  
"앞단에서 속도를 높이는 캐시 계층"으로 설명하는 것이 가장 자연스럽다.

## 8. 엣지 케이스 테스트

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

## 9. 성능 비교: Redis vs No Redis

이번 프로젝트에서 실제 DB 연동 benchmark까지 하지는 않았다.  
대신 캐시를 왜 쓰는지는 아래 시나리오로 설명할 수 있다.

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

이 프로젝트는 그 캐시 계층이 어떤 원리로 동작하는지 직접 구현해 본 것에 의미가 있다.

## 10. 테스트 케이스 요약

대표 테스트 케이스:

- `PING` 파싱 및 응답
- `SET a 1` 후 `GET a == 1`
- `DEL a` 후 `GET a == nil`
- `EXPIRE a 3` 후 만료 시 `TTL a == -2`
- `PERSIST a` 후 TTL 제거
- `EXISTS a` 동작 확인
- `FLUSH` 후 key 전체 삭제
- RESP 요청 파싱
- snapshot 저장 후 재시작 복구
- AOF replay 반영 확인

## 11. 복구 순서

서버 시작 시 복구 순서는 고정이다.

1. Snapshot 로드
2. Snapshot 시점 이후 AOF replay
3. 메모리 상태 복원
4. 서버 시작

이 순서를 README에 명시한 이유는,  
"왜 데이터가 다시 살아나는지"를 발표 때 짧게 설명하기 위해서다.

## 12. 결론

이 프로젝트는 "Redis처럼 보이는 서버"를 흉내 내는 수준이 아니라,  
실제로 아래 핵심 개념을 직접 구현하는 데 목적이 있었다.

- TCP 서버
- RESP 파싱
- 메모리 저장소
- TTL
- 동시성 제어
- Snapshot
- AOF
- 복구

즉, 작은 규모지만 Redis의 핵심 아이디어를 따라가 본 구현이다.

## 13. AI를 어떻게 사용했는가

AI는 전체를 한 번에 맡기는 방식이 아니라,  
"파일 단위, 기능 단위"로 잘라서 보조 도구처럼 사용했다.

사용 방식:

- parser / server / storage 구조 정리
- RESP 파싱 보완
- asyncio 리팩토링
- Snapshot / AOF 설계 초안 정리
- 테스트 코드 작성 보조
- README 초안 작성

중요한 점은:

- 생성된 코드를 그대로 쓰지 않고 직접 읽고 수정했다.
- 실제 실행과 테스트로 검증했다.
- 요구사항과 맞지 않는 부분은 다시 수정했다.

즉, AI는 구현 가속 도구로 사용했고,  
최종 설계 판단과 검증은 사람이 직접 진행했다.
