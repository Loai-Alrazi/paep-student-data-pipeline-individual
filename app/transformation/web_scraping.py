"""Validation, cleaning, and transformation for independent scraped quotes."""

from __future__ import annotations

import pandas as pd


RAW_COLUMNS = ["quote_text", "author", "tags", "source_url"]
OUTPUT_COLUMNS = RAW_COLUMNS + ["tag_count", "quote_length"]


class ScrapedQuoteDataError(ValueError):
    """Raised when scraped quote records do not satisfy their small contract."""


def validate_scraped_quotes(data: pd.DataFrame) -> pd.DataFrame:
    """Validate the scraped schema and required textual values."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("scraped quote data must be a pandas DataFrame")
    missing_columns = sorted(set(RAW_COLUMNS).difference(data.columns))
    if missing_columns:
        raise ScrapedQuoteDataError(
            f"Scraped quote data is missing columns: {', '.join(missing_columns)}"
        )
    if data.empty:
        raise ScrapedQuoteDataError("Scraped quote data is empty")

    validated = data.loc[:, RAW_COLUMNS].copy(deep=True)
    for column in ("quote_text", "author", "source_url"):
        values = validated[column].astype("string")
        if values.isna().any() or values.str.strip().eq("").any():
            raise ScrapedQuoteDataError(
                f"Scraped quote data contains a blank {column} value"
            )
    return validated


def clean_scraped_quotes(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize whitespace and discard exact repeated quote/author pairs."""
    cleaned = data.copy(deep=True)
    for column in RAW_COLUMNS:
        cleaned[column] = cleaned[column].map(
            lambda value: " ".join(value.split()) if isinstance(value, str) else value
        )
    return cleaned.drop_duplicates(
        subset=["quote_text", "author"], keep="first"
    ).reset_index(drop=True)


def transform_scraped_quotes(data: pd.DataFrame) -> pd.DataFrame:
    """Add small, deterministic features useful for demonstrating transform."""
    transformed = data.copy(deep=True)
    transformed["tag_count"] = transformed["tags"].map(
        lambda tags: len([tag for tag in tags.split("|") if tag])
        if isinstance(tags, str)
        else 0
    )
    transformed["quote_length"] = transformed["quote_text"].str.len()
    return transformed.loc[:, OUTPUT_COLUMNS]
