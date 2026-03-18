"""TCP server for the mini Redis MVP."""

from __future__ import annotations

import errno
import socket
from typing import Protocol

from parser import ParseError, ProtocolType, parse_command, read_request


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
            print(f"Mini Redis server listening on {self.host}:{self.port}")
            print(f"Connect from another terminal: nc {self.host} {self.port}")

            while True:
                client_socket, _ = server_socket.accept()
                with client_socket:
                    self._handle_client(client_socket)

    def _handle_client(self, client_socket: socket.socket) -> None:
        with client_socket.makefile("rwb") as client_file:
            while True:
                try:
                    parsed_request = read_request(client_file)
                except ParseError as exc:
                    client_file.write(self._serialize_error(str(exc), "inline"))
                    client_file.flush()
                    continue

                if parsed_request is None:
                    break

                protocol, command, args = parsed_request
                response_type, response_value = self.execute_command(command, args)
                client_file.write(
                    self._serialize_response(protocol, response_type, response_value)
                )
                client_file.flush()

    def handle_request(self, request: str) -> str:
        """Convert a raw request string into a protocol response."""
        try:
            command, args = parse_command(request)
        except ParseError as exc:
            return f"ERROR {exc}"

        response_type, response_value = self.execute_command(command, args)
        return self._format_inline_response(response_type, response_value)

    def execute_command(self, command: str, args: list[str]) -> tuple[str, str | int | None]:
        """Execute one already-parsed command and return a typed response."""
        if command == "PING":
            return "simple", "PONG"

        if command == "SET":
            key, value = args
            return "simple", self.storage.set(key, value)

        if command == "GET":
            return "bulk", self.storage.get(args[0])

        if command == "DEL":
            deleted = self.storage.delete(args[0])
            return "integer", 1 if deleted else 0

        if command == "EXPIRE":
            return self._handle_expire(args)

        if command == "TTL":
            return self._handle_ttl(args)

        return "error", f"unsupported command: {command}"

    def _handle_expire(self, args: list[str]) -> tuple[str, str | int]:
        if not hasattr(self.storage, "expire"):
            return "error", "EXPIRE not supported"

        key, seconds_text = args
        try:
            seconds = int(seconds_text)
        except ValueError:
            return "error", "EXPIRE seconds must be an integer"

        if seconds < 0:
            return "error", "EXPIRE seconds must be non-negative"

        expired = self.storage.expire(key, seconds)  # type: ignore[attr-defined]
        return "integer", 1 if expired else 0

    def _handle_ttl(self, args: list[str]) -> tuple[str, int | str]:
        if not hasattr(self.storage, "ttl"):
            return "error", "TTL not supported"

        ttl_value = self.storage.ttl(args[0])  # type: ignore[attr-defined]
        return "integer", ttl_value

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
    """Build a server using the project's Storage implementation."""
    try:
        from storage import Storage
    except ImportError as exc:
        raise RuntimeError("storage.py with a Storage class is required to run the server") from exc

    return MiniRedisServer(storage=Storage(), host=host, port=port)


def main() -> None:
    server = create_default_server()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nMini Redis server stopped.")
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            print(f"ERROR port {server.port} is already in use.")
            return
        raise


if __name__ == "__main__":
    main()
