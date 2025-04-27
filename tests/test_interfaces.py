"""Standardized test interfaces for ACB adapters."""

from types import TracebackType
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    Type,
    Union,
)

import pytest


class StorageAdapterProtocol(Protocol):
    async def init(self) -> Any: ...
    async def put_file(self, path: str, content: bytes) -> bool: ...
    async def get_file(self, path: str) -> Optional[bytes]: ...
    async def delete_file(self, path: str) -> bool: ...
    async def file_exists(self, path: str) -> bool: ...
    async def create_directory(self, path: str) -> bool: ...
    async def directory_exists(self, path: str) -> bool: ...


class StorageTestInterface:
    @pytest.mark.asyncio
    async def test_init(self, storage: StorageAdapterProtocol) -> None:
        result = await storage.init()
        assert result is not None

    @pytest.mark.asyncio
    async def test_put_get_file(self, storage: StorageAdapterProtocol) -> None:
        content = b"test content"
        await storage.put_file("test.txt", content)

        result = await storage.get_file("test.txt")

        assert result == content

    @pytest.mark.asyncio
    async def test_put_get_file_with_path(
        self, storage: StorageAdapterProtocol
    ) -> None:
        content = b"test content"
        await storage.put_file("subdir/test.txt", content)

        result = await storage.get_file("subdir/test.txt")

        assert result == content

    @pytest.mark.asyncio
    async def test_get_nonexistent_file(self, storage: StorageAdapterProtocol) -> None:
        result = await storage.get_file("nonexistent.txt")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_file(self, storage: StorageAdapterProtocol) -> None:
        content = b"test content"
        await storage.put_file("test.txt", content)

        result = await storage.delete_file("test.txt")

        assert result

        assert await storage.get_file("test.txt") is None

    @pytest.mark.asyncio
    async def test_file_exists(self, storage: StorageAdapterProtocol) -> None:
        result = await storage.file_exists("test.txt")
        assert not result

        content = b"test content"
        await storage.put_file("test.txt", content)

        result = await storage.file_exists("test.txt")
        assert result

    @pytest.mark.asyncio
    async def test_create_directory(self, storage: StorageAdapterProtocol) -> None:
        result = await storage.create_directory("testdir")

        assert result

        assert await storage.directory_exists("testdir")

    @pytest.mark.asyncio
    async def test_directory_exists(self, storage: StorageAdapterProtocol) -> None:
        result = await storage.directory_exists("testdir")
        assert not result

        await storage.create_directory("testdir")

        result = await storage.directory_exists("testdir")
        assert result


class CacheAdapterProtocol(Protocol):
    async def init(self) -> Any: ...
    async def get(self, key: str, default: Any = None) -> Any: ...
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool: ...
    async def delete(self, key: str) -> Any: ...
    async def exists(self, key: str) -> bool: ...
    async def clear(self, namespace: Optional[str] = None) -> bool: ...


class CacheTestInterface:
    @pytest.mark.asyncio
    async def test_init(self, cache: CacheAdapterProtocol) -> None:
        result = await cache.init()
        assert result is not None

    @pytest.mark.asyncio
    async def test_get(self, cache: CacheAdapterProtocol) -> None:
        await cache.set("test_key", "test_value")

        result = await cache.get("test_key")

        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_set(self, cache: CacheAdapterProtocol) -> None:
        result = await cache.set("test_key", "test_value", ttl=60)

        assert result

        assert await cache.get("test_key") == "test_value"

    @pytest.mark.asyncio
    async def test_delete(self, cache: CacheAdapterProtocol) -> None:
        await cache.set("test_key", "test_value")

        result = await cache.delete("test_key")

        assert result is not None

        assert await cache.get("test_key") is None

    @pytest.mark.asyncio
    async def test_exists(self, cache: CacheAdapterProtocol) -> None:
        result = await cache.exists("test_key")
        assert not result

        await cache.set("test_key", "test_value")

        result = await cache.exists("test_key")
        assert result

    @pytest.mark.asyncio
    async def test_clear(self, cache: CacheAdapterProtocol) -> None:
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        result = await cache.clear()

        assert result

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None


