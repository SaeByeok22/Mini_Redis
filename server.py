"""TCP server for the mini Redis MVP."""

from __future__ import annotations

import socket
from typing import Protocol

from parser import ParseError, parse_command


class StorageProtocol(Protocol):
    """Shared storage interface used by the server layer."""

    def set(self, key: str, value: str) -> str:
        ...

    def get(self, key: str) -> str | None:
        ...

    def delete(self, key: str) -> bool:
        ...


class MiniRedisServer:
    """A small line-based TCP server that dispatches commands to storage."""

    def __init__(self, storage: StorageProtocol, host: str = "127.0.0.1", port: int = 6380):
        self.storage = storage
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None

    def serve_forever(self) -> None:
        """Start the TCP server and handle one connection at a time."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            self._sock = server_socket
            self.host, self.port = server_socket.getsockname()

            while True:
                client_socket, _ = server_socket.accept()
                with client_socket:
                    self._handle_client(client_socket)

    def _handle_client(self, client_socket: socket.socket) -> None:
        with client_socket.makefile("rwb") as client_file:
            while True:
                raw_line = client_file.readline()
                if not raw_line:
                    break

                request = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                response = self.handle_request(request)
                client_file.write(f"{response}\n".encode("utf-8"))
                client_file.flush()

    def handle_request(self, request: str) -> str:
        """Convert a raw request string into a protocol response."""
        try:
            command, args = parse_command(request)
        except ParseError as exc:
            return f"ERROR {exc}"

        if command == "PING":
            return "PONG"

        if command == "SET":
            key, value = args
            return self.storage.set(key, value)

        if command == "GET":
            value = self.storage.get(args[0])
            return value if value is not None else "nil"

        if command == "DEL":
            deleted = self.storage.delete(args[0])
            return "1" if deleted else "0"

        if command == "EXPIRE":
            return self._handle_expire(args)

        if command == "TTL":
            return self._handle_ttl(args)

        return f"ERROR unsupported command: {command}"

    def _handle_expire(self, args: list[str]) -> str:
        if not hasattr(self.storage, "expire"):
            return "ERROR EXPIRE not supported"

        key, seconds_text = args
        try:
            seconds = int(seconds_text)
        except ValueError:
            return "ERROR EXPIRE seconds must be an integer"

        if seconds < 0:
            return "ERROR EXPIRE seconds must be non-negative"

        expired = self.storage.expire(key, seconds)  # type: ignore[attr-defined]
        return "1" if expired else "0"

    def _handle_ttl(self, args: list[str]) -> str:
        if not hasattr(self.storage, "ttl"):
            return "ERROR TTL not supported"

        ttl_value = self.storage.ttl(args[0])  # type: ignore[attr-defined]
        return str(ttl_value)


def create_default_server(host: str = "127.0.0.1", port: int = 6380) -> MiniRedisServer:
    """Build a server using the project's Storage implementation."""
    try:
        from storage import Storage
    except ImportError as exc:
        raise RuntimeError("storage.py with a Storage class is required to run the server") from exc

    return MiniRedisServer(storage=Storage(), host=host, port=port)


def main() -> None:
    server = create_default_server()
    print(f"Mini Redis server listening on {server.host}:{server.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
