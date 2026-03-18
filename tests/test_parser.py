import pytest

from parser import parse_command


def test_parse_ping_command():
    command, args = parse_command("PING")

    assert command == "PING"
    assert args == []


def test_parse_set_command():
    command, args = parse_command("SET a 1")

    assert command == "SET"
    assert args == ["a", "1"]


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
