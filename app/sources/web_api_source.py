"""Extract and normalize a simple public web API into student directory data."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pandas as pd
import requests

from app.sources.base_source import BaseSource
from app.utils.config_loader import load_config


WEB_COLUMNS = [
    "student_id",
    "web_name",
    "web_username",
    "web_email",
    "web_phone",
    "web_website",
    "web_city",
    "company_name",
]


class WebAPISourceError(RuntimeError):
    """Public web API configuration, request, or payload failure."""


class WebAPISource(BaseSource):
    """Adapt JSONPlaceholder-style user objects to the pipeline join key."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        if config is None:
            config = load_config()["sources"]["web"]
        try:
            self.url = config["url"]
            self.timeout_seconds = config["timeout_seconds"]
            self.student_id_offset = config.get("student_id_offset", 1000)
        except (KeyError, TypeError) as exc:
            raise WebAPISourceError(
                "Web API configuration requires url and timeout_seconds"
            ) from exc

        if not isinstance(self.url, str) or not self.url.strip():
            raise WebAPISourceError("Web API url must be a non-empty string")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise WebAPISourceError(
                "Web API timeout_seconds must be a positive finite number"
            )
        if (
            isinstance(self.student_id_offset, bool)
            or not isinstance(self.student_id_offset, int)
        ):
            raise WebAPISourceError("Web API student_id_offset must be an integer")

    def extract(self) -> pd.DataFrame:
        try:
            response = requests.get(self.url, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.Timeout as exc:
            raise WebAPISourceError("Web API request timed out") from exc
        except requests.RequestException as exc:
            raise WebAPISourceError(f"Web API request failed: {exc}") from exc

        try:
            payload = response.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise WebAPISourceError("Web API returned invalid JSON") from exc

        if not isinstance(payload, list) or not payload:
            raise WebAPISourceError("Web API must return a non-empty JSON array")

        records = [self._normalize_record(record, index) for index, record in enumerate(payload)]
        return pd.DataFrame.from_records(records, columns=WEB_COLUMNS)

    def _normalize_record(self, record: object, index: int) -> dict[str, Any]:
        if not isinstance(record, dict):
            raise WebAPISourceError(f"Web API record {index} must be an object")
        for field in ("id", "name", "username", "email"):
            if field not in record:
                raise WebAPISourceError(
                    f"Web API record {index} is missing required field: {field}"
                )
        raw_id = record["id"]
        if isinstance(raw_id, bool) or not isinstance(raw_id, int):
            raise WebAPISourceError(
                f"Web API record {index} id must be an integer"
            )

        address = record.get("address")
        company = record.get("company")
        return {
            "student_id": self.student_id_offset + raw_id,
            "web_name": record["name"],
            "web_username": record["username"],
            "web_email": record["email"],
            "web_phone": record.get("phone"),
            "web_website": record.get("website"),
            "web_city": address.get("city") if isinstance(address, dict) else None,
            "company_name": company.get("name") if isinstance(company, dict) else None,
        }


def extract_web_data(config: Mapping[str, Any] | None = None) -> pd.DataFrame:
    """Compatibility wrapper returning normalized public web records."""
    return WebAPISource(config).extract()
