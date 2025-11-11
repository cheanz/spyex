"""Sample configuration demonstrating how to scrape a generic profile page."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from ..core import PublicProfileScraper, SelectorProfileParser


def build_parser() -> SelectorProfileParser:
    """Return a parser configured for the bundled sample profile HTML."""

    selectors: Dict[str, str] = {
        "name": ".profile-name",
        "followers": ".stat.followers .stat-value",
        "friends": ".stat.friends .stat-value",
        "fans": ".stat.fans .stat-value",
    }
    return SelectorProfileParser(selectors)


def scrape_from_file(path: str | Path) -> None:
    """Example script that scrapes the bundled sample HTML file."""

    html = Path(path).read_text(encoding="utf8")
    scraper = PublicProfileScraper(fetcher=lambda _: html)
    parser = build_parser()
    metrics = scraper.scrape("file://" + str(Path(path).resolve()), parser)
    print(metrics.asdict())
