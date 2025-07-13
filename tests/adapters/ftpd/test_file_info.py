"""Tests for FTPD FileInfo class."""

from acb.adapters.ftpd._base import FileInfo


class TestFileInfo:
    def test_file_info_init_defaults(self) -> None:
        file_info = FileInfo("test.txt")

        assert file_info.name == "test.txt"
        assert file_info.size == 0
        assert not file_info.is_dir
        assert file_info.is_file
        assert not file_info.is_symlink
        assert file_info.permissions == ""
        assert file_info.mtime == 0.0
        assert file_info.owner == ""
        assert file_info.group == ""

    def test_file_info_init_custom_values(self) -> None:
        file_info = FileInfo(
            name="document.pdf",
            size=1024,
            permissions="644",
            mtime=1234567890.0,
            owner="user",
            group="staff",
        )

        assert file_info.name == "document.pdf"
        assert file_info.size == 1024
        assert not file_info.is_dir
        assert file_info.is_file
        assert not file_info.is_symlink
        assert file_info.permissions == "644"
        assert file_info.mtime == 1234567890.0
        assert file_info.owner == "user"
        assert file_info.group == "staff"

    def test_file_info_directory(self) -> None:
        file_info = FileInfo(name="mydir", is_dir=True, permissions="755")

        assert file_info.name == "mydir"
        assert file_info.is_dir
        assert not file_info.is_file
        assert file_info.permissions == "755"

    def test_file_info_symlink(self) -> None:
        file_info = FileInfo(name="link.txt", is_symlink=True, permissions="777")

        assert file_info.name == "link.txt"
        assert file_info.is_symlink
        assert file_info.permissions == "777"

    def test_file_info_large_file(self) -> None:
        file_info = FileInfo(
            name="bigfile.bin",
            size=2**31 - 1,  # Max 32-bit signed int
            mtime=1640995200.0,  # 2022-01-01 00:00:00 UTC
        )

        assert file_info.name == "bigfile.bin"
        assert file_info.size == 2**31 - 1
        assert file_info.mtime == 1640995200.0

    def test_file_info_empty_string_values(self) -> None:
        file_info = FileInfo(
            name="",  # Edge case: empty filename
        )

        assert file_info.name == ""
        assert file_info.owner == ""
        assert file_info.group == ""
        assert file_info.permissions == ""

    def test_file_info_special_characters_in_name(self) -> None:
        file_info = FileInfo(name="file with spaces & symbols!@#.txt", size=512)

        assert file_info.name == "file with spaces & symbols!@#.txt"
        assert file_info.size == 512

    def test_file_info_negative_size(self) -> None:
        # Testing edge case - negative size (unusual but should be handled)
        file_info = FileInfo(name="test.txt", size=-1)

        assert file_info.name == "test.txt"
        assert file_info.size == -1

    def test_file_info_zero_mtime(self) -> None:
        file_info = FileInfo(name="test.txt")

        assert file_info.name == "test.txt"
        assert file_info.mtime == 0.0
