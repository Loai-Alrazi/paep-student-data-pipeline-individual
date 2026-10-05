import json

import pandas as pd
import pytest
import requests

from app.sources.base_source import BaseSource
from app.sources.web_api_source import WEB_COLUMNS, WebAPISource, WebAPISourceError


CONFIG = {
    "url": "https://example.test/users",
    "timeout_seconds": 3,
    "student_id_offset": 1000,
}


class FakeResponse:
    def __init__(self, payload, status_error=None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.payload


def test_web_source_normalizes_jsonplaceholder_user(monkeypatch):
    payload = [
        {
            "id": 1,
            "name": "Leanne Graham",
            "username": "Bret",
            "email": "LEANNE@example.test",
            "phone": "1-770-736-8031",
            "website": "hildegard.org",
            "address": {"city": "Gwenborough"},
            "company": {"name": "Romaguera-Crona"},
        }
    ]
    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return FakeResponse(payload)

    monkeypatch.setattr(requests, "get", fake_get)
    source = WebAPISource(CONFIG)
    result = source.extract()

    assert isinstance(source, BaseSource)
    assert isinstance(result, pd.DataFrame)
    assert result.columns.tolist() == WEB_COLUMNS
    assert result.iloc[0].to_dict() == {
        "student_id": 1001,
        "web_name": "Leanne Graham",
        "web_username": "Bret",
        "web_email": "LEANNE@example.test",
        "web_phone": "1-770-736-8031",
        "web_website": "hildegard.org",
        "web_city": "Gwenborough",
        "company_name": "Romaguera-Crona",
    }
    assert calls == [(CONFIG["url"], 3)]


def test_web_source_reports_timeout(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("slow")

    monkeypatch.setattr(requests, "get", timeout)
    with pytest.raises(WebAPISourceError, match="timed out"):
        WebAPISource(CONFIG).extract()


def test_web_source_rejects_non_array_payload(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse({"id": 1}))
    with pytest.raises(WebAPISourceError, match="JSON array"):
        WebAPISource(CONFIG).extract()


def test_web_source_requires_user_fields(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse([{"id": 1}]))
    with pytest.raises(WebAPISourceError, match="missing required field"):
        WebAPISource(CONFIG).extract()


@pytest.mark.parametrize(
    "config",
    [
        {"url": "", "timeout_seconds": 1},
        {"url": "https://example.test", "timeout_seconds": 0},
        {"url": "https://example.test", "timeout_seconds": True},
        {"url": "https://example.test", "timeout_seconds": 1, "student_id_offset": 1.5},
    ],
)
def test_web_source_rejects_invalid_configuration(config):
    with pytest.raises(WebAPISourceError):
        WebAPISource(config)
