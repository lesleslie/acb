"""Tests for DuckDB vector adapter."""

from unittest.mock import MagicMock, patch

import pytest

from acb.adapters.vector.duckdb import Vector, VectorSettings


class TestVectorSettings:
    """Test DuckDB vector adapter settings."""

    @patch("acb.depends.depends.get")
    def test_vector_settings_defaults(self, mock_depends):
        """Test VectorSettings with default values."""
        mock_config = MagicMock()
        mock_depends.return_value = mock_config

        settings = VectorSettings()

        assert settings.database_path == "data/vectors.db"
        assert settings.memory_limit == "2GB"
        assert settings.threads == 4
        assert settings.enable_vss is True

    @patch("acb.depends.depends.get")
    @patch("pathlib.Path.mkdir")
    def test_vector_settings_custom_values(self, mock_mkdir, mock_depends):
        """Test VectorSettings with custom values."""
        mock_config = MagicMock()
        mock_depends.return_value = mock_config

        settings = VectorSettings(
            database_path="/custom/path/vectors.db",
            memory_limit="1GB",
            threads=2,
            enable_vss=False,
        )

        assert settings.database_path == "/custom/path/vectors.db"
        assert settings.memory_limit == "1GB"
        assert settings.threads == 2
        assert settings.enable_vss is False

    @patch("acb.depends.depends.get")
    @patch("pathlib.Path.mkdir")
    def test_vector_settings_creates_directory(self, mock_mkdir, mock_depends):
        """Test that VectorSettings creates database directory."""
        mock_config = MagicMock()
        mock_depends.return_value = mock_config

        VectorSettings(database_path="/custom/path/vectors.db")

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestVector:
    """Test DuckDB Vector adapter."""

    @pytest.fixture
    def mock_config(self, mock_vector_settings):
        """Mock configuration."""
        config = MagicMock()
        config.vector = mock_vector_settings
        return config

    @pytest.fixture
    def vector_adapter(self, mock_config):
        """Vector adapter instance with mocked config."""
        with patch("acb.depends.depends.get", return_value=mock_config):
            adapter = Vector()
            adapter.config = mock_config
            adapter.logger = MagicMock()
            return adapter

    @pytest.mark.asyncio
    async def test_create_client(self, vector_adapter, mock_duckdb_connection):
        """Test _create_client method."""
        with patch("duckdb.connect") as mock_connect:
            mock_connect.return_value = mock_duckdb_connection

            client = await vector_adapter._create_client()

            mock_connect.assert_called_once_with(
                vector_adapter.config.vector.database_path,
                config={
                    "memory_limit": "1GB",
                    "threads": 1,
                },
            )
            assert client == mock_duckdb_connection

    @pytest.mark.asyncio
    async def test_create_client_with_vss(self, vector_adapter, mock_duckdb_connection):
        """Test _create_client method with VSS extension."""
        vector_adapter.config.vector.enable_vss = True

        with patch("duckdb.connect") as mock_connect:
            mock_connect.return_value = mock_duckdb_connection

            await vector_adapter._create_client()

            # Should attempt to install and load VSS extension
            actual_calls = [
                call[0] for call in mock_duckdb_connection.execute.call_args_list
            ]

            assert any("INSTALL vss" in str(call) for call in actual_calls)
            assert any("LOAD vss" in str(call) for call in actual_calls)

    @pytest.mark.asyncio
    async def test_init(self, vector_adapter, mock_duckdb_connection):
        """Test init method."""
        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            await vector_adapter.init()

            # Should create vectors schema
            mock_duckdb_connection.execute.assert_called_with(
                "CREATE SCHEMA IF NOT EXISTS vectors"
            )

    @pytest.mark.asyncio
    async def test_search_empty_table(self, vector_adapter, mock_duckdb_connection):
        """Test search with non-existent table."""
        mock_duckdb_connection.execute.side_effect = Exception("Table not found")

        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            results = await vector_adapter.search(
                "test_collection", [0.1, 0.2, 0.3], limit=10
            )

            assert results == []

    @pytest.mark.asyncio
    async def test_search_with_results(self, vector_adapter, mock_duckdb_connection):
        """Test search with results."""
        # Mock successful query
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("doc1", {"title": "Test Document"}, 0.95),
            ("doc2", {"title": "Another Document"}, 0.85),
        ]
        mock_duckdb_connection.execute.return_value = mock_result

        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            results = await vector_adapter.search(
                "test_collection", [0.1, 0.2, 0.3], limit=10
            )

            assert len(results) == 2
            assert results[0].id == "doc1"
            assert results[0].score == 0.95
            assert results[0].metadata == {"title": "Test Document"}
            assert results[1].id == "doc2"
            assert results[1].score == 0.85

    @pytest.mark.asyncio
    async def test_search_with_filter(self, vector_adapter, mock_duckdb_connection):
        """Test search with filter expression."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("doc1", {"category": "test"}, 0.95)]
        mock_duckdb_connection.execute.return_value = mock_result

        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            await vector_adapter.search(
                "test_collection",
                [0.1, 0.2, 0.3],
                limit=10,
                filter_expr={"category": "test"},
            )

            # Verify filter was applied in query
            query_call = mock_duckdb_connection.execute.call_args[0][0]
            assert "WHERE" in query_call
            assert "category" in query_call

    @pytest.mark.asyncio
    async def test_insert(self, vector_adapter, mock_duckdb_connection, sample_vectors):
        """Test insert method."""
        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            with patch.object(
                vector_adapter, "_ensure_collection_exists", return_value=True
            ):
                ids = await vector_adapter.insert("test_collection", sample_vectors)

                assert len(ids) == 2
                # Verify executemany was called for batch insert
                mock_duckdb_connection.executemany.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert(self, vector_adapter, mock_duckdb_connection, sample_vectors):
        """Test upsert method."""
        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            with patch.object(
                vector_adapter, "_ensure_collection_exists", return_value=True
            ):
                ids = await vector_adapter.upsert("test_collection", sample_vectors)

                assert len(ids) == 2
                # Verify delete and insert were called for each document
                assert (
                    mock_duckdb_connection.execute.call_count >= 4
                )  # 2 deletes + 2 inserts

    @pytest.mark.asyncio
    async def test_delete(self, vector_adapter, mock_duckdb_connection):
        """Test delete method."""
        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            result = await vector_adapter.delete("test_collection", ["doc1", "doc2"])

            assert result is True
            # Verify DELETE query was executed
            delete_call = mock_duckdb_connection.execute.call_args[0][0]
            assert "DELETE FROM" in delete_call
            assert "WHERE id IN" in delete_call

    @pytest.mark.asyncio
    async def test_delete_failure(self, vector_adapter, mock_duckdb_connection):
        """Test delete method with failure."""
        mock_duckdb_connection.execute.side_effect = Exception("Delete failed")

        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            result = await vector_adapter.delete("test_collection", ["doc1"])

            assert result is False

    @pytest.mark.asyncio
    async def test_get(self, vector_adapter, mock_duckdb_connection):
        """Test get method."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("doc1", {"title": "Test"}, [0.1, 0.2, 0.3]),
        ]
        mock_duckdb_connection.execute.return_value = mock_result

        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            documents = await vector_adapter.get(
                "test_collection", ["doc1"], include_vectors=True
            )

            assert len(documents) == 1
            assert documents[0].id == "doc1"
            assert documents[0].metadata == {"title": "Test"}
            assert documents[0].vector == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_count(self, vector_adapter, mock_duckdb_connection):
        """Test count method."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (42,)
        mock_duckdb_connection.execute.return_value = mock_result

        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            count = await vector_adapter.count("test_collection")

            assert count == 42
            # Verify COUNT query was executed
            count_call = mock_duckdb_connection.execute.call_args[0][0]
            assert "SELECT COUNT(*)" in count_call

    @pytest.mark.asyncio
    async def test_count_with_filter(self, vector_adapter, mock_duckdb_connection):
        """Test count method with filter."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (5,)
        mock_duckdb_connection.execute.return_value = mock_result

        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            count = await vector_adapter.count(
                "test_collection", filter_expr={"category": "test"}
            )

            assert count == 5
            # Verify filter was applied in COUNT query
            count_call = mock_duckdb_connection.execute.call_args[0][0]
            assert "WHERE" in count_call

    @pytest.mark.asyncio
    async def test_create_collection(self, vector_adapter, mock_duckdb_connection):
        """Test create_collection method."""
        with patch.object(
            vector_adapter, "_ensure_collection_exists", return_value=True
        ) as mock_ensure:
            result = await vector_adapter.create_collection(
                "test_collection", 3, "cosine"
            )

            assert result is True
            mock_ensure.assert_called_once_with("test_collection", 3, "cosine")

    @pytest.mark.asyncio
    async def test_delete_collection(self, vector_adapter, mock_duckdb_connection):
        """Test delete_collection method."""
        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            result = await vector_adapter.delete_collection("test_collection")

            assert result is True
            # Verify DROP TABLE was executed
            drop_call = mock_duckdb_connection.execute.call_args[0][0]
            assert "DROP TABLE IF EXISTS" in drop_call

    @pytest.mark.asyncio
    async def test_list_collections(self, vector_adapter, mock_duckdb_connection):
        """Test list_collections method."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("collection1",), ("collection2",)]
        mock_duckdb_connection.execute.return_value = mock_result

        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            collections = await vector_adapter.list_collections()

            assert collections == ["collection1", "collection2"]

    @pytest.mark.asyncio
    async def test_ensure_collection_exists(
        self, vector_adapter, mock_duckdb_connection
    ):
        """Test _ensure_collection_exists method."""
        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            result = await vector_adapter._ensure_collection_exists(
                "test_collection", 3
            )

            assert result is True
            # Verify CREATE TABLE was executed
            create_calls = [
                call[0][0] for call in mock_duckdb_connection.execute.call_args_list
            ]
            assert any("CREATE TABLE IF NOT EXISTS" in call for call in create_calls)

    @pytest.mark.asyncio
    async def test_ensure_collection_exists_with_vss(
        self, vector_adapter, mock_duckdb_connection
    ):
        """Test _ensure_collection_exists with VSS extension."""
        vector_adapter.config.vector.enable_vss = True

        # Mock index check to return no existing index
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_duckdb_connection.execute.return_value = mock_result

        with patch.object(
            vector_adapter, "get_client", return_value=mock_duckdb_connection
        ):
            result = await vector_adapter._ensure_collection_exists(
                "test_collection", 3, "cosine"
            )

            assert result is True
            # Verify CREATE INDEX was attempted
            execute_calls = [
                call[0][0] for call in mock_duckdb_connection.execute.call_args_list
            ]
            assert any(
                "CREATE INDEX" in call and "USING HNSW" in call
                for call in execute_calls
            )
