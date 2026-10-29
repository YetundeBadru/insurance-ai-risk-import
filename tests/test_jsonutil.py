import pytest

from app.jsonutil import parse_json_object


def test_plain_fenced_and_chatty_replies():
    assert parse_json_object('{"a": 1}') == {"a": 1}
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('Sure! Here you go:\n{"a": {"b": 2}}\nHope that helps.') == {"a": {"b": 2}}


def test_no_json_raises():
    with pytest.raises(ValueError):
        parse_json_object("I cannot help with that.")
