from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class LoadedState:
    data: dict[str, str]
    expires_at: dict[str, float]
    aof_entries: list[tuple[str, list[str]]]


def store(
    snapshot_path: str,
    data: dict[str, str],
    expires_at: dict[str, float],
    aof_offset: int,
) -> None:
    path = Path(snapshot_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")

    payload = {
        "data": data,
        "expires_at": expires_at,
        "aof_offset": aof_offset,
    }

    with temp_path.open("w", encoding="utf-8") as snapshot_file:
        json.dump(payload, snapshot_file)

    os.replace(temp_path, path)


def load(snapshot_path: str, aof_path: str) -> LoadedState:
    data: dict[str, str] = {}
    expires_at: dict[str, float] = {}
    aof_offset = 0

    try:
        with open(snapshot_path, "r", encoding="utf-8") as snapshot_file:
            payload = json.load(snapshot_file)
            data = {str(key): str(value) for key, value in payload.get("data", {}).items()}
            expires_at = {
                str(key): float(value)
                for key, value in payload.get("expires_at", {}).items()
            }
            aof_offset = int(payload.get("aof_offset", 0))
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        data = {}
        expires_at = {}
        aof_offset = 0

    aof_entries = _load_aof_entries(aof_path, aof_offset)
    return LoadedState(data=data, expires_at=expires_at, aof_entries=aof_entries)


def _load_aof_entries(aof_path: str, offset: int) -> list[tuple[str, list[str]]]:
    entries: list[tuple[str, list[str]]] = []

    try:
        with open(aof_path, "rb") as aof_file:
            aof_file.seek(offset)
            for raw_line in aof_file:
                try:
                    payload = json.loads(raw_line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue

                command = str(payload.get("command", "")).upper()
                args = [str(arg) for arg in payload.get("args", [])]
                if command:
                    entries.append((command, args))
    except FileNotFoundError:
        return entries
    except OSError:
        return entries

    return entries


def _append_command(aof_path: str, command: str, args: list[str]) -> int:
    path = Path(aof_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps({"command": command, "args": args}).encode("utf-8") + b"\n"
    with path.open("ab") as aof_file:
        aof_file.write(payload)
        aof_file.flush()

    return len(payload)


class PersistenceManager:
    def __init__(self, snapshot_path: str, aof_path: str) -> None:
        self.snapshot_path = snapshot_path
        self.aof_path = aof_path
        self._aof_offset = 0

    @property
    def current_aof_offset(self) -> int:
        return self._aof_offset

    async def store(
        self,
        data: dict[str, str],
        expires_at: dict[str, float],
        aof_offset: int,
    ) -> None:
        await asyncio.to_thread(store, self.snapshot_path, data, expires_at, aof_offset)

    async def load(self) -> LoadedState:
        loaded_state = await asyncio.to_thread(load, self.snapshot_path, self.aof_path)
        self._aof_offset = await asyncio.to_thread(self._read_aof_size)
        return loaded_state

    async def append_command(self, command: str, args: list[str]) -> None:
        written_bytes = await asyncio.to_thread(_append_command, self.aof_path, command, args)
        self._aof_offset += written_bytes

    def _read_aof_size(self) -> int:
        try:
            return os.path.getsize(self.aof_path)
        except OSError:
            return 0