class MockStorage(StorageAdapterProtocol):
    def __init__(self) -> None:
        self._files: Dict[str, bytes] = {}
        self._directories: Set[str] = set()
        self._initialized: bool = False

    async def init(self) -> "MockStorage":
        self._initialized = True
        return self

    async def put_file(self, path: str, content: bytes) -> bool:
        self._files[path] = content

        parts = path.split("/")
        if len(parts) > 1:
            directory = "/".join(parts[:-1])
            self._directories.add(directory)

        return True

    async def get_file(self, path: str) -> Optional[bytes]:
        return self._files.get(path)

    async def delete_file(self, path: str) -> bool:
        if path in self._files:
            del self._files[path]
            return True
        return False

    async def file_exists(self, path: str) -> bool:
        return path in self._files

    async def create_directory(self, path: str) -> bool:
        self._directories.add(path)
        return True

    async def directory_exists(self, path: str) -> bool:
        return path in self._directories


class SQLAdapterProtocol(Protocol):
    async def init(self) -> Any: ...
    async def execute(self, query: str, *args: Any, **kwargs: Any) -> bool: ...
    async def fetch_one(
        self, query: str, *args: Any, **kwargs: Any
    ) -> Optional[Dict[str, Any]]: ...
    async def fetch_all(
        self, query: str, *args: Any, **kwargs: Any
    ) -> List[Dict[str, Any]]: ...
    async def fetch_val(self, query: str, *args: Any, **kwargs: Any) -> Any: ...
    def transaction(self) -> Any: ...


