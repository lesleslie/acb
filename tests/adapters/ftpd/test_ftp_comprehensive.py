"""Comprehensive tests for FTP adapter."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typing as t
from pydantic import SecretStr

from acb.adapters.ftpd._base import FileInfo
from acb.adapters.ftpd.ftp import Ftpd, FtpdSettings
from acb.config import Config


class MockAsyncClient(MagicMock):
    """Mock for FTP Client."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.connect = AsyncMock()
        self.login = AsyncMock()
        self.quit = AsyncMock()
        self.upload = AsyncMock()
        self.download = AsyncMock()
        self.list = MagicMock()
        self.make_directory = AsyncMock()
        self.remove_directory = AsyncMock()
        self.remove_file = AsyncMock()
        self.rename = AsyncMock()
        self.stat = AsyncMock()


class MockServer(MagicMock):
    """Mock for FTP Server."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.start = AsyncMock()
        self.close = AsyncMock()


class TestFTPSettings:
    """Test FTP settings."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for settings testing."""
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app
        mock_config.deployed = False

        # Mock logger to avoid logger config issues
        mock_logger = MagicMock()
        mock_logger.verbose = False
        mock_config.logger = mock_logger

        return mock_config

    def test_default_settings(self, mock_config):
        """Test settings initialization with default values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = FtpdSettings()

        # Test FTP-specific defaults
        assert settings.port == 8021
        assert settings.passive_ports_min == 50000
        assert settings.passive_ports_max == 50100
        assert settings.timeout == 30

        # Test inherited defaults from FtpdBaseSettings
        assert settings.host == "127.0.0.1"
        assert settings.root_dir == "tmp/ftp"
        assert isinstance(settings.username, str)
        assert isinstance(settings.password, SecretStr)

    def test_custom_settings(self, mock_config):
        """Test settings initialization with custom values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = FtpdSettings(
                host="ftp.example.com",
                port=2121,
                username="ftpuser",
                password=SecretStr("ftppass"),
                root_dir="/var/ftp",
                passive_ports_min=60000,
                passive_ports_max=60100,
                timeout=60,
                max_connections=20,
            )

        assert settings.host == "ftp.example.com"
        assert settings.port == 2121
        assert settings.username == "ftpuser"
        assert settings.password.get_secret_value() == "ftppass"
        assert settings.root_dir == "/var/ftp"
        assert settings.passive_ports_min == 60000
        assert settings.passive_ports_max == 60100
        assert settings.timeout == 60
        assert settings.max_connections == 20

    def test_anonymous_settings(self, mock_config):
        """Test anonymous FTP settings."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = FtpdSettings(anonymous=True)

        assert settings.anonymous is True


class TestFTP:
    """Test FTP adapter."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for testing."""
        mock_config = MagicMock(spec=Config)

        # Mock app settings
        mock_app = MagicMock()
        mock_app.name = "testapp"
        mock_config.app = mock_app

        # Mock FTPD settings
        mock_ftpd = MagicMock(spec=FtpdSettings)
        mock_ftpd.host = "127.0.0.1"
        mock_ftpd.port = 8021
        mock_ftpd.username = "ftpuser"
        mock_ftpd.password = SecretStr("ftppass")
        mock_ftpd.root_dir = "/tmp/ftp"
        mock_ftpd.anonymous = False
        mock_ftpd.max_connections = 10
        mock_ftpd.passive_ports_min = 50000
        mock_ftpd.passive_ports_max = 50100
        mock_ftpd.timeout = 30
        mock_config.ftpd = mock_ftpd

        return mock_config

    @pytest.fixture
    def ftp_adapter(self, mock_config):
        """FTP adapter for testing."""
        adapter = Ftpd()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    def test_adapter_initialization(self, ftp_adapter):
        """Test adapter initialization."""
        assert ftp_adapter._client is None
        assert ftp_adapter._path_io is None
        assert hasattr(ftp_adapter, "config")
        assert hasattr(ftp_adapter, "logger")

    def test_server_property(self, ftp_adapter):
        """Test server property creation."""
        with (
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch("acb.adapters.ftpd.ftp.Server", MockServer) as mock_server_class,
        ):
            # Access the server property to trigger the mkdir call
            _ = ftp_adapter.server

            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_server_class.assert_called_once()

            # Check the arguments passed to Server constructor
            call_args = mock_server_class.call_args
            assert call_args is not None
            # The call_args is a tuple of (args, kwargs)
            args, kwargs = call_args
            # Check that users parameter is present
            assert "users" in kwargs
            # Check that there's one user (no anonymous)
            assert len(kwargs["users"]) == 1
            # Check maximum_connections parameter
            assert kwargs["maximum_connections"] == 10
            assert "users" in kwargs
            assert len(kwargs["users"]) == 1  # No anonymous user
            assert kwargs["maximum_connections"] == 10

    def test_server_property_with_anonymous(self, ftp_adapter):
        """Test server property with anonymous access."""
        ftp_adapter.config.ftpd.anonymous = True

        with (
            patch("pathlib.Path.mkdir"),
            patch("acb.adapters.ftpd.ftp.Server", MockServer) as mock_server_class,
        ):
            # Verify server was configured with anonymous user
            call_kwargs = mock_server_class.call_args[1]
            assert len(call_kwargs["users"]) == 2  # Regular + anonymous user

    async def test_start_server(self, ftp_adapter):
        """Test starting FTP server."""
        mock_server = MockServer()

        with (
            patch.object(ftp_adapter, "server", mock_server),
            patch("acb.depends.depends.get", return_value=ftp_adapter.logger),
        ):
            await ftp_adapter.start()

            mock_server.start.assert_called_once()
            ftp_adapter.logger.info.assert_called()

    async def test_start_server_failure(self, ftp_adapter):
        """Test FTP server start failure."""
        mock_server = MockServer()
        mock_server.start.side_effect = Exception("Port already in use")

        with (
            patch.object(ftp_adapter, "server", mock_server),
            patch("acb.depends.depends.get", return_value=ftp_adapter.logger),
        ):
            with pytest.raises(Exception, match="Port already in use"):
                await ftp_adapter.start()

            mock_server.close.assert_called_once()
            ftp_adapter.logger.exception.assert_called()

    async def test_stop_server(self, ftp_adapter):
        """Test stopping FTP server."""
        mock_server = MockServer()

        with (
            patch.object(ftp_adapter, "server", mock_server),
            patch("acb.depends.depends.get", return_value=ftp_adapter.logger),
        ):
            await ftp_adapter.stop()

            mock_server.close.assert_called_once()
            ftp_adapter.logger.info.assert_called()

    async def test_stop_server_failure(self, ftp_adapter):
        """Test FTP server stop failure."""
        mock_server = MockServer()
        mock_server.close.side_effect = Exception("Server error")

        with (
            patch.object(ftp_adapter, "server", mock_server),
            patch("acb.depends.depends.get", return_value=ftp_adapter.logger),
        ):
            with pytest.raises(Exception, match="Server error"):
                await ftp_adapter.stop()

            ftp_adapter.logger.exception.assert_called()

    async def test_ensure_client(self, ftp_adapter):
        """Test client creation and caching."""
        mock_client = MockAsyncClient()

        with patch("acb.adapters.ftpd.ftp.Client", return_value=mock_client):
            client = await ftp_adapter._ensure_client()

            assert ftp_adapter._client == client
            mock_client.connect.assert_called_once_with("127.0.0.1", 8021)
            mock_client.login.assert_called_once_with("ftpuser", "ftppass")

            # Second call should return cached client
            client2 = await ftp_adapter._ensure_client()
            assert client == client2
            assert mock_client.connect.call_count == 1

    async def test_ensure_path_io(self, ftp_adapter):
        """Test AsyncPathIO creation and caching."""
        with patch("acb.adapters.ftpd.ftp.AsyncPathIO") as mock_path_io_class:
            mock_path_io = MagicMock()
            mock_path_io_class.return_value = mock_path_io

            path_io = await ftp_adapter._ensure_path_io()

            assert ftp_adapter._path_io == path_io
            mock_path_io_class.assert_called_once()

            # Second call should return cached path_io
            path_io2 = await ftp_adapter._ensure_path_io()
            assert path_io == path_io2
            assert mock_path_io_class.call_count == 1

    async def test_connect_context_manager(self, ftp_adapter):
        """Test connect context manager."""
        mock_client = MockAsyncClient()

        with patch.object(ftp_adapter, "_ensure_client", return_value=mock_client):
            async with ftp_adapter.connect() as adapter:
                assert adapter == ftp_adapter
                assert ftp_adapter._client == mock_client

            mock_client.quit.assert_called_once()
            assert ftp_adapter._client is None

    async def test_upload_file(self, ftp_adapter):
        """Test file upload."""
        mock_client = MockAsyncClient()
        local_path = Path("/tmp/local_file.txt")
        remote_path = "/remote/file.txt"

        with patch.object(ftp_adapter, "_ensure_client", return_value=mock_client):
            await ftp_adapter.upload(local_path, remote_path)

            mock_client.upload.assert_called_once_with(str(local_path), remote_path)

    async def test_download_file(self, ftp_adapter):
        """Test file download."""
        mock_client = MockAsyncClient()
        remote_path = "/remote/file.txt"
        local_path = Path("/tmp/local_file.txt")

        with patch.object(ftp_adapter, "_ensure_client", return_value=mock_client):
            await ftp_adapter.download(remote_path, local_path)

            mock_client.download.assert_called_once_with(remote_path, str(local_path))

    async def test_list_dir(self, ftp_adapter):
        """Test directory listing."""
        mock_client = MockAsyncClient()

        # Mock the async iterator returned by client.list
        mock_file_data = [
            (
                "file",
                {
                    "name": "file1.txt",
                    "size": 1024,
                    "type": "file",
                    "permissions": "644",
                    "modify": 1640995200.0,
                },
            ),
            ("dir", {"name": "subdir", "type": "dir", "permissions": "755"}),
        ]

        async def mock_list_generator():
            for item in mock_file_data:
                yield item

        mock_client.list.return_value = mock_list_generator()

        with patch.object(ftp_adapter, "_ensure_client", return_value=mock_client):
            files = await ftp_adapter.list_dir("/remote/path")

            assert len(files) == 2

            # Check file info
            file_info = files[0]
            assert file_info.name == "file1.txt"
            assert file_info.size == 1024
            assert file_info.is_file is True
            assert file_info.is_dir is False
            assert file_info.permissions == "644"
            assert file_info.mtime == 1640995200.0

            # Check dir info
            dir_info = files[1]
            assert dir_info.name == "subdir"
            assert dir_info.is_dir is True
            assert dir_info.is_file is False
            assert dir_info.permissions == "755"

    async def test_mkdir(self, ftp_adapter):
        """Test directory creation."""
        mock_client = MockAsyncClient()

        with patch.object(ftp_adapter, "_ensure_client", return_value=mock_client):
            await ftp_adapter.mkdir("/remote/newdir")

            mock_client.make_directory.assert_called_once_with("/remote/newdir")

    async def test_rmdir_simple(self, ftp_adapter):
        """Test simple directory removal."""
        mock_client = MockAsyncClient()

        with patch.object(ftp_adapter, "_ensure_client", return_value=mock_client):
            await ftp_adapter.rmdir("/remote/emptydir")

            mock_client.remove_directory.assert_called_once_with("/remote/emptydir")

    async def test_rmdir_recursive(self, ftp_adapter):
        """Test recursive directory removal."""
        mock_client = MockAsyncClient()

        # Mock directory contents
        mock_files = [
            FileInfo(name="file1.txt", is_file=True, is_dir=False),
            FileInfo(name="subdir", is_file=False, is_dir=True),
        ]

        with (
            patch.object(ftp_adapter, "_ensure_client", return_value=mock_client),
            patch.object(ftp_adapter, "list_dir", return_value=mock_files),
            patch.object(ftp_adapter, "delete", AsyncMock()) as mock_delete,
            patch.object(ftp_adapter, "rmdir", AsyncMock()) as mock_rmdir_recursive,
        ):
            # Avoid infinite recursion by making the recursive call a no-op
            async def side_effect(path, recursive=False):
                if recursive and path != "/remote/testdir":
                    return
                return await ftp_adapter.__class__.rmdir(ftp_adapter, path, recursive)

            mock_rmdir_recursive.side_effect = side_effect

            await ftp_adapter.rmdir("/remote/testdir", recursive=True)

            # Verify files and subdirs were processed
            mock_delete.assert_called()
            mock_rmdir_recursive.assert_called()

    async def test_delete_file(self, ftp_adapter):
        """Test file deletion."""
        mock_client = MockAsyncClient()

        with patch.object(ftp_adapter, "_ensure_client", return_value=mock_client):
            await ftp_adapter.delete("/remote/file.txt")

            mock_client.remove_file.assert_called_once_with("/remote/file.txt")

    async def test_rename_file(self, ftp_adapter):
        """Test file/directory renaming."""
        mock_client = MockAsyncClient()

        with patch.object(ftp_adapter, "_ensure_client", return_value=mock_client):
            await ftp_adapter.rename("/remote/old.txt", "/remote/new.txt")

            mock_client.rename.assert_called_once_with(
                "/remote/old.txt", "/remote/new.txt"
            )

    async def test_exists_true(self, ftp_adapter):
        """Test file exists check (file exists)."""
        mock_file_info = FileInfo(name="test.txt", is_file=True)

        with patch.object(ftp_adapter, "stat", return_value=mock_file_info):
            exists = await ftp_adapter.exists("/remote/test.txt")
            assert exists is True

    async def test_exists_false(self, ftp_adapter):
        """Test file exists check (file doesn't exist)."""
        with patch.object(ftp_adapter, "stat", side_effect=Exception("Not found")):
            exists = await ftp_adapter.exists("/remote/missing.txt")
            assert exists is False

    async def test_stat_file(self, ftp_adapter):
        """Test file stat operation."""
        mock_client = MockAsyncClient()
        mock_stat_result = {
            "size": 2048,
            "type": "file",
            "permissions": "644",
            "modify": 1640995200.0,
            "owner": "user",
            "group": "group",
        }
        mock_client.stat.return_value = mock_stat_result

        with patch.object(ftp_adapter, "_ensure_client", return_value=mock_client):
            file_info = await ftp_adapter.stat("/remote/test.txt")

            assert file_info.name == "test.txt"
            assert file_info.size == 2048
            assert file_info.is_file is True
            assert file_info.is_dir is False
            assert file_info.permissions == "644"
            assert file_info.mtime == 1640995200.0
            assert file_info.owner == "user"
            assert file_info.group == "group"

    async def test_read_text(self, ftp_adapter):
        """Test reading text file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir) / "test.txt"
            test_content = "Hello, FTP!"

            with (
                patch.object(ftp_adapter, "download", AsyncMock()) as mock_download,
                patch("anyio.Path") as mock_async_path_class,
            ):
                mock_async_path = MagicMock()
                mock_async_path.read_text = AsyncMock(return_value=test_content)
                mock_async_path_class.return_value = mock_async_path

                with (
                    patch("tempfile.mkdtemp", return_value=temp_dir),
                    patch("pathlib.Path.exists", return_value=True),
                    patch("pathlib.Path.unlink"),
                    patch("os.rmdir"),
                ):
                    content = await ftp_adapter.read_text("/remote/test.txt")

                    assert content == test_content
                    mock_download.assert_called_once()

    async def test_read_bytes(self, ftp_adapter):
        """Test reading binary file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir) / "test.bin"
            test_content = b"Binary data"

            with (
                patch.object(ftp_adapter, "download", AsyncMock()) as mock_download,
                patch("anyio.Path") as mock_async_path_class,
            ):
                mock_async_path = MagicMock()
                mock_async_path.read_bytes = AsyncMock(return_value=test_content)
                mock_async_path_class.return_value = mock_async_path

                with (
                    patch("tempfile.mkdtemp", return_value=temp_dir),
                    patch("pathlib.Path.exists", return_value=True),
                    patch("pathlib.Path.unlink"),
                    patch("os.rmdir"),
                ):
                    content = await ftp_adapter.read_bytes("/remote/test.bin")

                    assert content == test_content
                    mock_download.assert_called_once()

    async def test_write_text(self, ftp_adapter):
        """Test writing text file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_content = "Hello, FTP!"

            with (
                patch.object(ftp_adapter, "upload", AsyncMock()) as mock_upload,
                patch("anyio.Path") as mock_async_path_class,
            ):
                mock_async_path = MagicMock()
                mock_async_path.write_text = AsyncMock()
                mock_async_path_class.return_value = mock_async_path

                with (
                    patch("tempfile.mkdtemp", return_value=temp_dir),
                    patch("pathlib.Path.exists", return_value=True),
                    patch("pathlib.Path.unlink"),
                    patch("os.rmdir"),
                ):
                    await ftp_adapter.write_text("/remote/test.txt", test_content)

                    mock_async_path.write_text.assert_called_once_with(test_content)
                    mock_upload.assert_called_once()

    async def test_write_bytes(self, ftp_adapter):
        """Test writing binary file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_content = b"Binary data"

            with (
                patch.object(ftp_adapter, "upload", AsyncMock()) as mock_upload,
                patch("anyio.Path") as mock_async_path_class,
            ):
                mock_async_path = MagicMock()
                mock_async_path.write_bytes = AsyncMock()
                mock_async_path_class.return_value = mock_async_path

                with (
                    patch("tempfile.mkdtemp", return_value=temp_dir),
                    patch("pathlib.Path.exists", return_value=True),
                    patch("pathlib.Path.unlink"),
                    patch("os.rmdir"),
                ):
                    await ftp_adapter.write_bytes("/remote/test.bin", test_content)

                    mock_async_path.write_bytes.assert_called_once_with(test_content)
                    mock_upload.assert_called_once()

    def test_module_constants(self):
        """Test module constants."""
        from uuid import UUID

        from acb.adapters import AdapterStatus
        from acb.adapters.ftpd.ftp import MODULE_ID, MODULE_STATUS

        assert isinstance(MODULE_ID, UUID)
        assert MODULE_STATUS == AdapterStatus.STABLE

    def test_depends_registration(self):
        """Test that Ftpd class is registered with dependency injection."""
        from acb.depends import depends

        # This should not raise an exception if properly registered
        ftpd_class = depends.get(Ftpd)
        assert ftpd_class is not None

    def test_inheritance_structure(self):
        """Test that FTP adapter properly inherits from FtpdBase."""
        from acb.adapters.ftpd._base import FtpdBase

        adapter = Ftpd()

        # Test inheritance
        assert isinstance(adapter, FtpdBase)

        # Test that required methods exist
        assert hasattr(adapter, "server")
        assert hasattr(adapter, "start")
        assert hasattr(adapter, "stop")
        assert hasattr(adapter, "connect")
        assert hasattr(adapter, "upload")
        assert hasattr(adapter, "download")

    async def test_comprehensive_workflow(self, ftp_adapter):
        """Test comprehensive FTP workflow."""
        mock_client = MockAsyncClient()
        mock_server = MockServer()

        # Mock file operations
        test_content = "Test file content"
        mock_file_info = FileInfo(
            name="test.txt",
            size=len(test_content),
            is_file=True,
            is_dir=False,
            permissions="644",
            mtime=1640995200.0,
        )

        with (
            patch.object(ftp_adapter, "server", mock_server),
            patch.object(ftp_adapter, "_ensure_client", return_value=mock_client),
            patch("acb.depends.depends.get", return_value=ftp_adapter.logger),
        ):
            # Start server
            await ftp_adapter.start()
            assert mock_server.start.called

            # Connect and perform operations
            async with ftp_adapter.connect():
                # Create directory
                await ftp_adapter.mkdir("/test_dir")
                mock_client.make_directory.assert_called_with("/test_dir")

                # Upload file
                local_path = Path("/tmp/test.txt")
                await ftp_adapter.upload(local_path, "/test_dir/test.txt")
                mock_client.upload.assert_called_with(
                    str(local_path), "/test_dir/test.txt"
                )

                # Verify file exists
                with patch.object(ftp_adapter, "stat", return_value=mock_file_info):
                    exists = await ftp_adapter.exists("/test_dir/test.txt")
                    assert exists is True

                # Download file
                await ftp_adapter.download("/test_dir/test.txt", local_path)
                mock_client.download.assert_called_with(
                    "/test_dir/test.txt", str(local_path)
                )

                # Delete file
                await ftp_adapter.delete("/test_dir/test.txt")
                mock_client.remove_file.assert_called_with("/test_dir/test.txt")

                # Remove directory
                await ftp_adapter.rmdir("/test_dir")
                mock_client.remove_directory.assert_called_with("/test_dir")

            # Client should be disconnected
            mock_client.quit.assert_called_once()
            assert ftp_adapter._client is None

            # Stop server
            await ftp_adapter.stop()
            mock_server.close.assert_called()
