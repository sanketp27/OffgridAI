"""tests/unit/test_crawler.py — Catalog Import URL-branch link filtering.

Exercises only the pure, synchronous filtering functions (no live HTTP) --
same-domain check, non-product pattern matching, link extraction, and the
combined `filter_links` acceptance criteria.
"""

from __future__ import annotations

from services.crawler import (
    extract_links,
    filter_links,
    is_same_domain,
    matches_non_product_pattern,
)

NON_PRODUCT_PATTERNS = ("/about", "/contact", "/blog", "/faq", "/policy")


class TestIsSameDomain:
    def test_same_domain_true(self) -> None:
        assert is_same_domain("https://shop.example.com/", "https://shop.example.com/products/1") is True

    def test_different_domain_false(self) -> None:
        assert is_same_domain("https://shop.example.com/", "https://other.com/products/1") is False

    def test_different_subdomain_is_different_domain(self) -> None:
        assert is_same_domain("https://shop.example.com/", "https://blog.example.com/post") is False


class TestMatchesNonProductPattern:
    def test_matches_about_page(self) -> None:
        assert matches_non_product_pattern("https://shop.example.com/about-us", NON_PRODUCT_PATTERNS) is True

    def test_matches_blog_page(self) -> None:
        assert matches_non_product_pattern("https://shop.example.com/blog/post-1", NON_PRODUCT_PATTERNS) is True

    def test_product_page_does_not_match(self) -> None:
        assert matches_non_product_pattern("https://shop.example.com/products/sneaker-1", NON_PRODUCT_PATTERNS) is False


class TestExtractLinks:
    def test_extracts_and_resolves_relative_links(self) -> None:
        html = """
        <html><body>
            <a href="/products/1">Product 1</a>
            <a href="https://shop.example.com/products/2">Product 2</a>
            <a href="/about#team">About</a>
        </body></html>
        """
        links = extract_links(html, base_url="https://shop.example.com/")
        assert "https://shop.example.com/products/1" in links
        assert "https://shop.example.com/products/2" in links
        # Fragment should be stripped
        assert "https://shop.example.com/about" in links
        assert not any("#" in link for link in links)


class TestFilterLinks:
    def test_filters_offsite_and_non_product_and_visited(self) -> None:
        seed = "https://shop.example.com/"
        links = [
            "https://shop.example.com/products/1",
            "https://shop.example.com/about",  # non-product -> excluded
            "https://other-site.com/products/1",  # off-domain -> excluded
            "https://shop.example.com/products/2",
        ]
        visited = {"https://shop.example.com/products/2"}  # already visited -> excluded

        result = filter_links(
            links, seed_url=seed, visited=visited, non_product_patterns=NON_PRODUCT_PATTERNS
        )
        assert result == ["https://shop.example.com/products/1"]

    def test_deduplicates_within_a_single_call(self) -> None:
        seed = "https://shop.example.com/"
        links = [
            "https://shop.example.com/products/1",
            "https://shop.example.com/products/1",
        ]
        result = filter_links(links, seed_url=seed, visited=set(), non_product_patterns=NON_PRODUCT_PATTERNS)
        assert result == ["https://shop.example.com/products/1"]

    def test_empty_input_returns_empty(self) -> None:
        result = filter_links([], seed_url="https://shop.example.com/", visited=set(), non_product_patterns=NON_PRODUCT_PATTERNS)
        assert result == []
