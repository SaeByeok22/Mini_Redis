import asyncio
import time
from collections.abc import Callable

from persistence import LoadedState, PersistenceManager


class Storage:
    def __init__(
        self,
        persistence: PersistenceManager | None = None,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        self._data: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}
        self._time_func = time_func or time.monotonic
        self._lock = asyncio.Lock()
        self._persistence = persistence

    async def load(self) -> None:
        if self._persistence is None:
            return

        loaded_state = await self._persistence.load()
        data, expires_at = self._restore_state(loaded_state)

        async with self._lock:
            self._data = data
            self._expires_at = expires_at
            self._cleanup_expired_locked()

    async def store(self) -> None:
        if self._persistence is None:
            return

        async with self._lock:
            self._cleanup_expired_locked()
            data_copy = self._data.copy()
            expires_copy = self._expires_at.copy()
            aof_offset = self._persistence.current_aof_offset

        await self._persistence.store(data_copy, expires_copy, aof_offset)

    async def set(self, key: str, value: str) -> str:
        async with self._lock:
            self._data[key] = value
            self._expires_at.pop(key, None)
            await self._append_aof_locked("SET", [key, value])
            return "OK"

    async def get(self, key: str) -> str | None:
        async with self._lock:
            self._purge_if_expired_locked(key)
            return self._data.get(key)

    async def exists(self, key: str) -> bool:
        async with self._lock:
            self._purge_if_expired_locked(key)
            return key in self._data

    async def delete(self, key: str) -> bool:
        async with self._lock:
            self._purge_if_expired_locked(key)
            if key not in self._data:
                return False

            self._delete_key_locked(key)
            await self._append_aof_locked("DEL", [key])
            return True

    async def expire(self, key: str, seconds: int | float) -> bool:
        async with self._lock:
            self._purge_if_expired_locked(key)
            if key not in self._data:
                return False

            expires_at = self._now() + seconds
            self._expires_at[key] = expires_at
            await self._append_aof_locked("EXPIREAT", [key, repr(expires_at)])
            return True

    async def ttl(self, key: str) -> int:
        async with self._lock:
            self._purge_if_expired_locked(key)
            if key not in self._data:
                return -2

            expires_at = self._expires_at.get(key)
            if expires_at is None:
                return -1

            remaining = expires_at - self._now()
            return max(0, int(remaining))

    async def persist(self, key: str) -> bool:
        async with self._lock:
            self._purge_if_expired_locked(key)
            if key not in self._data or key not in self._expires_at:
                return False

            del self._expires_at[key]
            await self._append_aof_locked("PERSIST", [key])
            return True

    async def flush(self) -> None:
        async with self._lock:
            self._data.clear()
            self._expires_at.clear()
            await self._append_aof_locked("FLUSH", [])

    async def cleanup_expired(self) -> int:
        async with self._lock:
            return self._cleanup_expired_locked()

    async def keys(self) -> list[str]:
        async with self._lock:
            self._cleanup_expired_locked()
            return list(self._data.keys())

    def _restore_state(self, loaded_state: LoadedState) -> tuple[dict[str, str], dict[str, float]]:
        data = loaded_state.data.copy()
        expires_at = loaded_state.expires_at.copy()

        for command, args in loaded_state.aof_entries:
            self._apply_replayed_command(data, expires_at, command, args)

        self._cleanup_expired_state(data, expires_at)
        return data, expires_at

    async def _append_aof_locked(self, command: str, args: list[str]) -> None:
        if self._persistence is None:
            return

        await self._persistence.append_command(command, args)

    def _apply_replayed_command(
        self,
        data: dict[str, str],
        expires_at: dict[str, float],
        command: str,
        args: list[str],
    ) -> None:
        if command == "SET":
            key, value = args
            data[key] = value
            expires_at.pop(key, None)
            return

        if command == "DEL":
            key = args[0]
            data.pop(key, None)
            expires_at.pop(key, None)
            return

        if command == "EXPIREAT":
            key, expires_text = args
            if key in data:
                expires_at[key] = float(expires_text)
            return

        if command == "PERSIST":
            expires_at.pop(args[0], None)
            return

        if command == "FLUSH":
            data.clear()
            expires_at.clear()

    def _now(self) -> float:
        return self._time_func()

    def _cleanup_expired_locked(self) -> int:
        expired_keys = [key for key in self._expires_at if self._is_expired_state(key, self._expires_at)]
        for key in expired_keys:
            self._delete_key_locked(key)
        return len(expired_keys)

    def _cleanup_expired_state(
        self,
        data: dict[str, str],
        expires_at: dict[str, float],
    ) -> None:
        expired_keys = [key for key in expires_at if self._is_expired_state(key, expires_at)]
        for key in expired_keys:
            data.pop(key, None)
            expires_at.pop(key, None)

    def _is_expired_state(self, key: str, expires_at: dict[str, float]) -> bool:
        deadline = expires_at.get(key)
        if deadline is None:
            return False
        return deadline <= self._now()

    def _delete_key_locked(self, key: str) -> None:
        self._data.pop(key, None)
        self._expires_at.pop(key, None)

    def _purge_if_expired_locked(self, key: str) -> None:
        if not self._is_expired_state(key, self._expires_at):
            return

        self._delete_key_locked(key)
