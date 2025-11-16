"""Additional tests for the ACB FTPD modules to fix failing tests."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import SecretStr

from acb.adapters.ftpd._base import (
    FileInfo,
    FtpdBaseSettings,
)
from acb.adapters.ftpd.ftp import (
    Ftpd as FtpFtpd,
)
from acb.adapters.ftpd.ftp import (
    FtpdSettings as FtpFtpdSettings,
)
from acb.adapters.ftpd.sftp import (
    Ftpd as SftpFtpd,
)
from acb.adapters.ftpd.sftp import (
    FtpdSettings as SftpFtpdSettings,
)
from acb.config import Config


class TestFtpdBaseSettings:
    """Test the FtpdBaseSettings class."""

    def test_ftpd_base_settings_defaults(self) -> None:
        """Test FtpdBaseSettings default values."""
        settings = FtpdBaseSettings()

        assert settings.host == "127.0.0.1"
        assert settings.port == 8021
        assert settings.max_connections == 42
        assert settings.username == "ftpuser"
        assert settings.password.get_secret_value() == "ftppass"
        assert settings.anonymous is False
        assert settings.root_dir == "tmp/ftp"
        assert settings.use_tls is False
        assert settings.cert_file is None
        assert settings.key_file is None

    def test_ftpd_base_settings_custom_values(self) -> None:
        """Test FtpdBaseSettings with custom values."""
        settings = FtpdBaseSettings(
            host="192.168.1.100",
            port=2121,
            max_connections=100,
            username="customuser",
            password=SecretStr("custompass"),
            anonymous=True,
            root_dir="/custom/ftp",
            use_tls=True,
            cert_file="/path/to/cert.pem",
            key_file="/path/to/key.pem",
        )

        assert settings.host == "192.168.1.100"
        assert settings.port == 2121
        assert settings.max_connections == 100
        assert settings.username == "customuser"
        assert settings.password.get_secret_value() == "custompass"
        assert settings.anonymous is True
        assert settings.root_dir == "/custom/ftp"
        assert settings.use_tls is True
        assert settings.cert_file == "/path/to/cert.pem"
        assert settings.key_file == "/path/to/key.pem"


class TestFileInfo:
    """Test the FileInfo class."""

    def test_file_info_defaults(self) -> None:
        """Test FileInfo default values."""
        info = FileInfo(name="test.txt")

        assert info.name == "test.txt"
        assert info.size == 0
        assert info.is_dir is False
        assert info.is_file is True  # Derived from is_dir=False
        assert info.is_symlink is False
        assert info.permissions == ""
        assert info.mtime == 0.0
        assert info.owner == ""
        assert info.group == ""

    def test_file_info_custom_values(self) -> None:
        """Test FileInfo with custom values."""
        info = FileInfo(
            name="test.txt",
            size=1024,
            is_dir=False,
            is_file=True,
            is_symlink=True,
            permissions="rw-r--r--",
            mtime=1640995200.0,
            owner="testuser",
            group="testgroup",
        )

        assert info.name == "test.txt"
        assert info.size == 1024
        assert info.is_dir is False
        assert info.is_file is True
        assert info.is_symlink is True
        assert info.permissions == "rw-r--r--"
        assert info.mtime == 1640995200.0
        assert info.owner == "testuser"
        assert info.group == "testgroup"

    def test_file_info_directory(self) -> None:
        """Test FileInfo for directory."""
        info = FileInfo(
            name="testdir", size=0, is_dir=True, is_file=False, is_symlink=False
        )

        assert info.name == "testdir"
        assert info.size == 0
        assert info.is_dir is True
        assert info.is_file is False
        assert info.is_symlink is False


class TestFtpFtpdSettings:
    """Test the FTP FtpdSettings class."""

    def test_ftp_ftpd_settings_defaults(self) -> None:
        """Test FTP FtpdSettings default values."""
        settings = FtpFtpdSettings()

        assert settings.port == 8021
        assert settings.passive_ports_min == 50000
        assert settings.passive_ports_max == 50100
        assert settings.timeout == 30
        # Also check inherited values
        assert settings.host == "127.0.0.1"
        assert settings.username == "ftpuser"

    def test_ftp_ftpd_settings_custom_values(self) -> None:
        """Test FTP FtpdSettings with custom values."""
        settings = FtpFtpdSettings(
            port=2121,
            passive_ports_min=51000,
            passive_ports_max=52000,
            timeout=60,
            host="192.168.1.100",
            username="ftpuser2",
        )

        assert settings.port == 2121
        assert settings.passive_ports_min == 51000
        assert settings.passive_ports_max == 52000
        assert settings.timeout == 60
        assert settings.host == "192.168.1.100"
        assert settings.username == "ftpuser2"


class TestSftpFtpdSettings:
    """Test the SFTP FtpdSettings class."""

    def test_sftp_ftpd_settings_defaults(self) -> None:
        """Test SFTP FtpdSettings default values."""
        settings = SftpFtpdSettings()

        assert settings.port == 8022
        assert settings.server_host_keys == []
        assert settings.authorized_client_keys is None
        assert settings.known_hosts is None
        assert settings.client_keys == []
        # Also check inherited values
        assert settings.host == "127.0.0.1"
        assert settings.username == "ftpuser"

    def test_sftp_ftpd_settings_custom_values(self) -> None:
        """Test SFTP FtpdSettings with custom values."""
        settings = SftpFtpdSettings(
            port=2222,
            server_host_keys=["/path/to/host_key"],
            authorized_client_keys="/path/to/authorized_keys",
            known_hosts="/path/to/known_hosts",
            client_keys=["/path/to/client_key"],
            host="192.168.1.100",
            username="sftpuser",
        )

        assert settings.port == 2222
        assert settings.server_host_keys == ["/path/to/host_key"]
        assert settings.authorized_client_keys == "/path/to/authorized_keys"
        assert settings.known_hosts == "/path/to/known_hosts"
        assert settings.client_keys == ["/path/to/client_key"]
        assert settings.host == "192.168.1.100"
        assert settings.username == "sftpuser"


class TestFtpFtpd:
    """Test the FTP Ftpd class."""

    @pytest.fixture
    def mock_config(self) -> Mock:
        """Create a mock config."""
        mock_config = Mock(spec=Config)
        mock_config.ftpd = Mock()
        mock_config.ftpd.host = "127.0.0.1"
        mock_config.ftpd.port = 8021
        mock_config.ftpd.username = "ftpuser"
        mock_config.ftpd.password = SecretStr("ftppass")
        mock_config.ftpd.root_dir = "/tmp/ftp"
        mock_config.ftpd.anonymous = False
        mock_config.ftpd.max_connections = 42
        mock_config.ftpd.passive_ports_min = 50000
        mock_config.ftpd.passive_ports_max = 50100
        mock_config.ftpd.timeout = 30
        return mock_config

    @pytest.fixture
    def ftp_ftpd(self, mock_config: Mock) -> FtpFtpd:
        """Create an FTP Ftpd instance with mock config."""
        ftpd = FtpFtpd()
        ftpd.config = mock_config
        ftpd.logger = Mock()
        return ftpd

    def test_ftp_ftpd_initialization(self, ftp_ftpd: FtpFtpd) -> None:
        """Test FTP Ftpd initialization."""
        assert ftp_ftpd._client is None
        assert ftp_ftpd._path_io is None

    @patch("acb.adapters.ftpd.ftp.Path")
    @patch("acb.adapters.ftpd.ftp.User")
    @patch("acb.adapters.ftpd.ftp.Permission")
    @patch("acb.adapters.ftpd.ftp.Server")
    def test_ftp_ftpd_server_property(
        self,
        mock_server_class: Mock,
        mock_permission_class: Mock,
        mock_user_class: Mock,
        mock_path_class: Mock,
        ftp_ftpd: FtpFtpd,
    ) -> None:
        """Test FTP Ftpd server property."""
        mock_server_instance = Mock()
        mock_server_class.return_value = mock_server_instance

        mock_user_instance = Mock()
        mock_user_class.return_value = mock_user_instance

        mock_permission_instance = Mock()
        mock_permission_class.return_value = mock_permission_instance

        mock_path_instance = Mock()
        mock_path_class.return_value = mock_path_instance

        # Access the server property
        server = ftp_ftpd.server

        # Verify mocks were called with expected arguments
        mock_path_instance.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_user_class.assert_called_once()
        mock_server_class.assert_called_once()

        assert server == mock_server_instance

    @pytest.mark.asyncio
    @patch("acb.adapters.ftpd.ftp.Path")
    @patch("acb.adapters.ftpd.ftp.User")
    @patch("acb.adapters.ftpd.ftp.Permission")
    @patch("acb.adapters.ftpd.ftp.Server")
    async def test_ftp_ftpd_start_success(
        self,
        mock_server_class: Mock,
        mock_permission_class: Mock,
        mock_user_class: Mock,
        mock_path_class: Mock,
        ftp_ftpd: FtpFtpd,
    ) -> None:
        """Test FTP Ftpd start method success."""
        mock_server_instance = AsyncMock()
        mock_server_class.return_value = mock_server_instance

        mock_logger = Mock()

        await ftp_ftpd.start(logger=mock_logger)

        mock_server_instance.start.assert_called_once()
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    @patch("acb.adapters.ftpd.ftp.Path")
    @patch("acb.adapters.ftpd.ftp.User")
    @patch("acb.adapters.ftpd.ftp.Permission")
    @patch("acb.adapters.ftpd.ftp.Server")
    async def test_ftp_ftpd_start_failure(
        self,
        mock_server_class: Mock,
        mock_permission_class: Mock,
        mock_user_class: Mock,
        mock_path_class: Mock,
        ftp_ftpd: FtpFtpd,
    ) -> None:
        """Test FTP Ftpd start method failure."""
        mock_server_instance = AsyncMock()
        mock_server_instance.start = AsyncMock(side_effect=Exception("Start failed"))
        mock_server_instance.close = AsyncMock()
        mock_server_class.return_value = mock_server_instance

        mock_logger = Mock()

        with pytest.raises(Exception, match="Start failed"):
            await ftp_ftpd.start(logger=mock_logger)

        mock_server_instance.start.assert_called_once()
        mock_server_instance.close.assert_called_once()
        mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio
    @patch("acb.adapters.ftpd.ftp.Path")
    @patch("acb.adapters.ftpd.ftp.User")
    @patch("acb.adapters.ftpd.ftp.Permission")
    @patch("acb.adapters.ftpd.ftp.Server")
    async def test_ftp_ftpd_stop_success(
        self,
        mock_server_class: Mock,
        mock_permission_class: Mock,
        mock_user_class: Mock,
        mock_path_class: Mock,
        ftp_ftpd: FtpFtpd,
    ) -> None:
        """Test FTP Ftpd stop method success."""
        mock_server_instance = AsyncMock()
        mock_server_class.return_value = mock_server_instance

        mock_logger = Mock()

        await ftp_ftpd.stop(logger=mock_logger)

        mock_server_instance.close.assert_called_once()
        mock_logger.info.assert_called_once_with("FTP server stopped")

    @pytest.mark.asyncio
    @patch("acb.adapters.ftpd.ftp.Path")
    @patch("acb.adapters.ftpd.ftp.User")
    @patch("acb.adapters.ftpd.ftp.Permission")
    @patch("acb.adapters.ftpd.ftp.Server")
    async def test_ftp_ftpd_stop_failure(
        self,
        mock_server_class: Mock,
        mock_permission_class: Mock,
        mock_user_class: Mock,
        mock_path_class: Mock,
        ftp_ftpd: FtpFtpd,
    ) -> None:
        """Test FTP Ftpd stop method failure."""
        mock_server_instance = AsyncMock()
        mock_server_instance.close = AsyncMock(side_effect=Exception("Stop failed"))
        mock_server_class.return_value = mock_server_instance

        mock_logger = Mock()

        with pytest.raises(Exception, match="Stop failed"):
            await ftp_ftpd.stop(logger=mock_logger)

        mock_server_instance.close.assert_called_once()
        mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_ftp_ftpd_ensure_client(self, ftp_ftpd: FtpFtpd) -> None:
        """Test FTP Ftpd _ensure_client method."""
        with patch("acb.adapters.ftpd.ftp.Client") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value = mock_client_instance

            client = await ftp_ftpd._ensure_client()

            mock_client_class.assert_called_once()
            mock_client_instance.connect.assert_called_once_with(
                ftp_ftpd.config.ftpd.host, ftp_ftpd.config.ftpd.port
            )
            mock_client_instance.login.assert_called_once_with(
                ftp_ftpd.config.ftpd.username,
                ftp_ftpd.config.ftpd.password.get_secret_value(),
            )
            assert client == mock_client_instance

    @pytest.mark.asyncio
    async def test_ftp_ftpd_ensure_client_cached(self, ftp_ftpd: FtpFtpd) -> None:
        """Test FTP Ftpd _ensure_client method with cached client."""
        with patch("acb.adapters.ftpd.ftp.Client") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value = mock_client_instance

            # First call
            client1 = await ftp_ftpd._ensure_client()

            # Second call should return the same client
            client2 = await ftp_ftpd._ensure_client()

            # Client should only be created once
            mock_client_class.assert_called_once()
            assert client1 == client2
            assert ftp_ftpd._client == mock_client_instance

    @pytest.mark.asyncio
    async def test_ftp_ftpd_ensure_path_io(self, ftp_ftpd: FtpFtpd) -> None:
        """Test FTP Ftpd _ensure_path_io method."""
        with patch("acb.adapters.ftpd.ftp.AsyncPathIO") as mock_path_io_class:
            mock_path_io_instance = Mock()
            mock_path_io_class.return_value = mock_path_io_instance

            path_io = await ftp_ftpd._ensure_path_io()

            mock_path_io_class.assert_called_once()
            assert path_io == mock_path_io_instance

    @pytest.mark.asyncio
    async def test_ftp_ftpd_ensure_path_io_cached(self, ftp_ftpd: FtpFtpd) -> None:
        """Test FTP Ftpd _ensure_path_io method with cached instance."""
        with patch("acb.adapters.ftpd.ftp.AsyncPathIO") as mock_path_io_class:
            mock_path_io_instance = Mock()
            mock_path_io_class.return_value = mock_path_io_instance

            # First call
            path_io1 = await ftp_ftpd._ensure_path_io()

            # Second call should return the same instance
            path_io2 = await ftp_ftpd._ensure_path_io()

            # PathIO should only be created once
            mock_path_io_class.assert_called_once()
            assert path_io1 == path_io2
            assert ftp_ftpd._path_io == mock_path_io_instance

    @pytest.mark.asyncio
    async def test_ftp_ftpd_connect_context_manager(self, ftp_ftpd: FtpFtpd) -> None:
        """Test FTP Ftpd connect context manager."""
        with patch("acb.adapters.ftpd.ftp.Client") as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value = mock_client_instance

            async with ftp_ftpd.connect() as adapter:
                assert adapter == ftp_ftpd
                assert ftp_ftpd._client == mock_client_instance

            # After exiting context, client should be None
            mock_client_instance.quit.assert_called_once()
            assert ftp_ftpd._client is None

    @pytest.mark.asyncio
    async def test_ftp_ftpd_upload(self, ftp_ftpd: FtpFtpd) -> None:
        """Test FTP Ftpd upload method."""
        with patch.object(ftp_ftpd, "_ensure_client") as mock_ensure_client:
            mock_client = AsyncMock()
            mock_ensure_client.return_value = mock_client

            local_path = Path("/local/test.txt")
            remote_path = "/remote/test.txt"

            await ftp_ftpd.upload(local_path, remote_path)

            mock_client.upload.assert_called_once_with(str(local_path), remote_path)

    @pytest.mark.asyncio
    async def test_ftp_ftpd_download(self, ftp_ftpd: FtpFtpd) -> None:
        """Test FTP Ftpd download method."""
        with patch.object(ftp_ftpd, "_ensure_client") as mock_ensure_client:
            mock_client = AsyncMock()
            mock_ensure_client.return_value = mock_client

            remote_path = "/remote/test.txt"
            local_path = Path("/local/test.txt")

            await ftp_ftpd.download(remote_path, local_path)

            mock_client.download.assert_called_once_with(remote_path, str(local_path))


class TestSftpFtpd:
    """Test the SFTP Ftpd class."""

    @pytest.fixture
    def mock_config(self) -> Mock:
        """Create a mock config."""
        mock_config = Mock(spec=Config)
        mock_config.ftpd = Mock()
        mock_config.ftpd.host = "127.0.0.1"
        mock_config.ftpd.port = 8022
        mock_config.ftpd.username = "sftpuser"
        mock_config.ftpd.password = SecretStr("sftppass")
        mock_config.ftpd.root_dir = "/tmp/sftp"
        mock_config.ftpd.anonymous = False
        mock_config.ftpd.max_connections = 42
        mock_config.ftpd.server_host_keys = ["/path/to/host_key"]
        mock_config.ftpd.authorized_client_keys = "/path/to/authorized_keys"
        mock_config.ftpd.known_hosts = "/path/to/known_hosts"
        mock_config.ftpd.client_keys = ["/path/to/client_key"]
        return mock_config

    @pytest.fixture
    def sftp_ftpd(self, mock_config: Mock) -> SftpFtpd:
        """Create an SFTP Ftpd instance with mock config."""
        sftpd = SftpFtpd()
        sftpd.config = mock_config
        sftpd.logger = Mock()
        return sftpd

    def test_sftp_ftpd_initialization(self, sftp_ftpd: SftpFtpd) -> None:
        """Test SFTP Ftpd initialization."""
        assert sftp_ftpd._server is None
        assert sftp_ftpd._client is None
        assert sftp_ftpd._sftp_client is None
        assert sftp_ftpd._server_task is None
        assert sftp_ftpd._server_acceptor is None

    @pytest.mark.asyncio
    @patch("acb.adapters.ftpd.sftp.Path")
    @patch("acb.adapters.ftpd.sftp.asyncssh")
    async def test_sftp_ftpd_start_success(
        self, mock_asyncssh: Mock, mock_path_class: Mock, sftp_ftpd: SftpFtpd
    ) -> None:
        """Test SFTP Ftpd start method success."""
        mock_server_acceptor = AsyncMock()
        mock_asyncssh.create_server = AsyncMock(return_value=mock_server_acceptor)

        mock_logger = Mock()

        await sftp_ftpd.start(logger=mock_logger)

        mock_asyncssh.create_server.assert_called_once()
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    @patch("acb.adapters.ftpd.sftp.Path")
    @patch("acb.adapters.ftpd.sftp.asyncssh")
    async def test_sftp_ftpd_start_failure(
        self, mock_asyncssh: Mock, mock_path_class: Mock, sftp_ftpd: SftpFtpd
    ) -> None:
        """Test SFTP Ftpd start method failure."""
        mock_asyncssh.create_server = AsyncMock(side_effect=Exception("Start failed"))
        mock_logger = Mock()

        with pytest.raises(Exception, match="Start failed"):
            await sftp_ftpd.start(logger=mock_logger)

        mock_asyncssh.create_server.assert_called_once()
        mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio
    @patch("acb.adapters.ftpd.sftp.asyncssh")
    async def test_sftp_ftpd_stop_success(
        self, mock_asyncssh: Mock, sftp_ftpd: SftpFtpd
    ) -> None:
        """Test SFTP Ftpd stop method success."""
        sftp_ftpd._server = Mock()
        mock_server_acceptor = Mock()
        mock_server_acceptor.close = Mock()
        mock_server_acceptor.wait_closed = AsyncMock()
        sftp_ftpd._server_acceptor = mock_server_acceptor

        mock_logger = Mock()

        await sftp_ftpd.stop(logger=mock_logger)

        mock_server_acceptor.close.assert_called_once()
        mock_server_acceptor.wait_closed.assert_called_once()
        mock_logger.info.assert_called_once_with("SFTP server stopped")

    @pytest.mark.asyncio
    @patch("acb.adapters.ftpd.sftp.asyncssh")
    async def test_sftp_ftpd_stop_no_server(
        self, mock_asyncssh: Mock, sftp_ftpd: SftpFtpd
    ) -> None:
        """Test SFTP Ftpd stop method when no server exists."""
        sftp_ftpd._server = None
        sftp_ftpd._server_acceptor = None

        mock_logger = Mock()

        await sftp_ftpd.stop(logger=mock_logger)

        mock_logger.info.assert_called_once_with("SFTP server stopped")

    @pytest.mark.asyncio
    @patch("acb.adapters.ftpd.sftp.asyncssh")
    async def test_sftp_ftpd_ensure_client(
        self, mock_asyncssh: Mock, sftp_ftpd: SftpFtpd
    ) -> None:
        """Test SFTP Ftpd _ensure_client method."""
        mock_ssh_client = AsyncMock()
        mock_sftp_client = AsyncMock()
        mock_ssh_client.start_sftp_client = AsyncMock(return_value=mock_sftp_client)

        mock_asyncssh.connect = AsyncMock(return_value=mock_ssh_client)

        sftp_client = await sftp_ftpd._ensure_client()

        mock_asyncssh.connect.assert_called_once_with(
            sftp_ftpd.config.ftpd.host,
            sftp_ftpd.config.ftpd.port,
            username=sftp_ftpd.config.ftpd.username,
            password=sftp_ftpd.config.ftpd.password.get_secret_value(),
            known_hosts=sftp_ftpd.config.ftpd.known_hosts,
            client_keys=sftp_ftpd.config.ftpd.client_keys or None,
            encoding=None,
        )
        mock_ssh_client.start_sftp_client.assert_called_once()
        assert sftp_client == mock_sftp_client
        assert sftp_ftpd._client == mock_ssh_client
        assert sftp_ftpd._sftp_client == mock_sftp_client

    @pytest.mark.asyncio
    @patch("acb.adapters.ftpd.sftp.asyncssh")
    async def test_sftp_ftpd_ensure_client_cached(
        self, mock_asyncssh: Mock, sftp_ftpd: SftpFtpd
    ) -> None:
        """Test SFTP Ftpd _ensure_client method with cached client."""
        mock_ssh_client = AsyncMock()
        mock_sftp_client = AsyncMock()
        mock_ssh_client.start_sftp_client = AsyncMock(return_value=mock_sftp_client)

        mock_asyncssh.connect = AsyncMock(return_value=mock_ssh_client)

        # First call
        sftp_client1 = await sftp_ftpd._ensure_client()

        # Second call should return the same client
        sftp_client2 = await sftp_ftpd._ensure_client()

        # Should only connect once
        mock_asyncssh.connect.assert_called_once()
        assert sftp_client1 == sftp_client2
        assert sftp_ftpd._client == mock_ssh_client
        assert sftp_ftpd._sftp_client == mock_sftp_client

    @pytest.mark.asyncio
    async def test_sftp_ftpd_connect_context_manager(self, sftp_ftpd: SftpFtpd) -> None:
        """Test SFTP Ftpd connect context manager."""
        with patch.object(sftp_ftpd, "_ensure_client") as mock_ensure_client:
            mock_sftp_client = AsyncMock()
            mock_ensure_client.return_value = mock_sftp_client

            async with sftp_ftpd.connect() as adapter:
                assert adapter == sftp_ftpd
                assert sftp_ftpd._sftp_client == mock_sftp_client

            # Check that cleanup happened
            assert sftp_ftpd._sftp_client is None
            assert sftp_ftpd._client is None

    @pytest.mark.asyncio
    async def test_sftp_ftpd_upload(self, sftp_ftpd: SftpFtpd) -> None:
        """Test SFTP Ftpd upload method."""
        with patch.object(sftp_ftpd, "_ensure_client") as mock_ensure_client:
            mock_sftp_client = AsyncMock()
            mock_ensure_client.return_value = mock_sftp_client

            local_path = Path("/local/test.txt")
            remote_path = "/remote/test.txt"

            await sftp_ftpd.upload(local_path, remote_path)

            mock_sftp_client.put.assert_called_once_with(str(local_path), remote_path)

    @pytest.mark.asyncio
    async def test_sftp_ftpd_download(self, sftp_ftpd: SftpFtpd) -> None:
        """Test SFTP Ftpd download method."""
        with patch.object(sftp_ftpd, "_ensure_client") as mock_ensure_client:
            mock_sftp_client = AsyncMock()
            mock_ensure_client.return_value = mock_sftp_client

            remote_path = "/remote/test.txt"
            local_path = Path("/local/test.txt")

            await sftp_ftpd.download(remote_path, local_path)

            mock_sftp_client.get.assert_called_once_with(remote_path, str(local_path))
