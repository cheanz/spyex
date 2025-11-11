# spyex

A small, extensible scraper that records follower, friend, and fan counts exposed on
public profile pages.

## Features

- Parse profile pages using CSS selectors so that each platform can supply its own rules.
- Normalises shorthand counters such as `1.2k` into integers for storage.
- Persist results to JSON Lines or CSV for later processing.
- Command line interface that can target remote URLs or local HTML snapshots.

## Installation

Create a virtual environment (optional) and install the dependencies (none are strictly
required for the core scraper, but this keeps the environment isolated):

```bash
python -m venv .venv
source .venv/bin/activate
# No external dependencies are required
```

## Usage

Scrape a public profile that matches one of the configured site parsers:

```bash
python -m scraper.cli "https://example.com/profile/jane" --site sample
```

To scrape a local HTML file, use the `--from-file` flag. The bundled `sample` site
configuration matches `tests/sample_profile.html`.

```bash
python -m scraper.cli tests/sample_profile.html --from-file --pretty
```

Persist the metrics to disk by providing an output path. Use a `.jsonl` extension to
produce JSON Lines, otherwise CSV is written:

```bash
python -m scraper.cli tests/sample_profile.html --from-file --output data/metrics.csv
```

## Extending

To support a new platform, create a module in `scraper/sites/` that returns a
`SelectorProfileParser` configured with CSS selectors for the profile name, followers,
friends, and fans. Register the parser in `scraper/cli.py`.

## Tests

Run the unit test suite with:

```bash
python -m pytest
```
