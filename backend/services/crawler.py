"""services/crawler.py — URL crawler for the Catalog Import Agent's URL branch.

Implements the "Branch — URL" behavior from Implementation Plan §8.2 /
§9.4 Stage 1:

    1. Fetch seed URL (depth 0)
    2. Extract all same-domain <a href> links
    3. Filter: same-domain only, skip NON_PRODUCT_PATTERNS, dedup visited set
    4. Fetch each accepted link's content
    5. Repeat up to crawl_depth (default 3)
    6. Rate limit: 500ms delay between requests; respect robots.txt

The link-filtering logic (`is_same_domain`, `matches_non_product_pattern`,
`filter_links`) is pure and synchronous by design — it is the part with the
richest acceptance-criteria surface (OG risk register: "JS-rendered pages
not crawled by httpx" / crawl-depth caps) and the part unit tests exercise
directly, without needing a live HTTP server.
"""

from __future__ import annotations

import asyncio
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from models.catalog_import_job import RawPage


@dataclass
class CrawlResult:
    pages: list[RawPage] = field(default_factory=list)
    pages_crawled: int = 0
    errors: list[str] = field(default_factory=list)


def is_same_domain(seed_url: str, candidate_url: str) -> bool:
    return urlparse(seed_url).netloc == urlparse(candidate_url).netloc


def matches_non_product_pattern(url: str, patterns: tuple[str, ...]) -> bool:
    path = urlparse(url).path.lower()
    return any(pattern in path for pattern in patterns)


def extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        absolute = urljoin(base_url, a["href"])
        # Drop fragments/query noise for dedup purposes, keep the path.
        parsed = urlparse(absolute)
        clean = parsed._replace(fragment="").geturl()
        links.append(clean)
    return links


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.stripped_strings)


def extract_image_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for img in soup.find_all("img", src=True):
        urls.append(urljoin(base_url, img["src"]))
    return urls


def filter_links(
    links: list[str],
    *,
    seed_url: str,
    visited: set[str],
    non_product_patterns: tuple[str, ...],
) -> list[str]:
    """Apply the OG-* acceptance criteria: same-domain, not a non-product
    path, and not already visited. Order-preserving, de-duplicated.
    """
    accepted: list[str] = []
    seen_this_call: set[str] = set()
    for link in links:
        if link in visited or link in seen_this_call:
            continue
        if not is_same_domain(seed_url, link):
            continue
        if matches_non_product_pattern(link, non_product_patterns):
            continue
        accepted.append(link)
        seen_this_call.add(link)
    return accepted


class RobotsCache:
    """Fetches and caches robots.txt per-domain so we only fetch it once per crawl."""

    def __init__(self) -> None:
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    async def is_allowed(self, url: str, user_agent: str, client: httpx.AsyncClient) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._parsers:
            parser = urllib.robotparser.RobotFileParser()
            try:
                resp = await client.get(f"{origin}/robots.txt", timeout=5.0)
                parser.parse(resp.text.splitlines())
            except Exception:
                # No robots.txt / unreachable -> treat as allow-all, per common crawler convention.
                parser.parse([])
            self._parsers[origin] = parser
        return self._parsers[origin].can_fetch(user_agent, url)


class Crawler:
    """Depth-limited, same-domain, robots.txt-respecting product-page crawler."""

    USER_AGENT = "OffGridAI-CatalogImportBot/1.0"

    def __init__(
        self,
        *,
        max_depth: int = 3,
        max_pages: int = 300,
        rate_limit_seconds: float = 0.5,
        non_product_patterns: tuple[str, ...] = (
            "/about",
            "/contact",
            "/blog",
            "/faq",
            "/policy",
        ),
    ) -> None:
        self._max_depth = max_depth
        self._max_pages = max_pages
        self._rate_limit_seconds = rate_limit_seconds
        self._non_product_patterns = non_product_patterns
        self._robots = RobotsCache()

    async def crawl(self, seed_url: str) -> CrawlResult:
        result = CrawlResult()
        visited: set[str] = set()
        frontier: list[tuple[str, int]] = [(seed_url, 0)]

        async with httpx.AsyncClient(
            headers={"User-Agent": self.USER_AGENT}, follow_redirects=True, timeout=15.0
        ) as client:
            while frontier and result.pages_crawled < self._max_pages:
                url, depth = frontier.pop(0)
                if url in visited or depth > self._max_depth:
                    continue
                visited.add(url)

                if not await self._robots.is_allowed(url, self.USER_AGENT, client):
                    result.errors.append(f"robots.txt disallows: {url}")
                    continue

                try:
                    response = await client.get(url)
                    response.raise_for_status()
                except Exception as exc:
                    result.errors.append(f"fetch failed for {url}: {exc}")
                    continue

                html = response.text
                result.pages.append(
                    RawPage(
                        source_url=url,
                        depth=depth,
                        raw_text=extract_text(html),
                        image_urls=extract_image_urls(html, url),
                        input_type="url",
                    )
                )
                result.pages_crawled += 1

                if depth < self._max_depth:
                    links = extract_links(html, url)
                    accepted = filter_links(
                        links,
                        seed_url=seed_url,
                        visited=visited,
                        non_product_patterns=self._non_product_patterns,
                    )
                    frontier.extend((link, depth + 1) for link in accepted)

                await asyncio.sleep(self._rate_limit_seconds)

        return result
