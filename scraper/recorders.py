"""Utilities to persist scraped metrics for later analysis."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Protocol

from .core import ProfileMetrics


class MetricsRecorder(Protocol):
    """Protocol implemented by recorder classes."""

    def record(self, metrics: ProfileMetrics) -> None:
        """Persist the provided ``metrics`` entry."""


class JSONLinesRecorder:
    """Append metrics to a JSON Lines file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, metrics: ProfileMetrics) -> None:
        payload = metrics.asdict()
        with self._path.open("a", encoding="utf8") as fh:
            json.dump(payload, fh)
            fh.write("\n")


class CSVRecorder:
    """Append metrics to a CSV file and write headers when necessary."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fieldnames = [
            "source_url",
            "name",
            "followers",
            "friends",
            "fans",
            "scraped_at",
        ]

    def _needs_header(self) -> bool:
        return not self._path.exists() or self._path.stat().st_size == 0

    def record(self, metrics: ProfileMetrics) -> None:
        needs_header = self._needs_header()
        with self._path.open("a", encoding="utf8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=self._fieldnames)
            if needs_header:
                writer.writeheader()
            writer.writerow(metrics.asdict())


def record_many(recorder: MetricsRecorder, entries: Iterable[ProfileMetrics]) -> None:
    """Persist multiple metrics entries with a single call."""

    for metrics in entries:
        recorder.record(metrics)
