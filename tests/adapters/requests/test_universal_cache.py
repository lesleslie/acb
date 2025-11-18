"""Tests for UniversalHTTPCache implementation.

This module tests the universal HTTP caching layer for ACB requests adapters,
including cache key generation, RFC 9111 compliance, serialization, and GraphQL support.
"""

import time
from unittest.mock import AsyncMock

import msgspec
import pytest

from acb.adapters.requests._cache import UniversalHTTPCache


@pytest.fixture
def mock_cache():
    """Create mock cache adapter for testing."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.clear = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def http_cache(mock_cache):
    """Create UniversalHTTPCache instance with mock cache."""
    return UniversalHTTPCache(cache=mock_cache, default_ttl=300)


class TestCacheKeyGeneration:
    """Test cache key generation with various scenarios."""

    def test_basic_key_generation(self, http_cache):
        """Test basic cache key for GET request."""
        key = http_cache._generate_key(
            method="GET",
            url="https://api.example.com/data",
            headers={},
            body=b"",
        )

        # Should be deterministic
        assert key.startswith("acb:http:")
        assert len(key) == 73  # acb:http: + 64 char SHA-256 hex

        # Same input should produce same key
        key2 = http_cache._generate_key(
            method="GET",
            url="https://api.example.com/data",
            headers={},
            body=b"",
        )
        assert key == key2

    def test_different_urls_different_keys(self, http_cache):
        """Different URLs should produce different cache keys."""
        key1 = http_cache._generate_key(
            method="GET", url="https://api.example.com/data1", headers={}, body=b""
        )
        key2 = http_cache._generate_key(
            method="GET", url="https://api.example.com/data2", headers={}, body=b""
        )

        assert key1 != key2

    def test_different_methods_different_keys(self, http_cache):
        """Different HTTP methods should produce different cache keys."""
        key1 = http_cache._generate_key(
            method="GET", url="https://api.example.com/data", headers={}, body=b""
        )
        key2 = http_cache._generate_key(
            method="POST", url="https://api.example.com/data", headers={}, body=b""
        )

        assert key1 != key2

    def test_post_body_included_in_key(self, http_cache):
        """POST request body should be included in cache key (GraphQL support)."""
        key1 = http_cache._generate_key(
            method="POST",
            url="https://api.example.com/graphql",
            headers={},
            body=b'{"query": "{ user(id: 1) { name } }"}',
        )
        key2 = http_cache._generate_key(
            method="POST",
            url="https://api.example.com/graphql",
            headers={},
            body=b'{"query": "{ user(id: 2) { name } }"}',
        )

        # Different bodies should produce different keys
        assert key1 != key2

    def test_get_ignores_body(self, http_cache):
        """GET requests should ignore body in cache key."""
        key1 = http_cache._generate_key(
            method="GET",
            url="https://api.example.com/data",
            headers={},
            body=b"ignored",
        )
        key2 = http_cache._generate_key(
            method="GET", url="https://api.example.com/data", headers={}, body=b""
        )

        # Body should be ignored for GET
        assert key1 == key2

    def test_vary_header_included_in_key(self, http_cache):
        """Vary header values should be included in cache key."""
        key1 = http_cache._generate_key(
            method="GET",
            url="https://api.example.com/data",
            headers={"Vary": "Accept-Language", "Accept-Language": "en-US"},
            body=b"",
        )
        key2 = http_cache._generate_key(
            method="GET",
            url="https://api.example.com/data",
            headers={"Vary": "Accept-Language", "Accept-Language": "fr-FR"},
            body=b"",
        )

        # Different Vary header values should produce different keys
        assert key1 != key2

    def test_vary_header_case_insensitive(self, http_cache):
        """Vary header should be case-insensitive."""
        key1 = http_cache._generate_key(
            method="GET",
            url="https://api.example.com/data",
            headers={"Vary": "Accept-Language", "Accept-Language": "en-US"},
            body=b"",
        )
        key2 = http_cache._generate_key(
            method="GET",
            url="https://api.example.com/data",
            headers={"vary": "Accept-Language", "Accept-Language": "en-US"},
            body=b"",
        )

        # Should produce same key regardless of case
        assert key1 == key2


class TestRFC9111Compliance:
    """Test RFC 9111 HTTP caching compliance."""

    def test_cacheable_get_200(self, http_cache):
        """GET request with 200 status should be cacheable."""
        assert http_cache._is_cacheable(
            method="GET", status=200, headers={"content-type": "application/json"}
        )

    def test_cacheable_head_200(self, http_cache):
        """HEAD request with 200 status should be cacheable."""
        assert http_cache._is_cacheable(
            method="HEAD", status=200, headers={"content-type": "application/json"}
        )

    def test_not_cacheable_post(self, http_cache):
        """POST requests should not be cacheable (not safe method)."""
        assert not http_cache._is_cacheable(
            method="POST", status=200, headers={"content-type": "application/json"}
        )

    def test_not_cacheable_put(self, http_cache):
        """PUT requests should not be cacheable."""
        assert not http_cache._is_cacheable(
            method="PUT", status=200, headers={"content-type": "application/json"}
        )

    def test_not_cacheable_delete(self, http_cache):
        """DELETE requests should not be cacheable."""
        assert not http_cache._is_cacheable(
            method="DELETE", status=200, headers={"content-type": "application/json"}
        )

    def test_cacheable_status_codes(self, http_cache):
        """Test cacheable status codes per RFC 9111."""
        cacheable_statuses = [200, 203, 206, 300, 301, 304, 410]

        for status in cacheable_statuses:
            assert http_cache._is_cacheable(method="GET", status=status, headers={}), (
                f"Status {status} should be cacheable"
            )

    def test_not_cacheable_status_codes(self, http_cache):
        """Test non-cacheable status codes."""
        non_cacheable_statuses = [201, 202, 204, 302, 400, 401, 403, 404, 500, 502]

        for status in non_cacheable_statuses:
            assert not http_cache._is_cacheable(
                method="GET", status=status, headers={}
            ), f"Status {status} should not be cacheable"

    def test_cache_control_no_store(self, http_cache):
        """cache-control: no-store should prevent caching."""
        assert not http_cache._is_cacheable(
            method="GET",
            status=200,
            headers={"Cache-Control": "no-store"},
        )

    def test_cache_control_no_store_lowercase(self, http_cache):
        """cache-control should be case-insensitive."""
        assert not http_cache._is_cacheable(
            method="GET",
            status=200,
            headers={"cache-control": "no-store"},
        )

    def test_cache_control_private(self, http_cache):
        """cache-control: private should prevent caching (shared cache)."""
        assert not http_cache._is_cacheable(
            method="GET",
            status=200,
            headers={"Cache-Control": "private"},
        )

    def test_pragma_no_cache(self, http_cache):
        """Pragma: no-cache should prevent caching (HTTP/1.0)."""
        assert not http_cache._is_cacheable(
            method="GET",
            status=200,
            headers={"Pragma": "no-cache"},
        )

    def test_parse_max_age(self, http_cache):
        """Should parse max-age from cache-control header."""
        ttl = http_cache._parse_cache_control({"Cache-Control": "max-age=600"})
        assert ttl == 600

    def test_parse_max_age_with_other_directives(self, http_cache):
        """Should parse max-age from complex cache-control."""
        ttl = http_cache._parse_cache_control(
            {"Cache-Control": "public, max-age=3600, must-revalidate"}
        )
        assert ttl == 3600

    def test_parse_max_age_missing(self, http_cache):
        """Should return None when max-age is missing."""
        ttl = http_cache._parse_cache_control({"Cache-Control": "public"})
        assert ttl is None

    def test_parse_max_age_invalid(self, http_cache):
        """Should return None for invalid max-age."""
        ttl = http_cache._parse_cache_control({"Cache-Control": "max-age=invalid"})
        assert ttl is None


class TestSerialization:
    """Test msgspec serialization and deserialization."""

    @pytest.mark.asyncio
    async def test_store_and_retrieve_basic(self, http_cache, mock_cache):
        """Test basic store and retrieve cycle."""
        # Store response
        await http_cache.store_response(
            method="GET",
            url="https://api.example.com/data",
            status=200,
            headers={"content-type": "application/json"},
            content=b'{"result": "success"}',
        )

        # Verify cache.set was called
        assert mock_cache.set.called

        # Get the serialized data that was stored
        call_args = mock_cache.set.call_args
        call_args[0][0]
        cached_bytes = call_args[0][1]

        # Verify it's bytes
        assert isinstance(cached_bytes, bytes)

        # Mock cache.get to return the stored data
        mock_cache.get.return_value = cached_bytes

        # Retrieve response
        cached = await http_cache.get_cached_response(
            method="GET",
            url="https://api.example.com/data",
            headers={},
        )

        # Verify deserialization worked
        assert cached is not None
        assert cached["status"] == 200
        assert cached["content"] == b'{"result": "success"}'
        assert cached["headers"]["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_serialization_preserves_data_types(self, http_cache, mock_cache):
        """Test that serialization preserves data types correctly."""
        # Store response with various data types
        await http_cache.store_response(
            method="GET",
            url="https://api.example.com/data",
            status=200,
            headers={
                "content-type": "application/json",
                "x-custom-header": "value",
            },
            content=b"\x00\x01\x02\x03",  # Binary content
        )

        # Get stored data
        cached_bytes = mock_cache.set.call_args[0][1]
        mock_cache.get.return_value = cached_bytes

        # Retrieve and verify
        cached = await http_cache.get_cached_response(
            method="GET",
            url="https://api.example.com/data",
            headers={},
        )

        assert cached["status"] == 200  # int
        assert cached["content"] == b"\x00\x01\x02\x03"  # bytes preserved
        assert isinstance(cached["headers"], dict)  # dict
        assert isinstance(cached["cached_at"], float)  # timestamp


class TestFreshnessValidation:
    """Test cache freshness validation."""

    def test_fresh_response(self, http_cache):
        """Response within max-age should be fresh."""
        cached_data = {
            "cached_at": time.time(),  # Just cached
            "max_age": 300,  # 5 minutes
        }

        assert http_cache._is_fresh(cached_data)

    def test_stale_response(self, http_cache):
        """Response beyond max-age should be stale."""
        cached_data = {
            "cached_at": time.time() - 400,  # Cached 400 seconds ago
            "max_age": 300,  # Max age 5 minutes
        }

        assert not http_cache._is_fresh(cached_data)

    def test_edge_case_exact_max_age(self, http_cache):
        """Response at exactly max-age boundary."""
        now = time.time()
        cached_data = {
            "cached_at": now - 300,  # Exactly 300 seconds ago
            "max_age": 300,
        }

        # Should be stale (age >= max_age)
        assert not http_cache._is_fresh(cached_data)

    @pytest.mark.asyncio
    async def test_stale_response_deleted_on_retrieval(self, http_cache, mock_cache):
        """Stale responses should be deleted when retrieved."""
        # Create stale cached data
        stale_data = msgspec.msgpack.encode(
            {
                "status": 200,
                "headers": {},
                "content": b"old data",
                "cached_at": time.time() - 400,  # 400 seconds ago
                "max_age": 300,  # 5 minute max age
                "url": "https://api.example.com/data",
                "method": "GET",
            }
        )

        mock_cache.get.return_value = stale_data

        # Try to retrieve
        result = await http_cache.get_cached_response(
            method="GET",
            url="https://api.example.com/data",
            headers={},
        )

        # Should return None (stale)
        assert result is None

        # Should have deleted the stale entry
        assert mock_cache.delete.called


class TestGraphQLSupport:
    """Test GraphQL POST body caching."""

    @pytest.mark.asyncio
    async def test_different_graphql_queries_different_cache(
        self, http_cache, mock_cache
    ):
        """Different GraphQL queries should use different cache entries."""
        # Store first query
        query1 = b'{"query": "{ user(id: 1) { name } }"}'
        await http_cache.store_response(
            method="POST",
            url="https://api.example.com/graphql",
            status=200,
            headers={"content-type": "application/json"},
            content=b'{"data": {"user": {"name": "Alice"}}}',
        )

        key1 = http_cache._generate_key(
            method="POST",
            url="https://api.example.com/graphql",
            headers={},
            body=query1,
        )

        # Store second query
        query2 = b'{"query": "{ user(id: 2) { name } }"}'
        key2 = http_cache._generate_key(
            method="POST",
            url="https://api.example.com/graphql",
            headers={},
            body=query2,
        )

        # Keys should be different
        assert key1 != key2

    def test_graphql_body_hash_deterministic(self, http_cache):
        """GraphQL body hashing should be deterministic."""
        query = b'{"query": "{ user(id: 1) { name } }"}'

        key1 = http_cache._generate_key(
            method="POST",
            url="https://api.example.com/graphql",
            headers={},
            body=query,
        )

        key2 = http_cache._generate_key(
            method="POST",
            url="https://api.example.com/graphql",
            headers={},
            body=query,
        )

        # Same body should produce same key
        assert key1 == key2


class TestCacheBackendCompatibility:
    """Test compatibility with different cache backends."""

    @pytest.mark.asyncio
    async def test_works_with_none_cache_response(self, http_cache, mock_cache):
        """Should handle None response from cache backend gracefully."""
        mock_cache.get.return_value = None

        result = await http_cache.get_cached_response(
            method="GET",
            url="https://api.example.com/data",
            headers={},
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_works_with_corrupted_cache_data(self, http_cache, mock_cache):
        """Should handle corrupted cache data gracefully."""
        # Return invalid msgpack data
        mock_cache.get.return_value = b"\x00\x01\x02invalid"

        result = await http_cache.get_cached_response(
            method="GET",
            url="https://api.example.com/data",
            headers={},
        )

        # Should return None (not crash)
        assert result is None

        # Should delete corrupted entry
        assert mock_cache.delete.called

    @pytest.mark.asyncio
    async def test_ttl_passed_to_cache_backend(self, http_cache, mock_cache):
        """Should pass TTL to cache backend."""
        # Store with max-age header
        await http_cache.store_response(
            method="GET",
            url="https://api.example.com/data",
            status=200,
            headers={"Cache-Control": "max-age=600"},
            content=b"data",
        )

        # Verify TTL was passed to cache.set
        call_args = mock_cache.set.call_args
        assert call_args[1]["ttl"] == 600

    @pytest.mark.asyncio
    async def test_default_ttl_used_when_no_max_age(self, http_cache, mock_cache):
        """Should use default TTL when server doesn't specify max-age."""
        # Store without cache-control
        await http_cache.store_response(
            method="GET",
            url="https://api.example.com/data",
            status=200,
            headers={},
            content=b"data",
        )

        # Verify default TTL was used
        call_args = mock_cache.set.call_args
        assert call_args[1]["ttl"] == 300  # default_ttl from fixture


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_headers(self, http_cache, mock_cache):
        """Should handle empty headers dict."""
        await http_cache.store_response(
            method="GET",
            url="https://api.example.com/data",
            status=200,
            headers={},
            content=b"data",
        )

        # Should not crash
        assert mock_cache.set.called

    @pytest.mark.asyncio
    async def test_empty_content(self, http_cache, mock_cache):
        """Should handle empty response content."""
        await http_cache.store_response(
            method="GET",
            url="https://api.example.com/data",
            status=200,
            headers={"content-length": "0"},
            content=b"",
        )

        cached_bytes = mock_cache.set.call_args[0][1]
        mock_cache.get.return_value = cached_bytes

        result = await http_cache.get_cached_response(
            method="GET",
            url="https://api.example.com/data",
            headers={},
        )

        assert result["content"] == b""

    @pytest.mark.asyncio
    async def test_no_store_not_cached(self, http_cache, mock_cache):
        """Responses with no-store should not be cached."""
        await http_cache.store_response(
            method="GET",
            url="https://api.example.com/data",
            status=200,
            headers={"Cache-Control": "no-store"},
            content=b"sensitive data",
        )

        # Should not have called cache.set
        assert not mock_cache.set.called
