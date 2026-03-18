from io import BytesIO

import pytest

from parser import parse_command, parse_resp_command, read_request


def test_parse_ping_command():
    command, args = parse_command("PING")

    assert command == "PING"
    assert args == []


def test_parse_set_command():
    command, args = parse_command("SET a 1")

    assert command == "SET"
    assert args == ["a", "1"]


def test_parse_get_command():
    command, args = parse_command("GET a")

    assert command == "GET"
    assert args == ["a"]


def test_parse_del_command():
    command, args = parse_command("DEL a")

    assert command == "DEL"
    assert args == ["a"]


def test_parse_persist_command():
    command, args = parse_command("PERSIST a")

    assert command == "PERSIST"
    assert args == ["a"]


def test_parse_exists_command():
    command, args = parse_command("EXISTS a")

    assert command == "EXISTS"
    assert args == ["a"]


def test_parse_flush_command():
    command, args = parse_command("FLUSH")

    assert command == "FLUSH"
    assert args == []


def test_parse_keys_command():
    command, args = parse_command("KEYS")

    assert command == "KEYS"
    assert args == []


def test_parse_command_ignores_extra_spaces():
    command, args = parse_command("  SET   a   1  ")

    assert command == "SET"
    assert args == ["a", "1"]


def test_parse_empty_input_raises_value_error():
    with pytest.raises(ValueError):
        parse_command("")


def test_parse_set_with_missing_arguments_raises_value_error():
    with pytest.raises(ValueError):
        parse_command("SET a")


def test_parse_unknown_command_raises_value_error():
    with pytest.raises(ValueError):
        parse_command("UNKNOWN something")


def test_parse_resp_ping_command():
    command, args = parse_resp_command(BytesIO(b"$4\r\nPING\r\n"), b"*1\r\n")

    assert command == "PING"
    assert args == []


def test_parse_resp_set_command():
    command, args = parse_resp_command(
        BytesIO(b"$3\r\nSET\r\n$1\r\na\r\n$1\r\n1\r\n"),
        b"*3\r\n",
    )

    assert command == "SET"
    assert args == ["a", "1"]


def test_read_request_detects_inline_protocol():
    request = read_request(BytesIO(b"PING\n"))

    assert request == ("inline", "PING", [])


def test_read_request_detects_resp_protocol():
    request = read_request(BytesIO(b"*2\r\n$3\r\nGET\r\n$1\r\na\r\n"))

    assert request == ("resp", "GET", ["a"])
