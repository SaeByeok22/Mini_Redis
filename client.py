"""Small RESP client for the mini Redis server."""

from __future__ import annotations

import argparse
import socket
from typing import BinaryIO


def encode_resp_command(parts: list[str]) -> bytes:
    """Encode one command as a RESP array of bulk strings."""
    chunks = [f"*{len(parts)}\r\n".encode("utf-8")]
    for part in parts:
        payload = part.encode("utf-8")
        chunks.append(f"${len(payload)}\r\n".encode("utf-8"))
        chunks.append(payload + b"\r\n")
    return b"".join(chunks)


def read_resp_response(client_file: BinaryIO) -> str:
    """Read one RESP response and format it for terminal output."""
    first_line = client_file.readline()
    if not first_line:
        raise RuntimeError("server closed the connection")

    prefix = first_line[:1]
    body = first_line[1:].decode("utf-8", errors="replace").rstrip("\r\n")

    if prefix == b"+":
        return body

    if prefix == b"-":
        return body

    if prefix == b":":
        return body

    if prefix == b"$":
        length = int(body)
        if length == -1:
            return "nil"

        payload = client_file.read(length)
        if payload is None or len(payload) != length:
            raise RuntimeError("incomplete bulk string payload")

        if client_file.read(2) != b"\r\n":
            raise RuntimeError("bulk string missing CRLF")

        return payload.decode("utf-8", errors="replace")

    raise RuntimeError("unsupported RESP response")


def run_command(command_parts: list[str], host: str, port: int) -> str:
    """Send one RESP command to the server and return the decoded response."""
    if not command_parts:
        raise ValueError("command is required")

    payload = encode_resp_command(command_parts)
    with socket.create_connection((host, port)) as client_socket:
        with client_socket.makefile("rwb") as client_file:
            client_file.write(payload)
            client_file.flush()
            return read_resp_response(client_file)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send one RESP command to Mini Redis.")
    parser.add_argument("--host", default="127.0.0.1", help="server host")
    parser.add_argument("--port", type=int, default=6380, help="server port")
    parser.add_argument("command", nargs="*", help="command and arguments")
    return parser


def run_repl(host: str, port: int) -> None:
    """Interactive prompt that sends each line as one RESP command."""
    print(f"RESP client connected to {host}:{port}")
    print("Type commands like: PING, SET a 1, GET a")
    print("Type exit or quit to stop.")

    while True:
        try:
            raw = input("resp> ").strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            break

        if not raw:
            continue

        if raw.lower() in {"exit", "quit"}:
            break

        try:
            response = run_command(raw.split(), host=host, port=port)
        except Exception as exc:
            print(f"ERROR {exc}")
            continue

        print(response)


def main() -> None:
    args = build_parser().parse_args()
    if not args.command:
        run_repl(host=args.host, port=args.port)
        return

    response = run_command(args.command, host=args.host, port=args.port)
    print(response)


if __name__ == "__main__":
    main()
