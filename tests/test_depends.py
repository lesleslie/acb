"""Simple tests for the depends module."""

import pytest

from acb.depends import Inject, depends, fast_depends


class SampleService:
    def __init__(self, name: str = "test") -> None:
        self.name = name


@pytest.mark.unit
class TestDepends:
    @pytest.mark.asyncio
    async def test_set_get(self) -> None:
        service = SampleService(name="test_service")
        depends.set(SampleService, service)

        result = await depends.get(SampleService)
        assert result is not None
        assert result is service
        assert result.name == "test_service"

    @pytest.mark.asyncio
    async def test_set_factory(self) -> None:
        def factory() -> SampleService:
            return SampleService(name="factory_service")

        depends.set(SampleService, factory())

        result = await depends.get(SampleService)

        assert isinstance(result, SampleService)
        assert result.name == "factory_service"

    @pytest.mark.asyncio
    async def test_set_async(self) -> None:
        service = SampleService(name="async_service")

        depends.set(SampleService, service)

        result = await depends.get(SampleService)

        assert isinstance(result, SampleService)
        assert result.name == "async_service"

    @pytest.mark.asyncio
    async def test_set_without_instance(self) -> None:
        """Test set method without providing an instance."""
        # This should create a new instance of SampleService
        depends.set(SampleService)

        result = await depends.get(SampleService)
        assert result is not None
        assert isinstance(result, SampleService)

    @pytest.mark.asyncio
    async def test_inject_sync(self) -> None:
        service = SampleService(name="inject_service")
        depends.set(SampleService, service)

        @depends.inject
        def test_function(service: Inject[SampleService]) -> str:
            return service.name

        result = test_function()

        assert result == "inject_service"

    @pytest.mark.asyncio
    async def test_inject_async(self) -> None:
        service = SampleService(name="inject_async_service")
        depends.set(SampleService, service)

        @depends.inject
        async def test_async_function(service: Inject[SampleService]) -> str:
            return service.name

        result = await test_async_function()

        assert result == "inject_async_service"

    @pytest.mark.asyncio
    async def test_inject_with_args(self) -> None:
        service = SampleService(name="inject_args_service")
        depends.set(SampleService, service)

        @depends.inject
        def test_function(
            arg1: str,
            arg2: str,
            service: Inject[SampleService],
        ) -> str:
            return f"{arg1}_{arg2}_{service.name}"

        result = test_function("hello", "world")

        assert result == "hello_world_inject_args_service"

    @pytest.mark.asyncio
    async def test_inject_with_kwargs(self) -> None:
        service = SampleService(name="inject_kwargs_service")
        depends.set(SampleService, service)

        @depends.inject
        def test_function(
            arg1: str,
            arg2: str | None = None,
            service: Inject[SampleService] = None,  # type: ignore[assignment]
        ) -> str:
            return f"{arg1}_{arg2}_{service.name}"

        result = test_function("hello", arg2="world")

        assert result == "hello_world_inject_kwargs_service"

    @pytest.mark.asyncio
    async def test_inject_with_multiple_dependencies(self) -> None:
        service1 = SampleService(name="service1")

        class AnotherService:
            def __init__(self, name: str = "default") -> None:
                self.name = name

        service2 = AnotherService(name="service2")

        depends.set(SampleService, service1)
        depends.set(AnotherService, service2)

        @depends.inject
        def test_function(
            service1: Inject[SampleService],
            service2: Inject[AnotherService],
        ) -> str:
            return f"{service1.name}_{service2.name}"

        result = test_function()

        assert result == "service1_service2"

    @pytest.mark.asyncio
    async def test_get_async(self) -> None:
        service = SampleService(name="async_test_service")
        depends.set(SampleService, service)

        result = await depends.get_async(SampleService)
        assert result is not None
        assert result is service
        assert result.name == "async_test_service"

    def test_call_method(self) -> None:
        # Test that depends can be called as a callable
        result = depends()
        # The result should be a dependency marker from bevy
        assert result is not None

    @pytest.mark.asyncio
    async def test_fast_depends(self) -> None:
        service = SampleService(name="fast_depends_service")
        depends.set(SampleService, service)

        result = await fast_depends(SampleService)
        assert result is not None
        assert result is service
        assert result.name == "fast_depends_service"

    @pytest.mark.asyncio
    async def test_get_with_string_category_raises_runtime_error(self) -> None:
        """Test that getting a string category raises RuntimeError."""
        with pytest.raises(RuntimeError) as exc_info:
            await depends.get("nonexistent_category")

        assert "requires async initialization" in str(exc_info.value)
        assert "Use 'await depends.get_async" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_async_with_cached_string_category(self) -> None:
        """Test get_async with a cached string category."""
        from bevy import get_container

        # Register a string category in the container
        service = SampleService(name="cached_service")
        get_container().add("test_category", service)

        # This should hit the cache path (lines 101-102)
        result = await depends.get_async("test_category")
        assert result is service
        assert result.name == "cached_service"

    def test_get_sync_with_cached_string_category(self) -> None:
        """Test get_sync with a cached string category."""
        from bevy import get_container

        # Register a string category in the container
        service = SampleService(name="sync_cached_service")
        get_container().add("sync_test_category", service)

        # This should hit the cache path (lines 156-157)
        result = depends.get_sync("sync_test_category")
        assert result is service
        assert result.name == "sync_cached_service"

    def test_clear(self) -> None:
        """Test the clear method."""
        service = SampleService(name="clear_test")
        depends.set(SampleService, service)

        # Clear should not raise an error
        depends.clear()
