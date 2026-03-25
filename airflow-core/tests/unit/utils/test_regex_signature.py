from __future__ import annotations

from airflow.utils.regex_signature import extract_signature


def test_extract_signature_normalizes_whitespace() -> None:
    signature = extract_signature("Error\n\t at   2025-02-10")
    assert "\\n" not in signature
    assert "\\t" not in signature


def test_extract_signature_normalizes_timestamps() -> None:
    signature_a = extract_signature("Error at 2025-02-10")
    signature_b = extract_signature("Error at 2025-02-11")
    assert signature_a == signature_b
    assert r"\d{4}-\d{2}-\d{2}" in signature_a


def test_extract_signature_replaces_uuid_path_and_numbers() -> None:
    signature = extract_signature(
        "Failed run 123 in /Users/me/project/file.py with id 550e8400-e29b-41d4-a716-446655440000"
    )
    assert r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}" in signature
    assert r"(?:(?:[A-Za-z]:\\)|/)[^\s:]+" in signature
    assert r"\d+" in signature


def test_extract_signature_preserves_http_codes() -> None:
    signature = extract_signature("HTTP 404 Not Found")
    assert "HTTP\\ 404\\ Not\\ Found" in signature
    assert "HTTP\\ \\d+" not in signature


def test_extract_signature_replaces_token_number() -> None:
    signature = extract_signature("KeyError: token_4876")
    assert "token_\\d+" in signature
