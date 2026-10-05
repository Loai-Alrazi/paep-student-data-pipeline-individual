"""Extract quote records from a simple HTML page with BeautifulSoup."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from app.sources.base_source import BaseSource
from app.utils.config_loader import load_config


SCRAPED_COLUMNS = ["quote_text", "author", "tags", "source_url"]


class WebScrapingSourceError(RuntimeError):
    """Raised when the HTML source cannot be requested or parsed."""


class WebScrapingSource(BaseSource):
    """Scrape quotes from the educational quotes.toscrape.com layout."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        if config is None:
            config = load_config()["sources"]["web_scraping"]
        try:
            self.url = config["url"]
            self.timeout_seconds = config["timeout_seconds"]
        except (KeyError, TypeError) as exc:
            raise WebScrapingSourceError(
                "Web scraping configuration requires url and timeout_seconds"
            ) from exc

        if not isinstance(self.url, str) or not self.url.strip():
            raise WebScrapingSourceError("Web scraping url must be a non-empty string")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise WebScrapingSourceError(
                "Web scraping timeout_seconds must be a positive finite number"
            )

    def extract(self) -> pd.DataFrame:
        try:
            response = requests.get(
                self.url,
                timeout=self.timeout_seconds,
                headers={"User-Agent": "PAEP-Student-Pipeline/1.0 (educational project)"},
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise WebScrapingSourceError("Web scraping request timed out") from exc
        except requests.RequestException as exc:
            raise WebScrapingSourceError(f"Web scraping request failed: {exc}") from exc

        soup = BeautifulSoup(response.text, "html.parser")
        quote_elements = soup.select("div.quote")
        if not quote_elements:
            raise WebScrapingSourceError(
                "Web page did not contain any 'div.quote' elements"
            )

        records: list[dict[str, str]] = []
        for index, element in enumerate(quote_elements):
            text_element = element.select_one("span.text")
            author_element = element.select_one("small.author")
            if text_element is None or author_element is None:
                raise WebScrapingSourceError(
                    f"Quote element {index} is missing quote text or author"
                )
            tags = [tag.get_text(" ", strip=True) for tag in element.select("a.tag")]
            records.append(
                {
                    "quote_text": text_element.get_text(" ", strip=True),
                    "author": author_element.get_text(" ", strip=True),
                    "tags": "|".join(tag for tag in tags if tag),
                    "source_url": self.url,
                }
            )

        return pd.DataFrame.from_records(records, columns=SCRAPED_COLUMNS)


def extract_web_scraping_data(
    config: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Compatibility wrapper returning raw records parsed from HTML."""
    return WebScrapingSource(config).extract()
