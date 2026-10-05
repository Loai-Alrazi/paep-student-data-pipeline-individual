import pandas as pd
import pytest

from app.output.mongodb_writer import MongoDBWriterError, write_mongodb


CONFIG = {
    "uri": "mongodb://example:27017",
    "database": "students",
    "collection": "final_students",
    "server_selection_timeout_ms": 750,
}


class FakeCollection:
    def __init__(self):
        self.deleted = None
        self.index = None
        self.inserted = None

    def delete_many(self, query):
        self.deleted = query

    def create_index(self, field, unique):
        self.index = (field, unique)

    def insert_many(self, records, ordered):
        self.inserted = (records, ordered)


class FakeClient:
    def __init__(self):
        self.collection = FakeCollection()
        self.closed = False

    def __getitem__(self, name):
        if name == "students":
            return self
        assert name == "final_students"
        return self.collection

    def close(self):
        self.closed = True


def test_writer_replaces_collection_and_converts_missing_values():
    client = FakeClient()
    frame = pd.DataFrame(
        {
            "student_id": [1001, 1002],
            "gpa": [3.5, float("nan")],
            "advisor_name": ["Maha", None],
        }
    )

    write_mongodb(frame, CONFIG, client_factory=lambda *_: client)

    assert client.collection.deleted == {}
    assert client.collection.index == ("student_id", True)
    records, ordered = client.collection.inserted
    assert records[1]["gpa"] is None
    assert records[1]["advisor_name"] is None
    assert ordered is True
    assert client.closed is True


def test_writer_rejects_duplicate_student_ids_before_connecting():
    frame = pd.DataFrame({"student_id": [1001, 1001]})
    with pytest.raises(ValueError, match="unique student_id"):
        write_mongodb(frame, CONFIG, client_factory=lambda *_: FakeClient())


def test_writer_wraps_database_errors_and_closes_client():
    client = FakeClient()

    def fail(query):
        raise RuntimeError("offline")

    client.collection.delete_many = fail
    with pytest.raises(MongoDBWriterError, match="Cannot replace MongoDB"):
        write_mongodb(
            pd.DataFrame({"student_id": [1001]}),
            CONFIG,
            client_factory=lambda *_: client,
        )
    assert client.closed is True
