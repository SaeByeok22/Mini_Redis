from storage import Storage


def test_set_returns_ok_and_saves_value():
    storage = Storage()

    result = storage.set("a", "1")

    assert result == "OK"
    assert storage.get("a") == "1"


def test_set_then_get_returns_saved_value():
    storage = Storage()

    storage.set("a", "1")

    assert storage.get("a") == "1"


def test_get_missing_key_returns_none():
    storage = Storage()

    assert storage.get("missing") is None


def test_delete_removes_existing_key():
    storage = Storage()
    storage.set("a", "1")

    deleted = storage.delete("a")

    assert deleted is True
    assert storage.get("a") is None


def test_delete_missing_key_returns_false():
    storage = Storage()

    assert storage.delete("missing") is False


def test_expire_removes_key_after_time_passes():
    current_time = 100.0

    def fake_time() -> float:
        return current_time

    storage = Storage(time_func=fake_time)
    storage.set("a", "1")

    assert storage.expire("a", 3) is True
    assert storage.ttl("a") == 3

    current_time = 104.0

    assert storage.get("a") is None
    assert storage.ttl("a") == -2


def test_exists_returns_true_only_for_live_keys():
    current_time = 100.0

    def fake_time() -> float:
        return current_time

    storage = Storage(time_func=fake_time)
    storage.set("a", "1")
    storage.expire("a", 2)

    assert storage.exists("a") is True

    current_time = 103.0

    assert storage.exists("a") is False


def test_persist_removes_existing_ttl():
    storage = Storage()
    storage.set("a", "1")
    storage.expire("a", 5)

    persisted = storage.persist("a")

    assert persisted is True
    assert storage.ttl("a") == -1


def test_flush_clears_data_and_expire_metadata():
    storage = Storage()
    storage.set("a", "1")
    storage.set("b", "2")
    storage.expire("a", 5)

    storage.flush()

    assert storage.get("a") is None
    assert storage.get("b") is None
    assert storage.ttl("a") == -2


def test_cleanup_expired_removes_only_expired_keys():
    current_time = 100.0

    def fake_time() -> float:
        return current_time

    storage = Storage(time_func=fake_time)
    storage.set("a", "1")
    storage.set("b", "2")
    storage.expire("a", 1)
    storage.expire("b", 5)

    current_time = 102.0

    removed_count = storage.cleanup_expired()

    assert removed_count == 1
    assert storage.get("a") is None
    assert storage.get("b") == "2"


def test_keys_returns_only_live_keys():
    current_time = 100.0

    def fake_time() -> float:
        return current_time

    storage = Storage(time_func=fake_time)
    storage.set("a", "1")
    storage.set("b", "2")
    storage.expire("a", 1)

    current_time = 102.0

    assert storage.keys() == ["b"]
