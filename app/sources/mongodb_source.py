"""Extract supplemental student profiles from MongoDB."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any

import pandas as pd

from app.sources.base_source import BaseSource
from app.utils.config_loader import load_config


REQUIRED_FIELDS = {"student_id", "advisor_name", "scholarship_status"}


class MongoDBSourceError(RuntimeError):
    """MongoDB configuration, connection, or extraction failure."""


def _default_client_factory(uri: str, timeout_ms: int) -> Any:
    try:
        from pymongo import MongoClient
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise MongoDBSourceError(
            "pymongo is required for MongoDB support; install requirements.txt"
        ) from exc
    return MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)


def _read_settings(config: Mapping[str, Any]) -> tuple[str, str, str, int]:
    try:
        uri = config["uri"]
        database = config["database"]
        collection = config["collection"]
        timeout_ms = config.get("server_selection_timeout_ms", 5000)
    except (KeyError, TypeError) as exc:
        raise MongoDBSourceError(
            "MongoDB configuration requires uri, database, and collection"
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
            raise MongoDBSourceError(f"MongoDB {key} must be a non-empty string")
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms <= 0:
        raise MongoDBSourceError(
            "MongoDB server_selection_timeout_ms must be a positive integer"
        )
    return uri, database, collection, timeout_ms


class MongoDBSource(BaseSource):
    """Read one document per student from a configured MongoDB collection."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        client_factory: Callable[[str, int], Any] | None = None,
    ) -> None:
        if config is None:
            config = load_config()["sources"]["mongodb"]
        self.uri, self.database, self.collection, self.timeout_ms = _read_settings(
            config
        )
        self._client_factory = client_factory or _default_client_factory

    def extract(self) -> pd.DataFrame:
        client = None
        try:
            client = self._client_factory(self.uri, self.timeout_ms)
            documents = list(
                client[self.database][self.collection].find({}, {"_id": 0})
            )
        except MongoDBSourceError:
            raise
        except Exception as exc:
            raise MongoDBSourceError(
                f"Cannot read MongoDB collection "
                f"'{self.database}.{self.collection}': {exc}"
            ) from exc
        finally:
            if client is not None:
                client.close()

        if not documents:
            raise MongoDBSourceError(
                f"MongoDB collection '{self.database}.{self.collection}' is empty"
            )
        for index, document in enumerate(documents):
            if not isinstance(document, dict):
                raise MongoDBSourceError(
                    f"MongoDB document {index} must be an object"
                )
            missing = REQUIRED_FIELDS.difference(document)
            if missing:
                fields = ", ".join(sorted(missing))
                raise MongoDBSourceError(
                    f"MongoDB document {index} is missing required fields: {fields}"
                )

        frame = pd.DataFrame.from_records(documents)
        return frame.sort_values("student_id", kind="mergesort").reset_index(drop=True)


def extract_mongodb_data(
    config: Mapping[str, Any] | None = None,
    *,
    client_factory: Callable[[str, int], Any] | None = None,
) -> pd.DataFrame:
    """Compatibility wrapper returning raw MongoDB profile records."""
    return MongoDBSource(config, client_factory=client_factory).extract()