class SQLTestInterface:
    @pytest.mark.asyncio
    async def test_init(self, sql: SQLAdapterProtocol) -> None:
        result = await sql.init()
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute(self, sql: SQLAdapterProtocol) -> None:
        result = await sql.execute("SELECT 1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_fetch_one(self, sql: SQLAdapterProtocol) -> None:
        result = await sql.fetch_one("SELECT 1 as value")
        assert result is not None
        assert result["value"] == 1

    @pytest.mark.asyncio
    async def test_fetch_all(self, sql: SQLAdapterProtocol) -> None:
        result = await sql.fetch_all("SELECT 1 as value UNION SELECT 2 as value")
        assert result is not None
        assert len(result) == 2
        assert result[0]["value"] in (1, 2)
        assert result[1]["value"] in (1, 2)

    @pytest.mark.asyncio
    async def test_fetch_val(self, sql: SQLAdapterProtocol) -> None:
        result = await sql.fetch_val("SELECT 1 as value")
        assert result == 1

    @pytest.mark.asyncio
    async def test_transaction(self, sql: SQLAdapterProtocol) -> None:
        async with sql.transaction():
            result = await sql.execute("SELECT 1")
            assert result is not None


class NoSQLAdapterProtocol(Protocol):
    async def init(self) -> Any: ...
    async def get(self, collection: str, id: str) -> Optional[Dict[str, Any]]: ...
    async def set(self, collection: str, id: str, data: Dict[str, Any]) -> bool: ...
    async def delete(self, collection: str, id: str) -> bool: ...
    async def exists(self, collection: str, id: str) -> bool: ...
    async def find(
        self, collection: str, query: Dict[str, Any]
    ) -> List[Dict[str, Any]]: ...
    async def query(
        self, collection: str, query: Dict[str, Any]
    ) -> List[Dict[str, Any]]: ...


class NoSQLTestInterface:
    @pytest.mark.asyncio
    async def test_init(self, nosql: NoSQLAdapterProtocol) -> None:
        result = await nosql.init()
        assert result is not None

    @pytest.mark.asyncio
    async def test_get(self, nosql: NoSQLAdapterProtocol) -> None:
        await nosql.set("test_collection", "test_id", {"key": "value"})

        result = await nosql.get("test_collection", "test_id")

        assert result is not None
        assert result["key"] == "value"

    @pytest.mark.asyncio
    async def test_set(self, nosql: NoSQLAdapterProtocol) -> None:
        result = await nosql.set("test_collection", "test_id", {"key": "value"})

        assert result

        doc = await nosql.get("test_collection", "test_id")
        assert doc is not None
        assert doc["key"] == "value"

    @pytest.mark.asyncio
    async def test_delete(self, nosql: NoSQLAdapterProtocol) -> None:
        await nosql.set("test_collection", "test_id", {"key": "value"})

        result = await nosql.delete("test_collection", "test_id")

        assert result

        doc = await nosql.get("test_collection", "test_id")
        assert doc is None

    @pytest.mark.asyncio
    async def test_exists(self, nosql: NoSQLAdapterProtocol) -> None:
        result = await nosql.exists("test_collection", "test_id")
        assert not result

        await nosql.set("test_collection", "test_id", {"key": "value"})

        result = await nosql.exists("test_collection", "test_id")
        assert result

    @pytest.mark.asyncio
    async def test_query(self, nosql: NoSQLAdapterProtocol) -> None:
        await nosql.set("test_collection", "id1", {"key": "value1"})
        await nosql.set("test_collection", "id2", {"key": "value2"})

        result = await nosql.query("test_collection", {"key": "value1"})

        assert result is not None
        assert len(result) == 1
        assert result[0]["key"] == "value1"


class RequestsAdapterProtocol(Protocol):
    async def init(self) -> Any: ...
    async def get(self, url: str, **kwargs: Any) -> Any: ...
    async def post(self, url: str, **kwargs: Any) -> Any: ...
    async def put(self, url: str, **kwargs: Any) -> Any: ...
    async def delete(self, url: str, **kwargs: Any) -> Any: ...


class RequestsTestInterface:
    @pytest.mark.asyncio
    async def test_init(self, requests: RequestsAdapterProtocol) -> None:
        result = await requests.init()
        assert result is not None

    @pytest.mark.asyncio
    async def test_get(self, requests: RequestsAdapterProtocol) -> None:
        result = await requests.get("https://example.com")  # nosec B113
        assert result is not None
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_post(self, requests: RequestsAdapterProtocol) -> None:
        result = await requests.post(
            "https://example.com",  # nosec B113
            json={"key": "value"},
        )
        assert result is not None
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_put(self, requests: RequestsAdapterProtocol) -> None:
        result = await requests.put(
            "https://example.com",  # nosec B113
            json={"key": "value"},
        )
        assert result is not None
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_delete(self, requests: RequestsAdapterProtocol) -> None:
        result = await requests.delete("https://example.com")  # nosec B113
        assert result is not None
        assert result.status_code == 200


class SMTPAdapterProtocol(Protocol):
    async def init(self) -> Any: ...
    async def send_email(
        self, to: Union[str, List[str]], subject: str, body: Any, **kwargs: Any
    ) -> bool: ...
    async def send_template(
        self,
        to: Union[str, List[str]],
        template_name: str,
        template_data: Dict[str, Any],
        **kwargs: Any,
    ) -> bool: ...


class SMTPTestInterface:
    @pytest.mark.asyncio
    async def test_init(self, smtp: SMTPAdapterProtocol) -> None:
        result = await smtp.init()
        assert result is not None

    @pytest.mark.asyncio
    async def test_send_email(self, smtp: SMTPAdapterProtocol) -> None:
        result = await smtp.send_email(
            to="recipient@example.com",
            subject="Test Email",
            body="This is a test email.",
        )
        assert result

    @pytest.mark.asyncio
    async def test_send_template(self, smtp: SMTPAdapterProtocol) -> None:
        result = await smtp.send_template(
            to="recipient@example.com",
            template_name="test_template",
            template_data={"name": "Test User"},
        )
        assert result


class SecretAdapterProtocol(Protocol):
    async def init(self) -> Any: ...
    async def get_secret(self, key: str) -> Optional[str]: ...
    async def set_secret(self, key: str, value: str) -> bool: ...
    async def delete_secret(self, key: str) -> bool: ...
    async def secret_exists(self, key: str) -> bool: ...


class SecretTestInterface:
    @pytest.mark.asyncio
    async def test_init(self, secret: SecretAdapterProtocol) -> None:
        result = await secret.init()
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_secret(self, secret: SecretAdapterProtocol) -> None:
        await secret.set_secret("test_secret", "test_value")

        result = await secret.get_secret("test_secret")

        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_set_secret(self, secret: SecretAdapterProtocol) -> None:
        result = await secret.set_secret("test_secret", "test_value")

        assert result

        value = await secret.get_secret("test_secret")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_delete_secret(self, secret: SecretAdapterProtocol) -> None:
        await secret.set_secret("test_secret", "test_value")

        result = await secret.delete_secret("test_secret")

        assert result

        value = await secret.get_secret("test_secret")
        assert value is None


class DNSAdapterProtocol(Protocol):
    async def init(self) -> Any: ...
    async def get_record(self, domain: str, record_type: str) -> Optional[str]: ...
    async def set_record(self, domain: str, record_type: str, value: str) -> bool: ...
    async def delete_record(self, domain: str, record_type: str) -> bool: ...


class DNSTestInterface:
    @pytest.mark.asyncio
    async def test_init(self, dns: DNSAdapterProtocol) -> None:
        result = await dns.init()
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_record(self, dns: DNSAdapterProtocol) -> None:
        await dns.set_record("example.com", "A", "192.0.2.1")

        result = await dns.get_record("example.com", "A")

        assert result == "192.0.2.1"

    @pytest.mark.asyncio
    async def test_set_record(self, dns: DNSAdapterProtocol) -> None:
        result = await dns.set_record("example.com", "A", "192.0.2.1")

        assert result

        value = await dns.get_record("example.com", "A")
        assert value == "192.0.2.1"

    @pytest.mark.asyncio
    async def test_delete_record(self, dns: DNSAdapterProtocol) -> None:
        await dns.set_record("example.com", "A", "192.0.2.1")

        result = await dns.delete_record("example.com", "A")

        assert result

        value = await dns.get_record("example.com", "A")
        assert value is None


class FTPDAdapterProtocol(Protocol):
    async def init(self) -> Any: ...
    async def start_server(self) -> bool: ...
    async def stop_server(self) -> bool: ...
    async def add_user(self, username: str, password: str, home_dir: str) -> bool: ...
    async def remove_user(self, username: str) -> bool: ...


class FTPDTestInterface:
    @pytest.mark.asyncio
    async def test_init(self, ftpd: FTPDAdapterProtocol) -> None:
        result = await ftpd.init()
        assert result is not None

    @pytest.mark.asyncio
    async def test_start_server(self, ftpd: FTPDAdapterProtocol) -> None:
        result = await ftpd.start_server()
        assert result

    @pytest.mark.asyncio
    async def test_stop_server(self, ftpd: FTPDAdapterProtocol) -> None:
        await ftpd.start_server()

        result = await ftpd.stop_server()
        assert result

    @pytest.mark.asyncio
    async def test_add_user(self, ftpd: FTPDAdapterProtocol) -> None:
        result = await ftpd.add_user("testuser", "testpassword", "/home/testuser")
        assert result

    @pytest.mark.asyncio
    async def test_remove_user(self, ftpd: FTPDAdapterProtocol) -> None:
        await ftpd.add_user("testuser", "testpassword", "/home/testuser")

        result = await ftpd.remove_user("testuser")
        assert result


class MonitoringAdapterProtocol(Protocol):
    async def init(self) -> Any: ...
    async def log_event(self, event_name: str, data: Dict[str, Any]) -> bool: ...
    async def log_error(self, error_name: str, data: Dict[str, Any]) -> bool: ...
    async def log_metric(
        self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> bool: ...


class MonitoringTestInterface:
    @pytest.mark.asyncio
    async def test_init(self, monitoring: MonitoringAdapterProtocol) -> None:
        result = await monitoring.init()
        assert result is not None

    @pytest.mark.asyncio
    async def test_log_event(self, monitoring: MonitoringAdapterProtocol) -> None:
        result = await monitoring.log_event("test_event", {"key": "value"})
        assert result

    @pytest.mark.asyncio
    async def test_log_error(self, monitoring: MonitoringAdapterProtocol) -> None:
        result = await monitoring.log_error("test_error", {"key": "value"})
        assert result

    @pytest.mark.asyncio
    async def test_log_metric(self, monitoring: MonitoringAdapterProtocol) -> None:
        result = await monitoring.log_metric("test_metric", 1.0, {"key": "value"})
        assert result


class ModelsAdapterProtocol(Protocol):
    async def init(self) -> Any: ...
    async def create(self, data: Dict[str, Any]) -> str: ...
    async def get(self, id: str) -> Optional[Dict[str, Any]]: ...
    async def update(self, id: str, data: Dict[str, Any]) -> bool: ...
    async def delete(self, id: str) -> bool: ...
    async def find(self, query: Dict[str, Any]) -> List[Dict[str, Any]]: ...


class ModelsTestInterface:
    @pytest.mark.asyncio
    async def test_init(self, models: ModelsAdapterProtocol) -> None:
        result = await models.init()
        assert result is not None

    @pytest.mark.asyncio
    async def test_create(self, models: ModelsAdapterProtocol) -> None:
        result = await models.create({"name": "Test", "value": 1})
        assert result is not None

    @pytest.mark.asyncio
    async def test_get(self, models: ModelsAdapterProtocol) -> None:
        instance_id = await models.create({"name": "Test", "value": 1})

        result = await models.get(instance_id)
        assert result is not None
        assert result["name"] == "Test"
        assert result["value"] == 1

    @pytest.mark.asyncio
    async def test_update(self, models: ModelsAdapterProtocol) -> None:
        instance_id = await models.create({"name": "Test", "value": 1})

        result = await models.update(instance_id, {"value": 2})
        assert result

        updated = await models.get(instance_id)
        assert updated is not None
        assert updated["name"] == "Test"
        assert updated["value"] == 2

    @pytest.mark.asyncio
    async def test_delete(self, models: ModelsAdapterProtocol) -> None:
        instance_id = await models.create({"name": "Test", "value": 1})

        result = await models.delete(instance_id)
        assert result

        result = await models.get(instance_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_query(self, models: ModelsAdapterProtocol) -> None:
        await models.create({"name": "Test1", "value": 1})
        await models.create({"name": "Test2", "value": 2})

        result = await models.find({"value": 1})
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "Test1"
        assert result[0]["value"] == 1


class MockSQL(SQLAdapterProtocol):
    def __init__(self) -> None:
        self._initialized: bool = False
        self._data: Dict[str, Any] = {}

    async def init(self) -> "MockSQL":
        self._initialized = True
        return self

    async def execute(self, query: str, *args: Any, **kwargs: Any) -> bool:
        return True

    async def fetch_one(
        self, query: str, *args: Any, **kwargs: Any
    ) -> Optional[Dict[str, Any]]:
        if "SELECT 1" in query:
            return {"value": 1}
        return None

    async def fetch_all(
        self, query: str, *args: Any, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        if "UNION" in query:
            return [{"value": 1}, {"value": 2}]
        return []

    async def fetch_val(self, query: str, *args: Any, **kwargs: Any) -> Any:
        if "SELECT 1" in query:
            return 1
        return None

    def transaction(self) -> Any:
        class Transaction:
            async def __aenter__(self) -> "Transaction":
                return self

            async def __aexit__(
                self,
                exc_type: Optional[Type[BaseException]],
                exc_val: Optional[BaseException],
                exc_tb: Optional[TracebackType],
            ) -> bool:
                return False

        return Transaction()


class MockNoSQL(NoSQLAdapterProtocol):
    def __init__(self) -> None:
        self._initialized: bool = False
        self._data: Dict[str, Dict[str, Any]] = {}

    async def init(self) -> "MockNoSQL":
        self._initialized = True
        return self

    async def get(self, collection: str, id: str) -> Optional[Dict[str, Any]]:
        key = f"{collection}:{id}"
        return self._data.get(key)

    async def set(self, collection: str, id: str, data: Dict[str, Any]) -> bool:
        key = f"{collection}:{id}"
        self._data[key] = data
        return True

    async def delete(self, collection: str, id: str) -> bool:
        key = f"{collection}:{id}"
        if key in self._data:
            del self._data[key]
            return True
        return False

    async def exists(self, collection: str, id: str) -> bool:
        key = f"{collection}:{id}"
        return key in self._data

    async def query(
        self, collection: str, query: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for key, value in self._data.items():
            if key.startswith(f"{collection}:"):
                match = True
                for k, v in query.items():
                    if k not in value or value[k] != v:
                        match = False
                        break
                if match:
                    results.append(value)
        return results

    async def find(
        self, collection: str, query: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        return await self.query(collection, query)


class MockRequests(RequestsAdapterProtocol):
    def __init__(self) -> None:
        self._initialized: bool = False

    async def init(self) -> "MockRequests":
        self._initialized = True
        return self

    async def get(self, url: str, **kwargs: Any) -> Any:
        return MockResponse(200, {"url": url})

    async def post(self, url: str, **kwargs: Any) -> Any:
        return MockResponse(200, {"url": url, "data": kwargs.get("json")})

    async def put(self, url: str, **kwargs: Any) -> Any:
        return MockResponse(200, {"url": url, "data": kwargs.get("json")})

    async def delete(self, url: str, **kwargs: Any) -> Any:
        return MockResponse(200, {"url": url})


class MockResponse:
    def __init__(self, status_code: int, json_data: Dict[str, Any]) -> None:
        self.status_code: int = status_code
        self._json_data: Dict[str, Any] = json_data

    async def json(self) -> Dict[str, Any]:
        return self._json_data

    async def text(self) -> str:
        return str(self._json_data)

    async def __aenter__(self) -> "MockResponse":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        return False


class MockSMTP(SMTPAdapterProtocol):
    def __init__(self) -> None:
        self._initialized: bool = False
        self._emails: List[Dict[str, Any]] = []

    async def init(self) -> "MockSMTP":
        self._initialized = True
        return self

    async def send_email(
        self, to: Union[str, List[str]], subject: str, body: Any, **kwargs: Any
    ) -> bool:
        self._emails.append({"to": to, "subject": subject, "body": body} | kwargs)
        return True

    async def send_template(
        self,
        to: Union[str, List[str]],
        template_name: str,
        template_data: Dict[str, Any],
        **kwargs: Any,
    ) -> bool:
        self._emails.append(
            {"to": to, "template_name": template_name, "template_data": template_data}
            | kwargs
        )
        return True


class MockSecret(SecretAdapterProtocol):
    def __init__(self) -> None:
        self._initialized: bool = False
        self._secrets: Dict[str, str] = {}

    async def init(self) -> "MockSecret":
        self._initialized = True
        return self

    async def get_secret(self, key: str) -> Optional[str]:
        return self._secrets.get(key)

    async def set_secret(self, key: str, value: str) -> bool:
        self._secrets[key] = value
        return True

    async def delete_secret(self, key: str) -> bool:
        if key in self._secrets:
            del self._secrets[key]
            return True
        return False

    async def secret_exists(self, key: str) -> bool:
        return key in self._secrets


class MockDNS(DNSAdapterProtocol):
    def __init__(self) -> None:
        self._initialized: bool = False
        self._records: Dict[str, str] = {}

    async def init(self) -> "MockDNS":
        self._initialized = True
        return self

    async def get_record(self, domain: str, record_type: str) -> Optional[str]:
        key = f"{domain}:{record_type}"
        return self._records.get(key)

    async def set_record(self, domain: str, record_type: str, value: str) -> bool:
        key = f"{domain}:{record_type}"
        self._records[key] = value
        return True

    async def delete_record(self, domain: str, record_type: str) -> bool:
        key = f"{domain}:{record_type}"
        if key in self._records:
            del self._records[key]
            return True
        return False


class MockFTPD(FTPDAdapterProtocol):
    def __init__(self) -> None:
        self._initialized: bool = False
        self._running: bool = False
        self._users: Dict[str, Dict[str, str]] = {}

    async def init(self) -> "MockFTPD":
        self._initialized = True
        return self

    async def start_server(self) -> bool:
        self._running = True
        return True

    async def stop_server(self) -> bool:
        self._running = False
        return True

    async def add_user(self, username: str, password: str, home_dir: str) -> bool:
        self._users[username] = {"password": password, "home_dir": home_dir}
        return True

    async def remove_user(self, username: str) -> bool:
        if username in self._users:
            del self._users[username]
            return True
        return False


class MockMonitoring(MonitoringAdapterProtocol):
    def __init__(self) -> None:
        self._initialized: bool = False
        self._events: List[Dict[str, Any]] = []
        self._errors: List[Dict[str, Any]] = []
        self._metrics: List[Dict[str, Any]] = []

    async def init(self) -> "MockMonitoring":
        self._initialized = True
        return self

    async def log_event(
        self, event_name: str, data: Optional[Dict[str, Any]] = None
    ) -> bool:
        self._events.append({"name": event_name, "data": data or {}})
        return True

    async def log_error(
        self, error_name: str, data: Optional[Dict[str, Any]] = None
    ) -> bool:
        self._errors.append({"name": error_name, "data": data or {}})
        return True

    async def log_metric(
        self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> bool:
        self._metrics.append({"name": metric_name, "value": value, "tags": tags or {}})
        return True


class MockModels(ModelsAdapterProtocol):
    def __init__(self) -> None:
        self._initialized: bool = False
        self._models: Dict[str, Dict[str, Any]] = {}
        self._next_id: int = 1

    async def init(self) -> "MockModels":
        self._initialized = True
        return self

    async def create(self, data: Dict[str, Any]) -> str:
        model_name = "TestModel"
        if model_name not in self._models:
            self._models[model_name] = {}

        instance_id = str(self._next_id)
        self._next_id += 1

        instance = MockModelInstance(instance_id, **data)
        self._models[model_name][instance_id] = instance

        return instance_id

    async def get(self, id: str) -> Optional[Dict[str, Any]]:
        model_name = "TestModel"
        if model_name not in self._models:
            return None

        instance = self._models[model_name].get(id)
        if instance is None:
            return None

        result = {"id": instance.id}
        for key, value in vars(instance).items():
            if key != "id":
                result[key] = value
        return result

    async def update(self, id: str, data: Dict[str, Any]) -> bool:
        model_name = "TestModel"
        if model_name not in self._models or id not in self._models[model_name]:
            return False

        instance = self._models[model_name][id]

        for key, value in data.items():
            setattr(instance, key, value)

        return True

    async def delete(self, id: str) -> bool:
        model_name = "TestModel"
        if model_name not in self._models or id not in self._models[model_name]:
            return False

        del self._models[model_name][id]
        return True

    async def find(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        model_name = "TestModel"
        if model_name not in self._models:
            return []

        results: List[Dict[str, Any]] = []
        for instance in self._models[model_name].values():
            match = True
            for key, value in query.items():
                if not hasattr(instance, key) or getattr(instance, key) != value:
                    match = False
                    break

            if match:
                result_dict = {"id": instance.id}
                for k, v in vars(instance).items():
                    if k != "id":
                        result_dict[k] = v
                results.append(result_dict)

        return results


class MockModelInstance:
    def __init__(self, id: str, **kwargs: Any) -> None:
        self.id: str = id
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockCache(CacheAdapterProtocol):
    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._initialized: bool = False

    async def init(self) -> "MockCache":
        self._initialized = True
        return self

    async def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        self._data[key] = value
        return True

    async def delete(self, key: str) -> int:
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    async def exists(self, key: str) -> bool:
        return key in self._data

    async def clear(self, namespace: Optional[str] = None) -> bool:
        if namespace:
            keys_to_delete = [
                k for k in self._data.keys() if k.startswith(f"{namespace}:")
            ]
            for key in keys_to_delete:
                del self._data[key]
        else:
            self._data.clear()
        return True

    async def multi_get(self, keys: List[str]) -> List[Any]:
        return [self._data.get(key) for key in keys]

    async def multi_set(
        self, mapping: Dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        for key, value in mapping.items():
            self._data[key] = value
        return True
