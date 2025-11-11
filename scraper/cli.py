"""Command line interface for scraping public follower metrics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

from .core import PublicProfileScraper, SelectorProfileParser
from .recorders import CSVRecorder, JSONLinesRecorder, record_many
from .sites import sample as sample_site


PARSERS: Dict[str, SelectorProfileParser] = {
    "sample": sample_site.build_parser(),
}


def _load_parser(site: str) -> SelectorProfileParser:
    try:
        return PARSERS[site]
    except KeyError as exc:
        raise SystemExit(f"Unknown site '{site}'. Available options: {', '.join(PARSERS)}") from exc


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="URL or local file to scrape")
    parser.add_argument(
        "--site",
        choices=sorted(PARSERS),
        default="sample",
        help="Key of the site configuration to use (default: sample)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file (JSON Lines when .jsonl/.ndjson, CSV otherwise)",
    )
    parser.add_argument(
        "--from-file",
        action="store_true",
        help="Interpret 'source' as a local HTML file rather than a remote URL",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the metrics JSON to stdout",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arg_parser = build_arg_parser()
    args = arg_parser.parse_args(argv)
    parser = _load_parser(args.site)

    scraper = PublicProfileScraper()
    if args.from_file:
        html = Path(args.source).read_text(encoding="utf8")
        metrics = scraper.scrape_from_html(html, url=str(Path(args.source).resolve()), parser=parser)
    else:
        metrics = scraper.scrape(args.source, parser)

    if args.output:
        if args.output.suffix.lower() in {".jsonl", ".ndjson"}:
            recorder = JSONLinesRecorder(args.output)
        else:
            recorder = CSVRecorder(args.output)
        record_many(recorder, [metrics])

    payload = metrics.asdict()
    if args.pretty:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False))

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
