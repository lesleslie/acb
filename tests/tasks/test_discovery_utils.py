from pathlib import Path

import pytest

from acb.tasks import discovery as mod
from acb.tasks._base import QueueCapability, QueueMetadata


def _reset_registry() -> None:
    mod._provider_registry.clear()
    mod._provider_overrides.clear()
    mod._initialized = False


def test_register_and_list_providers() -> None:
    _reset_registry()
    mod.register_queue_providers()
    names = set(mod.list_queue_providers())
    assert {"memory", "redis", "rabbitmq"}.issubset(names)


def test_enable_disable_overrides() -> None:
    _reset_registry()
    mod.register_queue_providers()

    mod.enable_queue_provider("default", "redis")
    assert mod.get_queue_provider_override("default") == "redis"

    mod.disable_queue_provider("default")
    assert mod.get_queue_provider_override("default") is None


def test_descriptor_status_missing_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_registry()
    mod.register_queue_providers()

    import importlib.util as util

    real_find_spec = util.find_spec

    def fake_find_spec(name: str, package=None):  # type: ignore[no-redef]
        if name == "redis":
            return None  # Simulate missing redis
        return real_find_spec(name, package)

    monkeypatch.setattr(util, "find_spec", fake_find_spec)

    desc = mod.get_queue_provider_descriptor("redis")
    assert desc.status.name.lower() == "missing_dependencies"
    assert desc.error_message and "redis" in desc.error_message

    # memory has no required packages → available
    memory = mod.get_queue_provider_descriptor("memory")
    assert memory.status.name.lower() == "available"


def test_get_queue_provider_info_unknown() -> None:
    _reset_registry()
    info = mod.get_queue_provider_info("does-not-exist")
    assert info["status"] == mod.QueueProviderStatus.NOT_INSTALLED.value
    assert "not found" in info["error_message"].lower()


def test_list_by_capability_with_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_registry()
    mod.register_queue_providers()

    # Inject metadata for memory provider so capability filter can match
    desc = mod._provider_registry["memory"]
    desc.metadata = QueueMetadata(
        queue_id=mod.generate_provider_id(),
        name=desc.name,
        description="Memory",
        capabilities=[QueueCapability.BASIC_QUEUE],
    )

    names = mod.list_queue_providers_by_capability(QueueCapability.BASIC_QUEUE)
    assert "memory" in names


def test_apply_queue_provider_overrides_file(tmp_path: Path) -> None:
    _reset_registry()
    mod.register_queue_providers()

    cfg = tmp_path / "queues.yaml"
    cfg.write_text(
        """
provider_overrides:
  memory: redis
""".strip()
    )

    mod.apply_queue_provider_overrides(cfg)
    assert mod.get_queue_provider_override("memory") == "redis"
