"""Comprehensive tests for SFTP adapter."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typing as t
from pydantic import SecretStr

from acb.adapters.ftpd._base import FileInfo
from acb.adapters.ftpd.sftp import Ftpd, FtpdSettings
from acb.config import Config


class MockSFTPFileAttr(MagicMock):
    """Mock for SFTP file attributes."""

    def __init__(
        self,
        filename: str,
        size: int = 0,
        is_dir: bool = False,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.filename = filename
        self.size = size
        self._is_dir = is_dir
        self.permissions = 755 if is_dir else 644
        self.mtime = 1640995200.0
        self.uid = 1000
        self.gid = 1000

    def is_dir(self) -> bool:
        return self._is_dir

    def is_file(self) -> bool:
        return not self._is_dir

    def is_symlink(self) -> bool:
        return False


class MockSFTPFile(MagicMock):
    """Mock for SFTP file object."""

    def __init__(self, content: bytes = b"", *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self._content = content
        self.read = AsyncMock(return_value=content)
        self.write = AsyncMock()
        self.__aenter__ = AsyncMock(return_value=self)
        self.__aexit__ = AsyncMock(return_value=None)


class MockSFTPClient(MagicMock):
    """Mock for SFTP Client."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.put = AsyncMock()
        self.get = AsyncMock()
        self.listdir = AsyncMock()
        self.mkdir = AsyncMock()
        self.rmdir = AsyncMock()
        self.remove = AsyncMock()
        self.rename = AsyncMock()
        self.stat = AsyncMock()
        self.open = AsyncMock()
        self.__aexit__ = AsyncMock(return_value=None)


class MockSSHClientConnection(MagicMock):
    """Mock for SSH Client Connection."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.start_sftp_client = AsyncMock()
        self.close = MagicMock()


class MockSSHServerConnection(MagicMock):
    """Mock for SSH Server Connection."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.get_extra_info = MagicMock()
        self.set_extra_info = MagicMock()


