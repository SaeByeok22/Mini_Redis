# agent.md

## 1. 프로젝트 목표
이 저장소는 **파이썬으로 만든 미니 Redis 스타일 key-value 서버**를 구현하는 프로젝트입니다.
목표는 Redis 전체를 복제하는 것이 아니라, 아래 내용을 이해하고 직접 구현하는 것입니다.
- TCP 기반 클라이언트-서버 통신
- 명령어 파싱
- 메모리 기반 저장소
- 기본 테스트와 문서화

## 2. 오늘 구현 범위
### 필수 MVP 명령어
- `PING`
- `SET key value`
- `GET key`
- `DEL key`

### 시간이 남으면 추가
- `EXPIRE key seconds`
- `TTL key`

### 지금은 하지 않는 것
- Flask / FastAPI
- 웹 UI
- 디스크 영속성
- replication / clustering / scale-out
- list / set / hash / pub-sub
- 과도한 성능 최적화

## 3. 아키텍처 규칙
파일별 책임을 섞지 말 것.

### `storage.py`
데이터 저장 로직만 담당.
- 내부 `dict` 기반 저장
- `set/get/delete`
- 가능하면 `expire/ttl`
- socket 코드 넣지 말 것
- parser 코드 넣지 말 것

### `parser.py`
입력 명령 해석만 담당.
- raw text 또는 RESP 입력을 `(command, args)` 형태로 변환
- 인자 개수 검증
- 저장 로직 넣지 말 것

### `server.py`
TCP 통신과 요청/응답 처리만 담당.
- TCP 연결 수락
- 명령 수신
- parser 호출
- storage 호출
- 응답 전송
- 저장소 로직 재구현하지 말 것

### `tests/`
검증 담당.
- `test_storage.py`
- `test_parser.py`
- `test_server.py`

## 4. 인터페이스 규약
테스트와 README를 함께 수정하지 않는 한, 아래 규약을 임의로 바꾸지 말 것.

### Storage 규약
- `set(key, value) -> "OK"`
- `get(key) -> value | None`
- `delete(key) -> bool`
- `expire(key, seconds) -> bool` (선택)
- `ttl(key) -> int` (선택)
  - `-2`: key가 존재하지 않음
  - `-1`: 만료시간이 설정되지 않음
  - `0 이상`: 남은 초

### Parser 규약
- `parse_command("PING") -> ("PING", [])`
- `parse_command("SET a 1") -> ("SET", ["a", "1"])`
- 잘못된 입력은 명확한 예외를 발생시키거나, 문서화된 에러 형태를 반환할 것

### Server 응답 규약
- `PING` -> `PONG`
- `SET a 1` -> `OK`
- `GET a` -> `1`
- 없는 key -> `nil`
- `DEL a` 성공 -> `1`
- `DEL a` 실패 -> `0`
- 잘못된 명령 -> `ERROR ...`

## 5. 코딩 에이전트 작업 규칙
이 저장소를 수정할 때 아래 규칙을 따른다.
1. 가장 작은 동작 가능한 수정부터 할 것
2. 관련 없는 파일은 건드리지 말 것
3. 파일별 책임 분리를 유지할 것
4. 코드 단순성과 가독성을 우선할 것
5. 가능하면 파이썬 표준 라이브러리만 사용할 것
6. 동작이 바뀌면 테스트도 같이 추가 또는 수정할 것
7. 사용자 입장에서 바뀌는 내용이 있으면 README도 갱신할 것
8. 무엇을 바꿨는지, 어떻게 실행하는지 설명할 것

## 6. 권장 개발 순서
특별한 지시가 없으면 항상 아래 순서를 따른다.
1. `storage.py`
2. `parser.py`
3. `server.py`
4. `tests/`
5. `README.md` 정리

## 7. 코딩 스타일
- 함수는 작게 유지할 것
- 과한 추상화는 피할 것
- 초보자도 읽을 수 있게 작성할 것
- 꼭 필요한 곳에만 짧은 주석을 달 것
- 네트워킹, 파싱, 저장 로직을 한 곳에 섞지 말 것
- 숨겨진 부작용보다 명시적인 반환값을 선호할 것

## 8. 테스트 기준
완료로 보기 전에 최소한 아래는 검증해야 한다.
- `PING` 가 `PONG` 을 반환하는지
- `SET` 후 `GET` 이 저장된 값을 반환하는지
- `DEL` 이 key를 삭제하는지
- 없는 key가 계층 규약에 맞게 `nil` 또는 `None` 으로 처리되는지
- parser가 잘못된 입력을 거부하는지
- TTL 구현 시 만료 동작이 테스트되는지

## 9. 완료 조건
아래를 모두 만족해야 작업 완료로 본다.
- 코드가 실행됨
- 관련 테스트가 통과함
- 동작이 위 규약과 일치함
- README가 최신 상태임
- 관련 없는 부분이 깨지지 않음

## 10. 수동 테스트 예시
아래 흐름이 정상 동작해야 한다.

```text
PING -> PONG
SET a 1 -> OK
GET a -> 1
DEL a -> 1
GET a -> nil
```

## 11. 추후 확장 메모
RESP 프로토콜 지원은 나중에 추가할 수 있다.
RESP를 추가할 경우:
- parser는 bulk string 배열 형태의 RESP 요청을 파싱할 것
- server는 응답을 RESP 형식으로 직렬화할 것
- storage 계층은 그대로 유지할 것

## 12. 에이전트 작업 결과 보고 형식
작업 후 아래 형식으로 요약할 것.
- 변경한 파일
- 구현한 내용
- 실행 방법
- 테스트 방법
- 현재 한계점
