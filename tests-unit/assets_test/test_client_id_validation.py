"""POST /prompt enforces string-only client_id at submission time.

The client_id value is used as a dictionary key in WebSocket routing and
feature flag lookups. Python dictionaries require hashable keys, so arrays
and objects (unhashable types) cause TypeError when used in membership tests.
The membership test occurs before the socket-send exception wrapper, so the
error propagates through publish_loop and can terminate the server process.

This test verifies that non-string client_id values are rejected with a 400
error at the POST /prompt boundary, preventing unhashable values from reaching
the WebSocket routing layer.
"""

import requests


def _post_prompt(
    http: requests.Session, api_base: str, body: dict
) -> requests.Response:
    return http.post(api_base + "/prompt", json=body, timeout=30)


def _error_type(r: requests.Response) -> str:
    return r.json()["error"]["type"]


def test_array_client_id_rejected(http: requests.Session, api_base: str):
    """Array client_id must be rejected (unhashable, would crash publish_loop)."""
    r = _post_prompt(http, api_base, {"prompt": {}, "client_id": ["array", "value"]})
    assert r.status_code == 400, r.text
    assert _error_type(r) == "invalid_client_id"


def test_object_client_id_rejected(http: requests.Session, api_base: str):
    """Object client_id must be rejected (unhashable, would crash publish_loop)."""
    r = _post_prompt(http, api_base, {"prompt": {}, "client_id": {"key": "value"}})
    assert r.status_code == 400, r.text
    assert _error_type(r) == "invalid_client_id"


def test_number_client_id_rejected(http: requests.Session, api_base: str):
    """Numeric client_id must be rejected (wrong type, not a string)."""
    r = _post_prompt(http, api_base, {"prompt": {}, "client_id": 12345})
    assert r.status_code == 400, r.text
    assert _error_type(r) == "invalid_client_id"


def test_boolean_client_id_rejected(http: requests.Session, api_base: str):
    """Boolean client_id must be rejected (wrong type, not a string)."""
    r = _post_prompt(http, api_base, {"prompt": {}, "client_id": True})
    assert r.status_code == 400, r.text
    assert _error_type(r) == "invalid_client_id"


def test_string_client_id_accepted(http: requests.Session, api_base: str):
    """String client_id clears validation; workflow validation then runs."""
    r = _post_prompt(http, api_base, {"prompt": {}, "client_id": "valid-string-id"})
    assert r.status_code == 400, r.text
    # Empty workflow fails prompt validation, not client_id validation
    assert _error_type(r) != "invalid_client_id"


def test_null_client_id_accepted(http: requests.Session, api_base: str):
    """Null client_id is valid (means no targeted routing)."""
    r = _post_prompt(http, api_base, {"prompt": {}, "client_id": None})
    assert r.status_code == 400, r.text
    # Empty workflow fails prompt validation, not client_id validation
    assert _error_type(r) != "invalid_client_id"


def test_absent_client_id_accepted(http: requests.Session, api_base: str):
    """Absent client_id is valid (means no targeted routing)."""
    r = _post_prompt(http, api_base, {"prompt": {}})
    assert r.status_code == 400, r.text
    # Empty workflow fails prompt validation, not client_id validation
    assert _error_type(r) != "invalid_client_id"
