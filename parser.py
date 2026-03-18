"""Command parser for the mini Redis MVP."""

from __future__ import annotations


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


def parse_command(raw_command: str) -> tuple[str, list[str]]:
    """Parse a raw command string into an uppercased command and arguments."""
    if not isinstance(raw_command, str):
        raise ParseError("command must be a string")

    parts = raw_command.strip().split()
    if not parts:
        raise ParseError("empty command")

    command = parts[0].upper()
    args = parts[1:]

    if command not in COMMAND_SPECS:
        raise ParseError(f"unknown command: {command}")

    expected_arg_count = COMMAND_SPECS[command]
    if len(args) != expected_arg_count:
        raise ParseError(
            f"{command} expects {expected_arg_count} argument(s), got {len(args)}"
        )

    return command, args
