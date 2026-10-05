import pandas as pd
import pytest
import requests

from app.sources.base_source import BaseSource
from app.sources.web_scraping_source import (
    SCRAPED_COLUMNS,
    WebScrapingSource,
    WebScrapingSourceError,
)
from app.transformation.web_scraping import (
    OUTPUT_COLUMNS,
    ScrapedQuoteDataError,
    clean_scraped_quotes,
    transform_scraped_quotes,
    validate_scraped_quotes,
)


CONFIG = {
    "url": "https://example.test/quotes",
    "timeout_seconds": 3,
}

HTML = """
<html><body>
  <div class="quote">
    <span class="text">  “First   quote.”  </span>
    <small class="author">Ada Lovelace</small>
    <div class="tags"><a class="tag">wisdom</a><a class="tag">life</a></div>
  </div>
  <div class="quote">
    <span class="text">“Second quote.”</span>
    <small class="author">Grace Hopper</small>
  </div>
</body></html>
"""


class FakeResponse:
    def __init__(self, text, status_error=None):
        self.text = text
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error


def test_web_scraping_source_parses_real_html_elements(monkeypatch):
    calls = []

    def fake_get(url, timeout, headers):
        calls.append((url, timeout, headers))
        return FakeResponse(HTML)

    monkeypatch.setattr(requests, "get", fake_get)
    source = WebScrapingSource(CONFIG)
    result = source.extract()

    assert isinstance(source, BaseSource)
    assert isinstance(result, pd.DataFrame)
    assert result.columns.tolist() == SCRAPED_COLUMNS
    assert result.iloc[0].to_dict() == {
        "quote_text": "“First   quote.”",
        "author": "Ada Lovelace",
        "tags": "wisdom|life",
        "source_url": CONFIG["url"],
    }
    assert calls[0][0:2] == (CONFIG["url"], 3)
    assert "educational project" in calls[0][2]["User-Agent"]


def test_scraped_data_validate_clean_transform_pipeline():
    raw = pd.DataFrame(
        [
            {
                "quote_text": "  A   useful quote. ",
                "author": "  An Author ",
                "tags": "learning|life",
                "source_url": " https://example.test ",
            },
            {
                "quote_text": "A useful quote.",
                "author": "An Author",
                "tags": "learning|life",
                "source_url": "https://example.test",
            },
        ]
    )

    validated = validate_scraped_quotes(raw)
    cleaned = clean_scraped_quotes(validated)
    result = transform_scraped_quotes(cleaned)

    assert result.columns.tolist() == OUTPUT_COLUMNS
    assert len(result) == 1
    assert result.iloc[0]["quote_text"] == "A useful quote."
    assert result.iloc[0]["tag_count"] == 2
    assert result.iloc[0]["quote_length"] == len("A useful quote.")


def test_web_scraping_source_reports_timeout(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("slow")

    monkeypatch.setattr(requests, "get", timeout)
    with pytest.raises(WebScrapingSourceError, match="timed out"):
        WebScrapingSource(CONFIG).extract()


def test_web_scraping_source_rejects_page_without_quotes(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *args, **kwargs: FakeResponse("<html></html>")
    )
    with pytest.raises(WebScrapingSourceError, match="div.quote"):
        WebScrapingSource(CONFIG).extract()


def test_web_scraping_source_rejects_incomplete_quote(monkeypatch):
    html = '<div class="quote"><span class="text">No author</span></div>'
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse(html))
    with pytest.raises(WebScrapingSourceError, match="missing quote text or author"):
        WebScrapingSource(CONFIG).extract()


def test_scraped_validation_rejects_blank_required_value():
    data = pd.DataFrame(
        [{"quote_text": " ", "author": "A", "tags": "", "source_url": "u"}]
    )
    with pytest.raises(ScrapedQuoteDataError, match="blank quote_text"):
        validate_scraped_quotes(data)


@pytest.mark.parametrize(
    "config",
    [
        {"url": "", "timeout_seconds": 1},
        {"url": "https://example.test", "timeout_seconds": 0},
        {"url": "https://example.test", "timeout_seconds": True},
    ],
)
def test_web_scraping_source_rejects_invalid_configuration(config):
    with pytest.raises(WebScrapingSourceError):
        WebScrapingSource(config)