class MockSSHAcceptor(MagicMock):
    """Mock for SSH Acceptor."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.close = MagicMock()
        self.wait_closed = AsyncMock()


class MockSSHServerProcess(MagicMock):
    """Mock for SSH Server Process."""

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.exit = MagicMock()


class TestSFTPSettings:
    """Test SFTP settings."""

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

        # Test SFTP-specific defaults
        assert settings.port == 8022
        assert settings.server_host_keys == []
        assert settings.authorized_client_keys is None
        assert settings.known_hosts is None
        assert settings.client_keys == []

        # Test inherited defaults from FtpdBaseSettings
        assert settings.host == "127.0.0.1"
        assert settings.root_dir == "/tmp"
        assert isinstance(settings.username, str)
        assert isinstance(settings.password, SecretStr)

    def test_custom_settings(self, mock_config):
        """Test settings initialization with custom values."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = FtpdSettings(
                host="sftp.example.com",
                port=2222,
                username="sftpuser",
                password=SecretStr("sftppass"),
                root_dir="/var/sftp",
                server_host_keys=["/path/to/host_key"],
                authorized_client_keys="/path/to/authorized_keys",
                known_hosts="/path/to/known_hosts",
                client_keys=["/path/to/client_key"],
                max_connections=20,
            )

        assert settings.host == "sftp.example.com"
        assert settings.port == 2222
        assert settings.username == "sftpuser"
        assert settings.password.get_secret_value() == "sftppass"
        assert settings.root_dir == "/var/sftp"
        assert settings.server_host_keys == ["/path/to/host_key"]
        assert settings.authorized_client_keys == "/path/to/authorized_keys"
        assert settings.known_hosts == "/path/to/known_hosts"
        assert settings.client_keys == ["/path/to/client_key"]
        assert settings.max_connections == 20

    def test_anonymous_settings(self, mock_config):
        """Test anonymous SFTP settings."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            settings = FtpdSettings(anonymous=True)

        assert settings.anonymous is True


class TestSFTP:
    """Test SFTP adapter."""

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
        mock_ftpd.port = 8022
        mock_ftpd.username = "sftpuser"
        mock_ftpd.password = SecretStr("sftppass")
        mock_ftpd.root_dir = "/tmp/sftp"
        mock_ftpd.anonymous = False
        mock_ftpd.max_connections = 10
        mock_ftpd.server_host_keys = ["/path/to/host_key"]
        mock_ftpd.authorized_client_keys = "/path/to/authorized_keys"
        mock_ftpd.known_hosts = "/path/to/known_hosts"
        mock_ftpd.client_keys = ["/path/to/client_key"]
        mock_config.ftpd = mock_ftpd

        return mock_config

    @pytest.fixture
    def sftp_adapter(self, mock_config):
        """SFTP adapter for testing."""
        adapter = Ftpd()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    def test_adapter_initialization(self, sftp_adapter):
        """Test adapter initialization."""
        assert sftp_adapter._server is None
        assert sftp_adapter._client is None
        assert sftp_adapter._sftp_client is None
        assert sftp_adapter._server_task is None
        assert sftp_adapter._server_acceptor is None
        assert hasattr(sftp_adapter, "config")
        assert hasattr(sftp_adapter, "logger")

    def test_server_factory_property(self, sftp_adapter):
        """Test server factory property."""
        from acb.adapters.ftpd.sftp import SFTPHandler

        factory = sftp_adapter.server_factory
        assert factory == SFTPHandler

    async def test_start_server(self, sftp_adapter):
        """Test starting SFTP server."""
        mock_acceptor = MockSSHAcceptor()

        with (
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch(
                "acb.adapters.ftpd.sftp.asyncssh.create_server",
                AsyncMock(return_value=mock_acceptor),
            ) as mock_create_server,
            patch("acb.depends.depends.get", return_value=sftp_adapter.logger),
        ):
            await sftp_adapter.start()

            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_create_server.assert_called_once()

            # Verify server was configured with correct settings
            call_kwargs = mock_create_server.call_args[1]
            assert call_kwargs["server_host_keys"] == ["/path/to/host_key"]
            assert call_kwargs["authorized_client_keys"] == "/path/to/authorized_keys"
            assert call_kwargs["sftp_factory"] == sftp_adapter.server_factory
            assert call_kwargs["encoding"] is None

            assert sftp_adapter._server_acceptor == mock_acceptor
            sftp_adapter.logger.info.assert_called()

    async def test_start_server_failure(self, sftp_adapter):
        """Test SFTP server start failure."""
        with (
            patch("pathlib.Path.mkdir"),
            patch(
                "acb.adapters.ftpd.sftp.asyncssh.create_server",
                AsyncMock(side_effect=OSError("Port already in use")),
            ),
            patch("acb.depends.depends.get", return_value=sftp_adapter.logger),
        ):
            with pytest.raises(OSError, match="Port already in use"):
                await sftp_adapter.start()

            sftp_adapter.logger.exception.assert_called()

    async def test_stop_server(self, sftp_adapter):
        """Test stopping SFTP server."""
        mock_acceptor = MockSSHAcceptor()
        sftp_adapter._server_acceptor = mock_acceptor

        with patch("acb.depends.depends.get", return_value=sftp_adapter.logger):
            await sftp_adapter.stop()

            mock_acceptor.close.assert_called_once()
            mock_acceptor.wait_closed.assert_called_once()
            assert sftp_adapter._server_acceptor is None
            sftp_adapter.logger.info.assert_called()

    async def test_stop_server_no_server(self, sftp_adapter):
        """Test stopping SFTP server when no server exists."""
        with patch("acb.depends.depends.get", return_value=sftp_adapter.logger):
            await sftp_adapter.stop()

            sftp_adapter.logger.info.assert_called()

    async def test_stop_server_failure(self, sftp_adapter):
        """Test SFTP server stop failure."""
        mock_acceptor = MockSSHAcceptor()
        mock_acceptor.close.side_effect = Exception("Server error")
        sftp_adapter._server_acceptor = mock_acceptor

        with patch("acb.depends.depends.get", return_value=sftp_adapter.logger):
            with pytest.raises(Exception, match="Server error"):
                await sftp_adapter.stop()

            sftp_adapter.logger.exception.assert_called()

    async def test_ensure_client(self, sftp_adapter):
        """Test client creation and caching."""
        mock_client = MockSSHClientConnection()
        mock_sftp_client = MockSFTPClient()
        mock_client.start_sftp_client.return_value = mock_sftp_client

        with patch(
            "acb.adapters.ftpd.sftp.asyncssh.connect",
            AsyncMock(return_value=mock_client),
        ) as mock_connect:
            client = await sftp_adapter._ensure_client()

            assert sftp_adapter._client == mock_client
            assert sftp_adapter._sftp_client == mock_sftp_client
            assert client == mock_sftp_client

            # Verify connection parameters
            mock_connect.assert_called_once_with(
                "127.0.0.1",
                8022,
                username="sftpuser",
                password="sftppass",
                known_hosts="/path/to/known_hosts",
                client_keys=["/path/to/client_key"],
                encoding=None,
            )
            mock_client.start_sftp_client.assert_called_once()

            # Second call should return cached client
            client2 = await sftp_adapter._ensure_client()
            assert client == client2
            assert mock_connect.call_count == 1

    async def test_ensure_client_no_client_keys(self, sftp_adapter):
        """Test client creation without client keys."""
        sftp_adapter.config.ftpd.client_keys = []
        mock_client = MockSSHClientConnection()
        mock_sftp_client = MockSFTPClient()
        mock_client.start_sftp_client.return_value = mock_sftp_client

        with patch(
            "acb.adapters.ftpd.sftp.asyncssh.connect",
            AsyncMock(return_value=mock_client),
        ) as mock_connect:
            await sftp_adapter._ensure_client()

            # Verify client_keys is None when empty list
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["client_keys"] is None

    async def test_connect_context_manager(self, sftp_adapter):
        """Test connect context manager."""
        MockSSHClientConnection()
        mock_sftp_client = MockSFTPClient()

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            async with sftp_adapter.connect() as adapter:
                assert adapter == sftp_adapter
                assert sftp_adapter._sftp_client == mock_sftp_client

            # Verify cleanup (client and sftp_client should be None)
            assert sftp_adapter._client is None
            assert sftp_adapter._sftp_client is None

    async def test_connect_context_manager_with_client_cleanup(self, sftp_adapter):
        """Test connect context manager with client cleanup."""
        mock_client = MockSSHClientConnection()
        mock_sftp_client = MockSFTPClient()
        sftp_adapter._client = mock_client

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            async with sftp_adapter.connect():
                pass

            mock_client.close.assert_called_once()

    async def test_upload_file(self, sftp_adapter):
        """Test file upload."""
        mock_sftp_client = MockSFTPClient()
        local_path = Path("/tmp/local_file.txt")
        remote_path = "/remote/file.txt"

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            await sftp_adapter.upload(local_path, remote_path)

            mock_sftp_client.put.assert_called_once_with(str(local_path), remote_path)

    async def test_download_file(self, sftp_adapter):
        """Test file download."""
        mock_sftp_client = MockSFTPClient()
        remote_path = "/remote/file.txt"
        local_path = Path("/tmp/local_file.txt")

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            await sftp_adapter.download(remote_path, local_path)

            mock_sftp_client.get.assert_called_once_with(remote_path, str(local_path))

    async def test_list_dir(self, sftp_adapter):
        """Test directory listing."""
        mock_sftp_client = MockSFTPClient()

        # Mock file attributes
        file_attrs = [
            MockSFTPFileAttr("file1.txt", size=1024, is_dir=False),
            MockSFTPFileAttr("subdir", size=0, is_dir=True),
        ]
        mock_sftp_client.listdir.return_value = file_attrs

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            files = await sftp_adapter.list_dir("/remote/path")

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

    async def test_list_dir_with_string_attrs(self, sftp_adapter):
        """Test directory listing with string file attributes."""
        mock_sftp_client = MockSFTPClient()

        # Mock simple string attributes (fallback case)
        file_attrs = ["file1.txt", "subdir"]
        mock_sftp_client.listdir.return_value = file_attrs

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            files = await sftp_adapter.list_dir("/remote/path")

            assert len(files) == 2
            assert files[0].name == "file1.txt"
            assert files[1].name == "subdir"

    async def test_mkdir(self, sftp_adapter):
        """Test directory creation."""
        mock_sftp_client = MockSFTPClient()

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            await sftp_adapter.mkdir("/remote/newdir")

            mock_sftp_client.mkdir.assert_called_once_with("/remote/newdir")

    async def test_rmdir_simple(self, sftp_adapter):
        """Test simple directory removal."""
        mock_sftp_client = MockSFTPClient()

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            await sftp_adapter.rmdir("/remote/emptydir")

            mock_sftp_client.rmdir.assert_called_once_with("/remote/emptydir")

    async def test_rmdir_recursive(self, sftp_adapter):
        """Test recursive directory removal."""
        mock_sftp_client = MockSFTPClient()

        # Mock directory contents
        mock_files = [
            FileInfo(name="file1.txt", is_file=True, is_dir=False),
            FileInfo(name="subdir", is_file=False, is_dir=True),
        ]

        with (
            patch.object(sftp_adapter, "_ensure_client", return_value=mock_sftp_client),
            patch.object(sftp_adapter, "list_dir", return_value=mock_files),
            patch.object(sftp_adapter, "delete", AsyncMock()) as mock_delete,
            patch.object(sftp_adapter, "rmdir", AsyncMock()) as mock_rmdir_recursive,
        ):
            # Avoid infinite recursion by making the recursive call a no-op
            async def side_effect(path, recursive=False):
                if recursive and path != "/remote/testdir":
                    return
                return await sftp_adapter.__class__.rmdir(sftp_adapter, path, recursive)

            mock_rmdir_recursive.side_effect = side_effect

            await sftp_adapter.rmdir("/remote/testdir", recursive=True)

            # Verify files and subdirs were processed
            mock_delete.assert_called()
            mock_rmdir_recursive.assert_called()

    async def test_delete_file(self, sftp_adapter):
        """Test file deletion."""
        mock_sftp_client = MockSFTPClient()

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            await sftp_adapter.delete("/remote/file.txt")

            mock_sftp_client.remove.assert_called_once_with("/remote/file.txt")

    async def test_rename_file(self, sftp_adapter):
        """Test file/directory renaming."""
        mock_sftp_client = MockSFTPClient()

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            await sftp_adapter.rename("/remote/old.txt", "/remote/new.txt")

            mock_sftp_client.rename.assert_called_once_with(
                "/remote/old.txt", "/remote/new.txt"
            )

    async def test_exists_true(self, sftp_adapter):
        """Test file exists check (file exists)."""
        mock_file_info = FileInfo(name="test.txt", is_file=True)

        with patch.object(sftp_adapter, "stat", return_value=mock_file_info):
            exists = await sftp_adapter.exists("/remote/test.txt")
            assert exists is True

    async def test_exists_false(self, sftp_adapter):
        """Test file exists check (file doesn't exist)."""
        with patch.object(sftp_adapter, "stat", side_effect=Exception("Not found")):
            exists = await sftp_adapter.exists("/remote/missing.txt")
            assert exists is False

    async def test_stat_file(self, sftp_adapter):
        """Test file stat operation."""
        mock_sftp_client = MockSFTPClient()
        mock_file_attr = MockSFTPFileAttr("test.txt", size=2048, is_dir=False)
        mock_sftp_client.stat.return_value = mock_file_attr

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            file_info = await sftp_adapter.stat("/remote/test.txt")

            assert file_info.name == "test.txt"
            assert file_info.size == 2048
            assert file_info.is_file is True
            assert file_info.is_dir is False
            assert file_info.permissions == "644"
            assert file_info.mtime == 1640995200.0
            assert file_info.owner == "1000"
            assert file_info.group == "1000"

    async def test_read_text(self, sftp_adapter):
        """Test reading text file."""
        test_content = "Hello, SFTP!"

        with patch.object(
            sftp_adapter, "read_bytes", AsyncMock(return_value=test_content.encode())
        ):
            content = await sftp_adapter.read_text("/remote/test.txt")

            assert content == test_content

    async def test_read_bytes(self, sftp_adapter):
        """Test reading binary file."""
        mock_sftp_client = MockSFTPClient()
        test_content = b"Binary data"
        mock_file = MockSFTPFile(test_content)
        mock_sftp_client.open.return_value = mock_file

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            content = await sftp_adapter.read_bytes("/remote/test.bin")

            mock_sftp_client.open.assert_called_once_with("/remote/test.bin", "rb")
            mock_file.read.assert_called_once()
            assert content == test_content

    async def test_write_text(self, sftp_adapter):
        """Test writing text file."""
        test_content = "Hello, SFTP!"

        with patch.object(sftp_adapter, "write_bytes", AsyncMock()) as mock_write_bytes:
            await sftp_adapter.write_text("/remote/test.txt", test_content)

            mock_write_bytes.assert_called_once_with(
                "/remote/test.txt", test_content.encode()
            )

    async def test_write_bytes(self, sftp_adapter):
        """Test writing binary file."""
        mock_sftp_client = MockSFTPClient()
        test_content = b"Binary data"
        mock_file = MockSFTPFile()
        mock_sftp_client.open.return_value = mock_file

        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            await sftp_adapter.write_bytes("/remote/test.bin", test_content)

            mock_sftp_client.open.assert_called_once_with("/remote/test.bin", "wb")
            mock_file.write.assert_called_once_with(test_content)

    def test_create_server_connection(self, sftp_adapter):
        """Test server connection creation."""
        server_conn = sftp_adapter._create_server_connection()

        # Test basic attributes
        assert hasattr(server_conn, "config")
        assert server_conn.config == sftp_adapter.config

        # Test authentication methods
        assert server_conn.password_auth_supported() is True
        assert server_conn.begin_auth("sftpuser") is True
        assert server_conn.begin_auth("anonymous") is False  # Not anonymous
        assert server_conn.validate_password("sftpuser", "sftppass") is True
        assert server_conn.validate_password("sftpuser", "wrongpass") is False
        assert server_conn.validate_password("wronguser", "sftppass") is False

    def test_create_server_connection_anonymous(self, sftp_adapter):
        """Test server connection with anonymous access."""
        sftp_adapter.config.ftpd.anonymous = True
        server_conn = sftp_adapter._create_server_connection()

        # Anonymous user should not require authentication
        assert server_conn.begin_auth("anonymous") is False
        assert server_conn.begin_auth("sftpuser") is True

    def test_create_server_connection_made(self, sftp_adapter):
        """Test server connection made callback."""
        server_conn = sftp_adapter._create_server_connection()
        mock_ssh_conn = MockSSHServerConnection()

        server_conn.connection_made(mock_ssh_conn)

        mock_ssh_conn.set_extra_info.assert_called_once_with(ftpd_root_dir="/tmp/sftp")

    def test_process_factory(self, sftp_adapter):
        """Test process factory."""
        mock_process = MockSSHServerProcess()

        sftp_adapter._process_factory(mock_process)

        mock_process.exit.assert_called_once_with(0)

    def test_module_constants(self):
        """Test module constants."""
        from uuid import UUID

        from acb.adapters import AdapterStatus
        from acb.adapters.ftpd.sftp import MODULE_ID, MODULE_STATUS

        assert isinstance(MODULE_ID, UUID)
        assert MODULE_STATUS == AdapterStatus.STABLE

    def test_depends_registration(self):
        """Test that Ftpd class is registered with dependency injection."""
        from acb.depends import depends

        # This should not raise an exception if properly registered
        ftpd_class = depends.get(Ftpd)
        assert ftpd_class is not None

    def test_inheritance_structure(self):
        """Test that SFTP adapter properly inherits from FtpdBase."""
        from acb.adapters.ftpd._base import FtpdBase

        adapter = Ftpd()

        # Test inheritance
        assert isinstance(adapter, FtpdBase)

        # Test that required methods exist
        assert hasattr(adapter, "server_factory")
        assert hasattr(adapter, "start")
        assert hasattr(adapter, "stop")
        assert hasattr(adapter, "connect")
        assert hasattr(adapter, "upload")
        assert hasattr(adapter, "download")

    async def test_comprehensive_workflow(self, sftp_adapter):
        """Test comprehensive SFTP workflow."""
        mock_acceptor = MockSSHAcceptor()
        mock_client = MockSSHClientConnection()
        mock_sftp_client = MockSFTPClient()
        mock_client.start_sftp_client.return_value = mock_sftp_client

        # Mock file operations
        test_content = b"Test file content"
        mock_file_attr = MockSFTPFileAttr(
            "test.txt", size=len(test_content), is_dir=False
        )
        mock_sftp_client.stat.return_value = mock_file_attr

        mock_file = MockSFTPFile(test_content)
        mock_sftp_client.open.return_value = mock_file

        with (
            patch("pathlib.Path.mkdir"),
            patch(
                "acb.adapters.ftpd.sftp.asyncssh.create_server",
                AsyncMock(return_value=mock_acceptor),
            ),
            patch(
                "acb.adapters.ftpd.sftp.asyncssh.connect",
                AsyncMock(return_value=mock_client),
            ),
            patch("acb.depends.depends.get", return_value=sftp_adapter.logger),
        ):
            # Start server
            await sftp_adapter.start()
            assert sftp_adapter._server_acceptor == mock_acceptor

            # Connect and perform operations
            async with sftp_adapter.connect():
                # Create directory
                await sftp_adapter.mkdir("/test_dir")
                mock_sftp_client.mkdir.assert_called_with("/test_dir")

                # Upload file
                local_path = Path("/tmp/test.txt")
                await sftp_adapter.upload(local_path, "/test_dir/test.txt")
                mock_sftp_client.put.assert_called_with(
                    str(local_path), "/test_dir/test.txt"
                )

                # Verify file exists
                exists = await sftp_adapter.exists("/test_dir/test.txt")
                assert exists is True

                # Read file content
                content = await sftp_adapter.read_bytes("/test_dir/test.txt")
                assert content == test_content

                # Write file content
                await sftp_adapter.write_bytes("/test_dir/new_file.txt", b"New content")
                mock_sftp_client.open.assert_called()

                # Download file
                await sftp_adapter.download("/test_dir/test.txt", local_path)
                mock_sftp_client.get.assert_called_with(
                    "/test_dir/test.txt", str(local_path)
                )

                # Delete file
                await sftp_adapter.delete("/test_dir/test.txt")
                mock_sftp_client.remove.assert_called_with("/test_dir/test.txt")

                # Remove directory
                await sftp_adapter.rmdir("/test_dir")
                mock_sftp_client.rmdir.assert_called_with("/test_dir")

            # Client should be disconnected
            mock_client.close.assert_called_once()
            assert sftp_adapter._client is None
            assert sftp_adapter._sftp_client is None

            # Stop server
            await sftp_adapter.stop()
            mock_acceptor.close.assert_called()
            mock_acceptor.wait_closed.assert_called()

            # Verify all operations completed successfully
            sftp_adapter.logger.info.assert_called()

    async def test_sftp_handler_initialization(self, sftp_adapter):
        """Test SFTP handler initialization."""
        from acb.adapters.ftpd.sftp import SFTPHandler

        mock_conn = MockSSHServerConnection()
        mock_conn.get_extra_info.return_value = "/tmp/sftp"

        with patch("acb.adapters.ftpd.sftp.SFTPServer.__init__") as mock_super_init:
            SFTPHandler(mock_conn)

            mock_conn.get_extra_info.assert_called_once_with("ftpd_root_dir")
            mock_super_init.assert_called_once_with(mock_conn, chroot=None)

    async def test_error_handling_in_context_manager(self, sftp_adapter):
        """Test error handling in connect context manager."""
        mock_sftp_client = MockSFTPClient()

        # Test with suppress working correctly
        with patch.object(
            sftp_adapter, "_ensure_client", return_value=mock_sftp_client
        ):
            # Mock an AttributeError during cleanup
            mock_sftp_client.__aexit__.side_effect = AttributeError("No __aexit__")

            async with sftp_adapter.connect():
                pass  # Should not raise despite __aexit__ error

            # Cleanup should still happen
            assert sftp_adapter._client is None
            assert sftp_adapter._sftp_client is None
