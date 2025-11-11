"""Core scraping primitives for extracting public profile metrics."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from html.parser import HTMLParser


class FetchError(RuntimeError):
    """Raised when a profile page cannot be retrieved."""


class ParseError(RuntimeError):
    """Raised when the scraper cannot extract the required information."""


class HTMLFetcher(Protocol):
    """Protocol for callables able to retrieve HTML from a URL."""

    def __call__(self, url: str) -> str:
        """Return the HTML for ``url`` or raise :class:`FetchError`."""


@dataclass(slots=True)
class ProfileMetrics:
    """Structured representation of the metrics captured for a profile."""

    source_url: str
    name: str
    followers: int
    friends: int
    fans: int
    scraped_at: datetime

    def asdict(self) -> Dict[str, str | int]:
        """Return a serialisable representation of the metrics."""

        payload = asdict(self)
        payload["scraped_at"] = self.scraped_at.isoformat()
        return payload


def default_fetcher(url: str, *, timeout: int = 10) -> str:
    """Retrieve ``url`` using :mod:`urllib` and return its HTML body."""

    try:
        with urlopen(url, timeout=timeout) as response:
            if response.status != 200:
                raise FetchError(
                    f"Expected HTTP 200 when fetching {url}, received {response.status}"
                )
            data = response.read()
    except HTTPError as exc:  # pragma: no cover - network failure
        raise FetchError(
            f"HTTP error when fetching {url}: {exc.code} {exc.reason}"
        ) from exc
    except URLError as exc:  # pragma: no cover - network failure
        raise FetchError(f"Unable to fetch {url}: {exc.reason}") from exc

    return data.decode("utf8", errors="replace")


def _normalise_count(raw_value: str) -> int:
    """Convert a human readable counter (``1.2k``) to an integer."""

    raw_value = raw_value.strip().replace(",", "")
    if not raw_value:
        raise ParseError("Encountered an empty counter value")

    suffix = raw_value[-1].lower()
    multiplier = 1
    if suffix in {"k", "m", "b"}:
        raw_value = raw_value[:-1]
        if suffix == "k":
            multiplier = 1_000
        elif suffix == "m":
            multiplier = 1_000_000
        elif suffix == "b":
            multiplier = 1_000_000_000

    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ParseError(f"Could not parse counter value '{raw_value}'") from exc

    return int(value * multiplier)


class _SelectorToken:
    """Representation of a minimal CSS selector token."""

    __slots__ = ("tag", "classes")

    def __init__(self, tag: Optional[str], classes: Sequence[str]) -> None:
        self.tag = tag
        self.classes = tuple(classes)

    @classmethod
    def parse(cls, token: str) -> "_SelectorToken":
        token = token.strip()
        if not token:
            raise ValueError("Selector tokens cannot be empty")

        tag = None
        classes: List[str] = []
        fragments = token.split(".")
        if fragments[0] and fragments[0] != "*":
            tag = fragments[0]
        classes.extend(filter(None, fragments[1:]))
        return cls(tag, classes)


class _Node:
    """Simple DOM node tree used for lightweight CSS selection."""

    __slots__ = ("tag", "attrs", "children", "text", "parent")

    def __init__(self, tag: str, attrs: Dict[str, str], parent: Optional["_Node"] = None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: List["_Node"] = []
        self.text: List[str] = []
        self.parent = parent

    def append_child(self, child: "_Node") -> None:
        self.children.append(child)

    def append_text(self, data: str) -> None:
        if data:
            self.text.append(data)

    # traversal utilities
    def iter_descendants(self) -> List["_Node"]:
        nodes: List["_Node"] = []
        stack = list(self.children)
        while stack:
            node = stack.pop(0)
            nodes.append(node)
            stack[0:0] = node.children
        return nodes

    def get_text(self, *, strip: bool = False) -> str:
        parts: List[str] = []

        def _collect(node: "_Node") -> None:
            parts.extend(node.text)
            for child in node.children:
                _collect(child)

        _collect(self)
        combined = "".join(parts)
        return combined.strip() if strip else combined

    def has_classes(self, required: Sequence[str]) -> bool:
        if not required:
            return True
        classes = self.attrs.get("class", "").split()
        return all(cls in classes for cls in required)

    def matches(self, selector: _SelectorToken) -> bool:
        if selector.tag and self.tag != selector.tag:
            return False
        return self.has_classes(selector.classes)


class _MiniSoup(HTMLParser):
    """Very small subset of BeautifulSoup with class-only selectors."""

    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("document", {})
        self._stack: List[_Node] = [self.root]
        self.feed(html)
        self.close()

    # HTMLParser hooks
    def handle_starttag(self, tag: str, attrs: List[tuple[str, str | None]]) -> None:  # type: ignore[override]
        attr_dict = {name: value or "" for name, value in attrs}
        parent = self._stack[-1]
        node = _Node(tag, attr_dict, parent=parent)
        parent.append_child(node)
        self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if len(self._stack) > 1:
            self._stack.pop()

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if data:
            self._stack[-1].append_text(data)

    # selection API
    def select_one(self, selector: str) -> Optional[_Node]:
        tokens = [_SelectorToken.parse(part) for part in selector.split() if part]
        if not tokens:
            return None

        def _search(node: _Node, remaining: Sequence[_SelectorToken]) -> Optional[_Node]:
            if not remaining:
                return node
            token = remaining[0]
            for child in node.iter_descendants():
                if child.matches(token):
                    if len(remaining) == 1:
                        return child
                    found = _search(child, remaining[1:])
                    if found is not None:
                        return found
            return None

        return _search(self.root, tokens)


class SelectorProfileParser:
    """Parse a profile page using CSS selectors for each metric."""

    def __init__(
        self,
        selectors: Dict[str, str],
        *,
        name_selector: str = "name",
        followers_selector: str = "followers",
        friends_selector: str = "friends",
        fans_selector: str = "fans",
    ) -> None:
        required = {name_selector, followers_selector, friends_selector, fans_selector}
        missing = required.difference(selectors)
        if missing:
            joined = ", ".join(sorted(missing))
            raise ValueError(f"Selectors missing CSS rules for: {joined}")

        self._selectors = selectors
        self._name_key = name_selector
        self._followers_key = followers_selector
        self._friends_key = friends_selector
        self._fans_key = fans_selector

    def parse(self, html: str, *, url: str) -> ProfileMetrics:
        """Extract metrics from the supplied HTML snippet."""

        soup = _MiniSoup(html)
        name_element = soup.select_one(self._selectors[self._name_key])
        followers_element = soup.select_one(self._selectors[self._followers_key])
        friends_element = soup.select_one(self._selectors[self._friends_key])
        fans_element = soup.select_one(self._selectors[self._fans_key])

        if not all([name_element, followers_element, friends_element, fans_element]):
            raise ParseError("Failed to locate one or more required profile fields")

        name = name_element.get_text(strip=True)
        followers = _normalise_count(followers_element.get_text(strip=True))
        friends = _normalise_count(friends_element.get_text(strip=True))
        fans = _normalise_count(fans_element.get_text(strip=True))

        return ProfileMetrics(
            source_url=url,
            name=name,
            followers=followers,
            friends=friends,
            fans=fans,
            scraped_at=datetime.now(timezone.utc),
        )


class PublicProfileScraper:
    """High level orchestrator responsible for fetching and parsing profiles."""

    def __init__(self, fetcher: Optional[HTMLFetcher] = None) -> None:
        self._fetcher = fetcher or default_fetcher

    def scrape(self, url: str, parser: SelectorProfileParser) -> ProfileMetrics:
        """Fetch ``url`` and parse its metrics using ``parser``."""

        html = self._fetcher(url)
        return parser.parse(html, url=url)

    def scrape_from_html(self, html: str, *, url: str, parser: SelectorProfileParser) -> ProfileMetrics:
        """Parse the metrics directly from a supplied HTML fragment."""

        return parser.parse(html, url=url)
