import asyncio

from persistence import PersistenceManager
from storage import Storage


def test_set_returns_ok_and_saves_value():
    async def scenario() -> None:
        storage = Storage()
        result = await storage.set("a", "1")

        assert result == "OK"
        assert await storage.get("a") == "1"

    asyncio.run(scenario())


def test_delete_removes_existing_key():
    async def scenario() -> None:
        storage = Storage()
        await storage.set("a", "1")

        deleted = await storage.delete("a")

        assert deleted is True
        assert await storage.get("a") is None

    asyncio.run(scenario())


def test_expire_removes_key_after_time_passes():
    current_time = 100.0

    def fake_time() -> float:
        return current_time

    async def scenario() -> None:
        nonlocal current_time
        storage = Storage(time_func=fake_time)
        await storage.set("a", "1")

        assert await storage.expire("a", 3) is True
        assert await storage.ttl("a") == 3

        current_time = 104.0

        assert await storage.get("a") is None
        assert await storage.ttl("a") == -2

    asyncio.run(scenario())


def test_persist_removes_existing_ttl():
    async def scenario() -> None:
        storage = Storage()
        await storage.set("a", "1")
        await storage.expire("a", 5)

        persisted = await storage.persist("a")

        assert persisted is True
        assert await storage.ttl("a") == -1

    asyncio.run(scenario())


def test_flush_clears_data_and_expire_metadata():
    async def scenario() -> None:
        storage = Storage()
        await storage.set("a", "1")
        await storage.set("b", "2")
        await storage.expire("a", 5)

        await storage.flush()

        assert await storage.get("a") is None
        assert await storage.get("b") is None
        assert await storage.ttl("a") == -2

    asyncio.run(scenario())


def test_keys_returns_only_live_keys():
    current_time = 100.0

    def fake_time() -> float:
        return current_time

    async def scenario() -> None:
        nonlocal current_time
        storage = Storage(time_func=fake_time)
        await storage.set("a", "1")
        await storage.set("b", "2")
        await storage.expire("a", 1)

        current_time = 102.0

        assert await storage.keys() == ["b"]

    asyncio.run(scenario())


def test_store_and_load_restore_snapshot_and_aof(tmp_path):
    current_time = 100.0

    def fake_time() -> float:
        return current_time

    async def scenario() -> None:
        nonlocal current_time
        persistence = PersistenceManager(
            snapshot_path=str(tmp_path / "snapshot.json"),
            aof_path=str(tmp_path / "appendonly.aof"),
        )
        storage = Storage(persistence=persistence, time_func=fake_time)

        await storage.set("a", "1")
        await storage.expire("a", 10)
        await storage.store()
        await storage.set("b", "2")
        await storage.delete("a")

        restored = Storage(
            persistence=PersistenceManager(
                snapshot_path=str(tmp_path / "snapshot.json"),
                aof_path=str(tmp_path / "appendonly.aof"),
            ),
            time_func=fake_time,
        )
        await restored.load()

        assert await restored.get("a") is None
        assert await restored.get("b") == "2"

        current_time = 200.0
        assert await restored.ttl("b") == -1

    asyncio.run(scenario())
