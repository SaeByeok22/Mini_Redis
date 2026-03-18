# Parser Design

## Goal

`parser.py` is the command parsing layer for the mini Redis MVP.

It only does three things:

- split the input string by whitespace
- normalize the command name to uppercase
- validate the command name and argument count

It does not store data and it does not send network responses.

## Interface

```python
parse_command(raw_command: str) -> tuple[str, list[str]]
```

Examples:

```python
parse_command("PING")        # ("PING", [])
parse_command("SET a 1")     # ("SET", ["a", "1"])
parse_command("  GET a  ")   # ("GET", ["a"])
parse_command("del a")       # ("DEL", ["a"])
```

Invalid input raises `ParseError`.

Examples:

```python
parse_command("")            # ParseError("empty command")
parse_command("UNKNOWN a")   # ParseError("unknown command: UNKNOWN")
parse_command("SET a")       # ParseError("SET expects 2 argument(s), got 1")
```

## Supported Commands

- `PING`
- `SET key value`
- `GET key`
- `DEL key`
- `EXPIRE key seconds`
- `TTL key`

`EXPIRE` and `TTL` are included because they are optional extensions in the project
scope, but the required MVP commands are still `PING`, `SET`, `GET`, and `DEL`.

## Edge Cases Handled

- leading and trailing whitespace
- multiple spaces between tokens
- lowercase command names
- empty input
- unsupported commands
- wrong argument count
- non-string input

## How To Connect It In `server.py`

1. receive one line from the client
2. decode it to `str`
3. call `parse_command(...)`
4. if `ParseError` is raised, return `ERROR ...`
5. otherwise, dispatch to `Storage`

Expected flow:

```text
client input -> parser.parse_command() -> (command, args) -> storage/server response
```
