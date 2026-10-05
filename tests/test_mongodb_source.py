import pandas as pd
import pytest

from app.sources.base_source import BaseSource
from app.sources.mongodb_source import MongoDBSource, MongoDBSourceError


CONFIG = {
    "uri": "mongodb://example:27017",
    "database": "students",
    "collection": "profiles",
    "server_selection_timeout_ms": 1234,
}


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents
        self.find_args = None

    def find(self, query, projection):
        self.find_args = (query, projection)
        return list(self.documents)


class FakeDatabase:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, name):
        assert name == "profiles"
        return self.collection


class FakeClient:
    def __init__(self, documents):
        self.collection = FakeCollection(documents)
        self.closed = False

    def __getitem__(self, name):
        assert name == "students"
        return FakeDatabase(self.collection)

    def close(self):
        self.closed = True


def test_mongodb_source_implements_contract_and_extracts_sorted_records(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    client = FakeClient(
        [
            {"student_id": 1002, "advisor_name": "B", "scholarship_status": "None"},
            {"student_id": 1001, "advisor_name": "A", "scholarship_status": "Full"},
        ]
    )
    calls = []

    def factory(uri, timeout_ms):
        calls.append((uri, timeout_ms))
        return client

    source = MongoDBSource(CONFIG, client_factory=factory)
    result = source.extract()

    assert isinstance(source, BaseSource)
    assert isinstance(result, pd.DataFrame)
    assert result["student_id"].tolist() == [1001, 1002]
    assert calls == [(CONFIG["uri"], 1234)]
    assert client.collection.find_args == ({}, {"_id": 0})
    assert client.closed is True


def test_mongodb_uri_can_come_from_environment(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://secret-host:27017")
    source = MongoDBSource(CONFIG, client_factory=lambda *_: FakeClient([]))
    assert source.uri == "mongodb://secret-host:27017"


def test_empty_collection_is_rejected_and_client_is_closed():
    client = FakeClient([])
    source = MongoDBSource(CONFIG, client_factory=lambda *_: client)

    with pytest.raises(MongoDBSourceError, match="is empty"):
        source.extract()

    assert client.closed is True


def test_missing_required_document_fields_are_reported():
    client = FakeClient([{"student_id": 1001}])
    source = MongoDBSource(CONFIG, client_factory=lambda *_: client)

    with pytest.raises(MongoDBSourceError, match="advisor_name.*scholarship_status"):
        source.extract()


def test_driver_errors_are_wrapped_and_client_is_closed():
    class BrokenCollection(FakeCollection):
        def find(self, query, projection):
            raise RuntimeError("offline")

    client = FakeClient([])
    client.collection = BrokenCollection([])
    source = MongoDBSource(CONFIG, client_factory=lambda *_: client)

    with pytest.raises(MongoDBSourceError, match="Cannot read MongoDB"):
        source.extract()

    assert client.closed is True
