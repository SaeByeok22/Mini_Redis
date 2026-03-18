from io import BytesIO

from client import encode_resp_command, read_resp_response


def test_encode_resp_command_for_ping():
    payload = encode_resp_command(["PING"])

    assert payload == b"*1\r\n$4\r\nPING\r\n"


def test_encode_resp_command_for_set():
    payload = encode_resp_command(["SET", "a", "1"])

    assert payload == b"*3\r\n$3\r\nSET\r\n$1\r\na\r\n$1\r\n1\r\n"


def test_read_resp_response_for_simple_string():
    response = read_resp_response(BytesIO(b"+PONG\r\n"))

    assert response == "PONG"


def test_read_resp_response_for_integer():
    response = read_resp_response(BytesIO(b":1\r\n"))

    assert response == "1"


def test_read_resp_response_for_null_bulk_string():
    response = read_resp_response(BytesIO(b"$-1\r\n"))

    assert response == "nil"


def test_read_resp_response_for_bulk_string():
    response = read_resp_response(BytesIO(b"$1\r\n1\r\n"))

    assert response == "1"
