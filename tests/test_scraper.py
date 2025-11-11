from __future__ import annotations

from pathlib import Path

from scraper import cli
from scraper.core import PublicProfileScraper, SelectorProfileParser
from scraper.recorders import CSVRecorder, JSONLinesRecorder


def load_sample_html() -> str:
    return Path(__file__).with_name("sample_profile.html").read_text(encoding="utf8")


def build_sample_parser() -> SelectorProfileParser:
    selectors = {
        "name": ".profile-name",
        "followers": ".stat.followers .stat-value",
        "friends": ".stat.friends .stat-value",
        "fans": ".stat.fans .stat-value",
    }
    return SelectorProfileParser(selectors)


def test_sample_profile_scrape(tmp_path):
    html = load_sample_html()
    scraper = PublicProfileScraper(fetcher=lambda _: html)
    parser = build_sample_parser()

    metrics = scraper.scrape("file://sample", parser)

    assert metrics.name == "Jane Doe"
    assert metrics.followers == 1200
    assert metrics.friends == 320
    assert metrics.fans == 450
    assert metrics.source_url == "file://sample"


def test_recorders_write_expected_format(tmp_path):
    html = load_sample_html()
    scraper = PublicProfileScraper(fetcher=lambda _: html)
    parser = build_sample_parser()
    metrics = scraper.scrape("file://sample", parser)

    jsonl_path = tmp_path / "metrics.jsonl"
    csv_path = tmp_path / "metrics.csv"

    json_recorder = JSONLinesRecorder(jsonl_path)
    csv_recorder = CSVRecorder(csv_path)

    json_recorder.record(metrics)
    csv_recorder.record(metrics)

    assert jsonl_path.exists()
    assert csv_path.exists()

    json_content = jsonl_path.read_text(encoding="utf8").strip()
    assert metrics.name in json_content

    csv_lines = csv_path.read_text(encoding="utf8").splitlines()
    assert csv_lines[0].startswith("source_url")
    assert any("Jane Doe" in line for line in csv_lines[1:])


def test_cli_reports_parse_error(tmp_path, capsys):
    malformed = tmp_path / "broken.html"
    malformed.write_text("<html></html>", encoding="utf8")

    exit_code = cli.main([str(malformed), "--from-file"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "parser expects html" in captured.err.lower()
