"""Provider JSON parsing tests."""

import pytest

from glorious_mess_reviewer.providers import ProviderError, extract_json_payload


def test_extract_json_payload_from_fenced_block() -> None:
    payload = extract_json_payload("```json\n{\"ok\": true}\n```")
    assert payload == {"ok": True}


def test_extract_json_payload_rejects_invalid_text() -> None:
    with pytest.raises(ProviderError):
        extract_json_payload("not json at all")
