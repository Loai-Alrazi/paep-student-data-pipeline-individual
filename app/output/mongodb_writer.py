"""Load a final DataFrame as one MongoDB collection."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from datetime import date, datetime
from typing import Any

import pandas as pd


class MongoDBWriterError(RuntimeError):
    """MongoDB configuration, connection, or write failure."""


def _default_client_factory(uri: str, timeout_ms: int) -> Any:
    try:
        from pymongo import MongoClient
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise MongoDBWriterError(
            "pymongo is required for MongoDB support; install requirements.txt"
        ) from exc
    return MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)


def _settings(config: Mapping[str, Any]) -> tuple[str, str, str, int]:
    try:
        uri = config["uri"]
        database = config["database"]
        collection = config["collection"]
        timeout_ms = config.get("server_selection_timeout_ms", 5000)
    except (KeyError, TypeError) as exc:
        raise MongoDBWriterError(
            "MongoDB output requires uri, database, and collection"
        ) from exc

    uri_env = config.get("uri_env", "MONGODB_URI")
    if isinstance(uri_env, str) and uri_env.strip():
        uri = os.getenv(uri_env, uri)
    for key, value in (
        ("uri", uri),
        ("database", database),
        ("collection", collection),
    ):
        if not isinstance(value, str) or not value.strip():
            raise MongoDBWriterError(f"MongoDB {key} must be a non-empty string")
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms <= 0:
        raise MongoDBWriterError(
            "MongoDB server_selection_timeout_ms must be a positive integer"
        )
    return uri, database, collection, timeout_ms


def _python_value(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, (date, datetime)):
        return value
    return value


def _records(data: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {column: _python_value(value) for column, value in record.items()}
        for record in data.to_dict(orient="records")
    ]


def write_mongodb(
    data: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    client_factory: Callable[[str, int], Any] | None = None,
) -> None:
    """Replace the configured collection with the supplied final snapshot."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    if "student_id" not in data.columns:
        raise ValueError("MongoDB output requires a student_id column")
    if data["student_id"].duplicated().any():
        raise ValueError("MongoDB output requires unique student_id values")

    uri, database, collection_name, timeout_ms = _settings(config)
    factory = client_factory or _default_client_factory
    client = None
    try:
        client = factory(uri, timeout_ms)
        collection = client[database][collection_name]
        collection.delete_many({})
        collection.create_index("student_id", unique=True)
        records = _records(data)
        if records:
            collection.insert_many(records, ordered=True)
    except MongoDBWriterError:
        raise
    except Exception as exc:
        raise MongoDBWriterError(
            f"Cannot replace MongoDB collection '{database}.{collection_name}': {exc}"
        ) from exc
    finally:
        if client is not None:
            client.close()
