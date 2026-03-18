"""WebSocket bridge and live demo page for Mini Redis."""

from __future__ import annotations

import asyncio
import base64
import dbm.dumb
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from persistence import PersistenceManager
from server import MiniRedisServer
from storage import Storage


WEBSOCKET_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8765


class DemoSourceDB:
    """Small file-backed source DB used for cache comparisons."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        samples = {
            "user:1": "kim",
            "user:2": "lee",
            "product:1": "keyboard",
            "session:1": "token123",
        }
        with dbm.dumb.open(str(self.db_path), "c") as db:
            for key, value in samples.items():
                db[key] = value.encode("utf-8")

    async def fetch_value(self, key: str, delay_ms: int = 0) -> str | None:
        return await asyncio.to_thread(self._fetch_value_sync, key, delay_ms)

    def _fetch_value_sync(self, key: str, delay_ms: int) -> str | None:
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

        with dbm.dumb.open(str(self.db_path), "c") as db:
            value = db.get(key.encode("utf-8"))
        return None if value is None else value.decode("utf-8")


class MiniRedisWebBridge:
    """Serve a live HTML demo and bridge browser messages to Mini Redis."""

    def __init__(
        self,
        *,
        host: str = DEFAULT_HTTP_HOST,
        port: int = DEFAULT_HTTP_PORT,
        page_path: str | Path | None = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parent
        data_dir = base_dir / "data"

        persistence = PersistenceManager(
            snapshot_path=str(data_dir / "snapshot.json"),
            aof_path=str(data_dir / "appendonly.aof"),
        )
        self.redis = MiniRedisServer(
            storage=Storage(persistence=persistence),
            host="127.0.0.1",
            port=6380,
        )
        self.source_db = DemoSourceDB(data_dir / "demo_source_db")
        self.host = host
        self.port = port
        self.page_path = Path(page_path) if page_path is not None else base_dir / "mini_redis_live.html"
        self._http_server: asyncio.AbstractServer | None = None
        self._snapshot_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self.redis.initialize()
        await self.source_db.initialize()

        self._http_server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port,
        )
        sockets = self._http_server.sockets or []
        if sockets:
            bound_host, bound_port = sockets[0].getsockname()[:2]
            self.host = str(bound_host)
            self.port = int(bound_port)

        self._snapshot_task = asyncio.create_task(self._snapshot_loop())
        print(f"Mini Redis Web Demo listening on http://{self.host}:{self.port}")
        print(f"WebSocket endpoint: ws://{self.host}:{self.port}/ws")

    async def close(self) -> None:
        if self._http_server is not None:
            self._http_server.close()
            await self._http_server.wait_closed()
            self._http_server = None

        if self._snapshot_task is not None:
            self._snapshot_task.cancel()
            try:
                await self._snapshot_task
            except asyncio.CancelledError:
                pass
            self._snapshot_task = None

        try:
            await self.redis.storage.store()
        except OSError as exc:
            print(f"Snapshot skipped during shutdown: {exc}")

    async def serve_forever(self) -> None:
        await self.start()
        assert self._http_server is not None
        try:
            async with self._http_server:
                await self._http_server.serve_forever()
        finally:
            await self.close()

    async def _snapshot_loop(self) -> None:
        while True:
            await asyncio.sleep(self.redis.snapshot_interval)
            try:
                await self.redis.storage.store()
            except OSError as exc:
                print(f"Snapshot skipped: {exc}")

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            request_line = await reader.readline()
            if not request_line:
                return

            headers: dict[str, str] = {}
            while True:
                line = await reader.readline()
                if not line or line == b"\r\n":
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip("\r\n")
                if ":" in decoded:
                    key, value = decoded.split(":", 1)
                    headers[key.strip().lower()] = value.strip()

            method, path, _ = request_line.decode("utf-8", errors="replace").strip().split(" ", 2)
            if headers.get("upgrade", "").lower() == "websocket" and path == "/ws":
                await self._accept_websocket(reader, writer, headers)
                return

            if method != "GET":
                await self._send_http_response(writer, 405, b"Method Not Allowed", "text/plain")
                return

            if path == "/" or path == "/mini_redis_live.html":
                await self._serve_page(writer)
                return

            if path == "/health":
                await self._send_http_response(writer, 200, b"ok", "text/plain")
                return

            await self._send_http_response(writer, 404, b"Not Found", "text/plain")
        finally:
            if not writer.is_closing():
                writer.close()
                try:
                    await writer.wait_closed()
                except ConnectionError:
                    pass

    async def _serve_page(self, writer: asyncio.StreamWriter) -> None:
        html = self.page_path.read_bytes()
        await self._send_http_response(writer, 200, html, "text/html; charset=utf-8")

    async def _send_http_response(
        self,
        writer: asyncio.StreamWriter,
        status: int,
        body: bytes,
        content_type: str,
    ) -> None:
        reasons = {
            200: "OK",
            404: "Not Found",
            405: "Method Not Allowed",
            500: "Internal Server Error",
        }
        reason = reasons.get(status, "OK")
        head = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("utf-8")
        writer.write(head + body)
        await writer.drain()

    async def _accept_websocket(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        headers: dict[str, str],
    ) -> None:
        key = headers.get("sec-websocket-key")
        if not key:
            await self._send_http_response(writer, 400, b"Missing WebSocket key", "text/plain")
            return

        accept = base64.b64encode(
            hashlib.sha1((key + WEBSOCKET_MAGIC).encode("utf-8")).digest()
        ).decode("ascii")
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        ).encode("utf-8")
        writer.write(response)
        await writer.drain()

        try:
            while True:
                opcode, payload = await self._read_ws_frame(reader)
                if opcode == 0x8:
                    await self._send_ws_frame(writer, b"", opcode=0x8)
                    break
                if opcode == 0x9:
                    await self._send_ws_frame(writer, payload, opcode=0xA)
                    continue
                if opcode != 0x1:
                    continue

                reply = await self.handle_message(payload.decode("utf-8", errors="replace"))
                await self._send_ws_frame(writer, reply.encode("utf-8"), opcode=0x1)
        except (asyncio.IncompleteReadError, ConnectionError):
            pass

    async def _read_ws_frame(self, reader: asyncio.StreamReader) -> tuple[int, bytes]:
        header = await reader.readexactly(2)
        first_byte, second_byte = header
        opcode = first_byte & 0x0F
        masked = (second_byte & 0x80) != 0
        payload_length = second_byte & 0x7F

        if payload_length == 126:
            payload_length = int.from_bytes(await reader.readexactly(2), "big")
        elif payload_length == 127:
            payload_length = int.from_bytes(await reader.readexactly(8), "big")

        mask_key = await reader.readexactly(4) if masked else b""
        payload = await reader.readexactly(payload_length)
        if masked:
            payload = bytes(
                byte ^ mask_key[index % 4]
                for index, byte in enumerate(payload)
            )
        return opcode, payload

    async def _send_ws_frame(
        self,
        writer: asyncio.StreamWriter,
        payload: bytes,
        *,
        opcode: int,
    ) -> None:
        first_byte = 0x80 | opcode
        length = len(payload)
        if length < 126:
            header = bytes([first_byte, length])
        elif length < (1 << 16):
            header = bytes([first_byte, 126]) + length.to_bytes(2, "big")
        else:
            header = bytes([first_byte, 127]) + length.to_bytes(8, "big")

        writer.write(header + payload)
        await writer.drain()

    async def handle_message(self, text: str) -> str:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return json.dumps({"ok": False, "error": "invalid json"})

        action = str(payload.get("action", "command"))
        if action == "command":
            command = str(payload.get("command", "")).strip()
            if not command:
                return json.dumps({"ok": False, "error": "command is required"})

            response = await self.redis.handle_request(command)
            return json.dumps(
                {
                    "ok": not response.startswith("ERROR "),
                    "action": "command",
                    "command": command,
                    "response": response,
                }
            )

        if action == "benchmark":
            key = str(payload.get("key", "user:1")).strip() or "user:1"
            iterations = max(1, int(payload.get("iterations", 50)))
            db_delay_ms = max(0, int(payload.get("db_delay_ms", 20)))
            result = await self._run_benchmark(key, iterations, db_delay_ms)
            return json.dumps({"ok": True, "action": "benchmark", **result})

        if action == "samples":
            return json.dumps(
                {
                    "ok": True,
                    "action": "samples",
                    "keys": ["user:1", "user:2", "product:1", "session:1"],
                }
            )

        return json.dumps({"ok": False, "error": f"unsupported action: {action}"})

    async def _run_benchmark(
        self,
        key: str,
        iterations: int,
        db_delay_ms: int,
    ) -> dict[str, Any]:
        cache_key = f"cache:{key}"
        source_value = await self.source_db.fetch_value(key, 0)
        if source_value is None:
            return {
                "key": key,
                "iterations": iterations,
                "db_delay_ms": db_delay_ms,
                "error": "source key not found in demo source db",
            }

        await self.redis.handle_request(f"DEL {cache_key}")

        no_cache_start = time.perf_counter()
        for _ in range(iterations):
            await self.source_db.fetch_value(key, db_delay_ms)
        no_cache_total_ms = (time.perf_counter() - no_cache_start) * 1000

        cache_hits = 0
        cache_misses = 0
        with_cache_start = time.perf_counter()
        for _ in range(iterations):
            cached = await self.redis.handle_request(f"GET {cache_key}")
            if cached != "nil":
                cache_hits += 1
                continue

            cache_misses += 1
            value = await self.source_db.fetch_value(key, db_delay_ms)
            if value is None:
                continue
            await self.redis.handle_request(f"SET {cache_key} {value}")
        with_cache_total_ms = (time.perf_counter() - with_cache_start) * 1000

        no_cache_avg_ms = no_cache_total_ms / iterations
        with_cache_avg_ms = with_cache_total_ms / iterations
        speedup = no_cache_avg_ms / with_cache_avg_ms if with_cache_avg_ms else 0.0

        return {
            "key": key,
            "iterations": iterations,
            "db_delay_ms": db_delay_ms,
            "source_value": source_value,
            "no_cache_total_ms": round(no_cache_total_ms, 2),
            "no_cache_avg_ms": round(no_cache_avg_ms, 2),
            "with_cache_total_ms": round(with_cache_total_ms, 2),
            "with_cache_avg_ms": round(with_cache_avg_ms, 2),
            "speedup": round(speedup, 2),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": round((cache_hits / iterations) * 100, 2),
        }


async def _main() -> None:
    bridge = MiniRedisWebBridge()
    try:
        await bridge.serve_forever()
    finally:
        await bridge.close()


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\nMini Redis Web Demo stopped.")


if __name__ == "__main__":
    main()
