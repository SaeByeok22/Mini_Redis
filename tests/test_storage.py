from storage import Storage


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
