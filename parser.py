"""Command parser for the mini Redis MVP."""

from __future__ import annotations

from typing import BinaryIO, Literal


class ParseError(ValueError):
    """Raised when a command cannot be parsed or validated."""


COMMAND_SPECS: dict[str, int] = {
    "PING": 0,
    "SET": 2,
    "GET": 1,
    "DEL": 1,
    "EXPIRE": 2,
    "TTL": 1,
}


ProtocolType = Literal["inline", "resp"]


def parse_command(raw_command: str) -> tuple[str, list[str]]:
    """Parse a raw inline command string into an uppercased command and arguments."""
    if not isinstance(raw_command, str):
        raise ParseError("command must be a string")

    parts = raw_command.strip().split()
    if not parts:
        raise ParseError("empty command")

    command = parts[0].upper()
    args = parts[1:]

    return _validate_command(command, args)


def parse_resp_command(client_file: BinaryIO, first_line: bytes) -> tuple[str, list[str]]:
    """Parse one RESP array command from a socket-like buffered stream."""
    header = _decode_line(first_line)
    if not header.startswith("*"):
        raise ParseError("RESP array expected")

    try:
        item_count = int(header[1:])
    except ValueError as exc:
        raise ParseError("invalid RESP array length") from exc

    if item_count <= 0:
        raise ParseError("RESP array must contain at least one item")

    parts: list[str] = []
    for _ in range(item_count):
        length_line = client_file.readline()
        if not length_line:
            raise ParseError("incomplete RESP bulk string length")

        length_header = _decode_line(length_line)
        if not length_header.startswith("$"):
            raise ParseError("RESP array items must be bulk strings")

        try:
            length = int(length_header[1:])
        except ValueError as exc:
            raise ParseError("invalid RESP bulk string length") from exc

        if length < 0:
            raise ParseError("RESP null bulk strings are not supported")

        data = client_file.read(length)
        if data is None or len(data) != length:
            raise ParseError("incomplete RESP bulk string data")

        if client_file.read(2) != b"\r\n":
            raise ParseError("RESP bulk string must end with CRLF")

        parts.append(data.decode("utf-8", errors="replace"))

    command = parts[0].upper()
    args = parts[1:]

    return _validate_command(command, args)


def read_request(client_file: BinaryIO) -> tuple[ProtocolType, str, list[str]] | None:
    """Read one inline or RESP request from a socket-like buffered stream."""
    first_line = client_file.readline()
    if not first_line:
        return None

    if first_line.startswith(b"*"):
        command, args = parse_resp_command(client_file, first_line)
        return "resp", command, args

    request = first_line.decode("utf-8", errors="replace").rstrip("\r\n")
    command, args = parse_command(request)
    return "inline", command, args


def _validate_command(command: str, args: list[str]) -> tuple[str, list[str]]:
    """Validate the normalized command and argument list."""

    if command not in COMMAND_SPECS:
        raise ParseError(f"unknown command: {command}")

    expected_arg_count = COMMAND_SPECS[command]
    if len(args) != expected_arg_count:
        raise ParseError(
            f"{command} expects {expected_arg_count} argument(s), got {len(args)}"
        )

    return command, args


def _decode_line(line: bytes) -> str:
    return line.decode("utf-8", errors="replace").rstrip("\r\n")
