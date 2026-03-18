from server import MiniRedisServer
from storage import Storage


def test_ping_returns_pong():
    server = MiniRedisServer(storage=Storage())

    assert server.handle_request("PING") == "PONG"


def test_set_get_and_del_work_together():
    server = MiniRedisServer(storage=Storage())

    assert server.handle_request("SET a 1") == "OK"
    assert server.handle_request("GET a") == "1"
    assert server.handle_request("DEL a") == "1"
    assert server.handle_request("GET a") == "nil"


def test_missing_key_returns_nil():
    server = MiniRedisServer(storage=Storage())

    assert server.handle_request("GET missing") == "nil"


def test_invalid_command_returns_error_message():
    server = MiniRedisServer(storage=Storage())

    response = server.handle_request("BADCOMMAND")

    assert response.startswith("ERROR ")


def test_expire_and_ttl_work_with_storage():
    current_time = 100.0

    def fake_time() -> float:
        return current_time

    server = MiniRedisServer(storage=Storage(time_func=fake_time))

    assert server.handle_request("SET a 1") == "OK"
    assert server.handle_request("EXPIRE a 3") == "1"
    assert server.handle_request("TTL a") == "3"

    current_time = 104.0

    assert server.handle_request("GET a") == "nil"
    assert server.handle_request("TTL a") == "-2"


def test_resp_ping_serializes_as_simple_string():
    server = MiniRedisServer(storage=Storage())

    payload = server._serialize_response("resp", "simple", "PONG")

    assert payload == b"+PONG\r\n"


def test_resp_get_missing_key_serializes_as_null_bulk_string():
    server = MiniRedisServer(storage=Storage())

    payload = server._serialize_response("resp", "bulk", None)

    assert payload == b"$-1\r\n"


def test_resp_del_serializes_as_integer():
    server = MiniRedisServer(storage=Storage())

    response_type, response_value = server.execute_command("DEL", ["missing"])

    assert server._serialize_response("resp", response_type, response_value) == b":0\r\n"


def test_resp_ttl_serializes_as_integer():
    server = MiniRedisServer(storage=Storage())

    response_type, response_value = server.execute_command("TTL", ["missing"])

    assert server._serialize_response("resp", response_type, response_value) == b":-2\r\n"
