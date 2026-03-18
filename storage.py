import time
from collections.abc import Callable
from typing import Any


class Storage:
    def __init__(self, time_func: Callable[[], float] | None = None) -> None:
        # Keep value data separate from expire metadata.
        self._data: dict[str, Any] = {}
        self._expires_at: dict[str, float] = {}
        self._time_func = time_func or time.monotonic

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._expires_at.pop(key, None)

    def get(self, key: str) -> Any:
        # Return None when the key does not exist.
        self._purge_if_expired(key)
        return self._data.get(key)

    def delete(self, key: str) -> bool:
        self._purge_if_expired(key)

        if key not in self._data:
            return False

        del self._data[key]
        self._expires_at.pop(key, None)
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

    def _now(self) -> float:
        return self._time_func()

    def _purge_if_expired(self, key: str) -> None:
        expires_at = self._expires_at.get(key)
        if expires_at is None:
            return

        if expires_at > self._now():
            return

        self._data.pop(key, None)
        self._expires_at.pop(key, None)
