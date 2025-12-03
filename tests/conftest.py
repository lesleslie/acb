"""Configuration for pytest testing framework."""

import asyncio
import pytest
from _pytest.python import Function


def pytest_collection_modifyitems(config: pytest.Config, items: list[Function]) -> None:
    """Modify test items during collection."""
    for item in items:
        # Mark tests that require external services
        if any(
            marker in item.nodeid
            for marker in [
                "mysql",
                "pgsql",
                "neo4j",
                "arangodb",
                "mongodb",
                "firestore",
                "pinecone",
                "qdrant",
                "weaviate",
                "azure",
                "cloudflare",
                "route53",
                "openai",
                "sentence_transformers",
                "langchain",
                "llamaindex",
                "aiormq",  # Messaging services
                "rabbitmq",
                "ftpd",
                "sftp",
                "ftp",
                "smtp",
                "mailgun",
                "gmail",
                "redis",
                "vector",
                "embedding",
                "reasoning",
                "graph",
                "nosql",
                "secret",
                "storage",
                "sql",
            ]
        ):
            # Add external marker to tests that require external services
            item.add_marker(pytest.mark.external)

        # Handle asyncio
        if "asyncio" in item.keywords:
            if (
                not hasattr(item, "fixturenames")
                or "event_loop" not in item.fixturenames
            ):
                item.fixturenames.append("event_loop")


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "integration: mark test as requiring external integration"
    )
    config.addinivalue_line(
        "markers", "external: mark test as requiring external service"
    )
    config.addinivalue_line(
        "markers", "architecture: mark test as checking architecture patterns"
    )
    config.addinivalue_line("markers", "quick: mark test as fast-running")
    config.addinivalue_line(
        "markers", "coverage: mark test as providing unique coverage"
    )


def pytest_runtest_setup(item: Function) -> None:
    """Setup for each test."""
    # Skip integration tests by default unless specifically requested
    if item.get_closest_marker("integration") or item.get_closest_marker("external"):
        if not item.config.getoption("--run-external", default=False):
            pytest.skip(
                "Skipping external integration test. Use --run-external to run."
            )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add command-line options."""
    parser.addoption(
        "--run-external",
        action="store_true",
        default=False,
        help="Run tests that require external services",
    )


# Set up asyncio event loop policy for all tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for all tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """Mock Config for unit testing adapters.

    This mock provides all the config attributes that adapters access.
    """
    from unittest.mock import Mock

    config = Mock()
    config.deployed = False
    config.debug = Mock()
    config.debug.production = False
    config.debug.logger = False
    config.root_path = "/test/path"
    config.app = Mock()
    config.app.name = "test_app"
    config.logger = Mock()
    config.logger.log_level = "INFO"
    config.logger.level_per_module = {}
    return config


@pytest.fixture(autouse=True)
def reset_dependency_container():
    """Reset the dependency container before each test to ensure test isolation."""
    from acb.depends import depends

    # Clear the dependency container to ensure test isolation
    depends.clear()
