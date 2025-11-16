"""Unit tests for adapter metadata utilities.

Covers metadata extraction, capability listing, version compatibility,
and testing-mode behavior for `import_adapter`.
"""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from typing import Any

from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
    extract_metadata_from_class,
    generate_adapter_id,
    generate_adapter_report,
    get_adapter_info,
    import_adapter,
    list_adapter_capabilities,
    validate_version_compatibility,
)


class _DummyAdapter:
    """Adapter class with attached module metadata for testing."""


_DUMMY_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="Dummy Adapter",
    category="example",
    provider="acme",
    version="1.2.3",
    acb_min_version="0.10.0",
    acb_max_version=None,
    author="Unit Tester",
    created_date="2024-10-10",
    last_modified="2025-01-01",
    status=AdapterStatus.BETA,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.BATCHING,
    ],
    required_packages=["example-lib>=1.0"],
    optional_packages={"nice-to-have": "optional-lib"},
    description="A dummy adapter used for metadata tests",
    settings_class="ExampleSettings",
    config_example={"opt": True},
)

# Attach to class in the way adapters/__init__.py expects
setattr(_DummyAdapter, "__module_metadata__", _DUMMY_METADATA)


@pytest.mark.unit
def test_extract_metadata_from_class() -> None:
    m = extract_metadata_from_class(_DummyAdapter)
    assert m is not None
    assert m.name == "Dummy Adapter"
    assert AdapterCapability.ASYNC_OPERATIONS in m.capabilities


@pytest.mark.unit
def test_get_adapter_info_and_capabilities() -> None:
    info = get_adapter_info(_DummyAdapter)
    assert info["has_metadata"] is True
    assert info["name"] == "Dummy Adapter"
    assert info["provider"] == "acme"
    caps = list_adapter_capabilities(_DummyAdapter)
    # Ensure capability values are strings
    assert "async_operations" in caps and "batching" in caps


@pytest.mark.unit
def test_generate_adapter_report_contains_fields() -> None:
    report = generate_adapter_report(_DummyAdapter)
    assert "Adapter Report: Dummy Adapter" in report
    assert re.search(r"Capabilities \(\d+\):", report)
    assert "Dependencies (1):" in report


@pytest.mark.unit
def test_validate_version_compatibility_ranges() -> None:
    # current < min -> False
    assert not validate_version_compatibility(_DUMMY_METADATA, "0.9.9")
    # current >= min -> True
    assert validate_version_compatibility(_DUMMY_METADATA, "0.10.0")

    # With explicit max
    with_max = _DUMMY_METADATA.model_copy(update={"acb_max_version": "9.9.9"})
    assert validate_version_compatibility(with_max, "9.0.0")
    assert not validate_version_compatibility(with_max, "10.0.0")


@pytest.mark.unit
def test_generate_adapter_id_uuid() -> None:
    uid = generate_adapter_id()
    assert isinstance(uid, UUID)


@pytest.mark.unit
def test_import_adapter_testing_mode_fallback_returns_mock() -> None:
    # Nonexistent category should fall back to testing-mode mock under pytest
    obj: Any = import_adapter("totally_nonexistent_category")
    from unittest.mock import MagicMock

    # Some paths return a single MagicMock, others a 1-tuple of MagicMock
    if isinstance(obj, tuple):
        assert len(obj) == 1
        assert isinstance(obj[0], MagicMock)
    else:
        assert isinstance(obj, MagicMock)
