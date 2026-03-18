import time
from collections.abc import Callable


class Storage:
    def __init__(self, time_func: Callable[[], float] | None = None) -> None:
        # Keep value data separate from expire metadata.
        self._data: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}
        self._time_func = time_func or time.monotonic

    def set(self, key: str, value: str) -> str:
        self._data[key] = value
        self._expires_at.pop(key, None)
        return "OK"

    def get(self, key: str) -> str | None:
        # Return None when the key does not exist.
        self._purge_if_expired(key)
        return self._data.get(key)

    def exists(self, key: str) -> bool:
        self._purge_if_expired(key)
        return key in self._data

    def delete(self, key: str) -> bool:
        self._purge_if_expired(key)

        if key not in self._data:
            return False

        self._delete_key(key)
        return True

    def expire(self, key: str, seconds: int | float) -> bool:
        self._purge_if_expired(key)

        if key not in self._data:
            return False

        self._expires_at[key] = self._now() + seconds
        return True

    def ttl(self, key: str) -> int:
        self._purge_if_expired(key)

        # -2: key does not exist, -1: key exists without expire, >=0: seconds left.
        if key not in self._data:
            return -2

        expires_at = self._expires_at.get(key)
        if expires_at is None:
            return -1

        remaining = expires_at - self._now()
        return max(0, int(remaining))

    def persist(self, key: str) -> bool:
        self._purge_if_expired(key)

        if key not in self._data:
            return False

        if key not in self._expires_at:
            return False

        del self._expires_at[key]
        return True

    def flush(self) -> None:
        self._data.clear()
        self._expires_at.clear()

    def cleanup_expired(self) -> int:
        expired_keys = [key for key in self._expires_at if self._is_expired(key)]
        for key in expired_keys:
            self._delete_key(key)

        return len(expired_keys)

    def keys(self) -> list[str]:
        self.cleanup_expired()
        return list(self._data.keys())

    def _now(self) -> float:
        return self._time_func()

    def _is_expired(self, key: str) -> bool:
        expires_at = self._expires_at.get(key)
        if expires_at is None:
            return False

        return expires_at <= self._now()

    def _delete_key(self, key: str) -> None:
        self._data.pop(key, None)
        self._expires_at.pop(key, None)

    def _purge_if_expired(self, key: str) -> None:
        if not self._is_expired(key):
            return

        self._delete_key(key)
