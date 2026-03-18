"""Async TCP server for the mini Redis MVP."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

from parser import ParseError, ProtocolType, parse_command, read_request_async
from persistence import PersistenceManager


class StorageProtocol(Protocol):
    async def load(self) -> None:
        ...

    async def store(self) -> None:
        ...

    async def set(self, key: str, value: str) -> str:
        ...

    async def get(self, key: str) -> str | None:
        ...

    async def delete(self, key: str) -> bool:
        ...

    async def expire(self, key: str, seconds: int | float) -> bool:
        ...

    async def ttl(self, key: str) -> int:
        ...

    async def persist(self, key: str) -> bool:
        ...

    async def exists(self, key: str) -> bool:
        ...

    async def flush(self) -> None:
        ...

    async def keys(self) -> list[str]:
        ...


class MiniRedisServer:
    """Async line-based TCP server that dispatches commands to storage."""

    def __init__(
        self,
        storage: StorageProtocol,
        host: str = "127.0.0.1",
        port: int = 6380,
        snapshot_interval: int = 300,
    ) -> None:
        self.storage = storage
        self.host = host
        self.port = port
        self.snapshot_interval = snapshot_interval
        self._server: asyncio.AbstractServer | None = None
        self._snapshot_task: asyncio.Task[None] | None = None

    async def initialize(self) -> None:
        await self.storage.load()

    async def serve_forever(self) -> None:
        await self.initialize()
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)

        socket_names = self._server.sockets or []
        if socket_names:
            bound_host, bound_port = socket_names[0].getsockname()[:2]
            self.host = str(bound_host)
            self.port = int(bound_port)

        print(f"Mini Redis server listening on {self.host}:{self.port}")
        print(f"Connect from another terminal: nc {self.host} {self.port}")

        self._snapshot_task = asyncio.create_task(self._snapshot_loop())

        try:
            async with self._server:
                await self._server.serve_forever()
        finally:
            if self._snapshot_task is not None:
                self._snapshot_task.cancel()
                try:
                    await self._snapshot_task
                except asyncio.CancelledError:
                    pass

    async def _snapshot_loop(self) -> None:
        while True:
            await asyncio.sleep(self.snapshot_interval)
            await self.storage.store()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        protocol: ProtocolType = "inline"

        try:
            while True:
                try:
                    parsed_request = await read_request_async(reader)
                except ParseError as exc:
                    writer.write(self._serialize_error(str(exc), protocol))
                    await writer.drain()
                    continue

                if parsed_request is None:
                    break

                protocol, command, args = parsed_request
                response_type, response_value = await self.execute_command(command, args)
                writer.write(self._serialize_response(protocol, response_type, response_value))
                await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    async def handle_request(self, request: str) -> str:
        """Execute one inline request without going through TCP."""
        try:
            command, args = parse_command(request)
        except ParseError as exc:
            return f"ERROR {exc}"

        response_type, response_value = await self.execute_command(command, args)
        return self._format_inline_response(response_type, response_value)

    async def execute_command(self, command: str, args: list[str]) -> tuple[str, str | int | None]:
        if command == "PING":
            return "simple", "PONG"

        if command == "SET":
            key, value = args
            return "simple", await self.storage.set(key, value)

        if command == "GET":
            return "bulk", await self.storage.get(args[0])

        if command == "DEL":
            deleted = await self.storage.delete(args[0])
            return "integer", 1 if deleted else 0

        if command == "EXPIRE":
            return await self._handle_expire(args)

        if command == "TTL":
            return "integer", await self.storage.ttl(args[0])

        if command == "PERSIST":
            persisted = await self.storage.persist(args[0])
            return "integer", 1 if persisted else 0

        if command == "EXISTS":
            exists = await self.storage.exists(args[0])
            return "integer", 1 if exists else 0

        if command == "FLUSH":
            await self.storage.flush()
            return "simple", "OK"

        if command == "KEYS":
            return "bulk", " ".join(await self.storage.keys())

        return "error", f"unsupported command: {command}"

    async def _handle_expire(self, args: list[str]) -> tuple[str, str | int]:
        key, seconds_text = args
        try:
            seconds = int(seconds_text)
        except ValueError:
            return "error", "EXPIRE seconds must be an integer"

        if seconds < 0:
            return "error", "EXPIRE seconds must be non-negative"

        expired = await self.storage.expire(key, seconds)
        return "integer", 1 if expired else 0

    def _format_inline_response(self, response_type: str, response_value: str | int | None) -> str:
        if response_type == "simple":
            return str(response_value)

        if response_type == "bulk":
            return str(response_value) if response_value is not None else "nil"

        if response_type == "integer":
            return str(response_value)

        return f"ERROR {response_value}"

    def _serialize_response(
        self,
        protocol: ProtocolType,
        response_type: str,
        response_value: str | int | None,
    ) -> bytes:
        if protocol == "inline":
            return f"{self._format_inline_response(response_type, response_value)}\n".encode(
                "utf-8"
            )

        if response_type == "simple":
            return f"+{response_value}\r\n".encode("utf-8")

        if response_type == "bulk":
            if response_value is None:
                return b"$-1\r\n"

            bulk_value = str(response_value)
            return f"${len(bulk_value.encode('utf-8'))}\r\n{bulk_value}\r\n".encode("utf-8")

        if response_type == "integer":
            return f":{response_value}\r\n".encode("utf-8")

        return self._serialize_error(str(response_value), protocol)

    def _serialize_error(self, message: str, protocol: ProtocolType) -> bytes:
        if protocol == "resp":
            return f"-ERROR {message}\r\n".encode("utf-8")

        return f"ERROR {message}\n".encode("utf-8")


def create_default_server(host: str = "127.0.0.1", port: int = 6380) -> MiniRedisServer:
    from storage import Storage

    data_dir = Path(__file__).resolve().parent / "data"
    persistence = PersistenceManager(
        snapshot_path=str(data_dir / "snapshot.json"),
        aof_path=str(data_dir / "appendonly.aof"),
    )
    storage = Storage(persistence=persistence)
    return MiniRedisServer(storage=storage, host=host, port=port)


async def _main() -> None:
    server = create_default_server()
    try:
        await server.serve_forever()
    except OSError as exc:
        if exc.errno == 98:
            print(f"ERROR port {server.port} is already in use.")
            return
        if exc.errno == 48:
            print(f"ERROR port {server.port} is already in use.")
            return
        raise


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\nMini Redis server stopped.")


if __name__ == "__main__":
    main()
