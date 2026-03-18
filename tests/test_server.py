import asyncio

from server import MiniRedisServer
from storage import Storage


def test_ping_returns_pong():
    async def scenario() -> None:
        server = MiniRedisServer(storage=Storage())
        assert await server.handle_request("PING") == "PONG"

    asyncio.run(scenario())


def test_set_get_and_del_work_together():
    async def scenario() -> None:
        server = MiniRedisServer(storage=Storage())

        assert await server.handle_request("SET a 1") == "OK"
        assert await server.handle_request("GET a") == "1"
        assert await server.handle_request("DEL a") == "1"
        assert await server.handle_request("GET a") == "nil"

    asyncio.run(scenario())


def test_invalid_command_returns_error_message():
    async def scenario() -> None:
        server = MiniRedisServer(storage=Storage())
        response = await server.handle_request("BADCOMMAND")
        assert response.startswith("ERROR ")

    asyncio.run(scenario())


def test_expire_and_ttl_work_with_storage():
    current_time = 100.0

    def fake_time() -> float:
        return current_time

    async def scenario() -> None:
        nonlocal current_time
        server = MiniRedisServer(storage=Storage(time_func=fake_time))

        assert await server.handle_request("SET a 1") == "OK"
        assert await server.handle_request("EXPIRE a 3") == "1"
        assert await server.handle_request("TTL a") == "3"

        current_time = 104.0

        assert await server.handle_request("GET a") == "nil"
        assert await server.handle_request("TTL a") == "-2"

    asyncio.run(scenario())


def test_persist_exists_flush_and_keys_work_with_storage():
    async def scenario() -> None:
        server = MiniRedisServer(storage=Storage())

        assert await server.handle_request("SET a 1") == "OK"
        assert await server.handle_request("SET b 2") == "OK"
        assert await server.handle_request("EXISTS a") == "1"
        assert await server.handle_request("PERSIST a") == "0"
        assert await server.handle_request("KEYS") == "a b"
        assert await server.handle_request("FLUSH") == "OK"
        assert await server.handle_request("KEYS") == ""
        assert await server.handle_request("EXISTS a") == "0"

    asyncio.run(scenario())


def test_snapshot_loop_calls_store():
    class FakeStorage:
        def __init__(self) -> None:
            self.calls = 0

        async def load(self) -> None:
            return None

        async def store(self) -> None:
            self.calls += 1

    async def scenario() -> None:
        storage = FakeStorage()
        server = MiniRedisServer(storage=storage, snapshot_interval=0)
        task = asyncio.create_task(server._snapshot_loop())
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert storage.calls >= 1

    asyncio.run(scenario())


def test_resp_serialization_formats():
    server = MiniRedisServer(storage=Storage())

    assert server._serialize_response("resp", "simple", "PONG") == b"+PONG\r\n"
    assert server._serialize_response("resp", "bulk", None) == b"$-1\r\n"
    assert server._serialize_response("resp", "integer", -2) == b":-2\r\n"
