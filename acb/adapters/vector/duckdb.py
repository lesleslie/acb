from pathlib import Path
from uuid import UUID, uuid4

import typing as t

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import VectorBase, VectorBaseSettings, VectorDocument, VectorSearchResult

MODULE_ID = UUID("0197ff50-1234-7890-abcd-ef0123456789")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="DuckDB Vector Search",
    category="vector",
    provider="duckdb",
    version="1.0.0",
    acb_min_version="0.19.1",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-21",
    last_modified="2025-01-21",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.SCHEMA_VALIDATION,
    ],
    required_packages=["duckdb>=0.10.2"],
    description="DuckDB-based vector adapter with VSS extension for local development",
    settings_class="VectorSettings",
    config_example={
        "database_path": "data/vectors.db",
        "default_dimension": 1536,
        "default_distance_metric": "cosine",
    },
)


class VectorSettings(VectorBaseSettings):
    """DuckDB vector adapter settings."""

    database_path: str = "data/vectors.db"
    memory_limit: str = "2GB"
    threads: int = 4
    enable_vss: bool = True


class Vector(VectorBase):
    """DuckDB vector adapter implementation."""

    async def _create_client(self) -> t.Any:
        """Create DuckDB connection with VSS extension."""
        import duckdb

        # Ensure database directory exists before creating connection
        db_path = self.config.vector.database_path
        if db_path != ":memory:" and ("/" in db_path or "\\" in db_path):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = duckdb.connect(
            db_path,
            config={
                "memory_limit": self.config.vector.memory_limit,
                "threads": self.config.vector.threads,
            },
        )

        if self.config.vector.enable_vss:
            try:
                conn.execute("INSTALL vss")
                conn.execute("LOAD vss")
                self.logger.debug("VSS extension loaded successfully")
            except Exception as e:
                self.logger.warning(f"Failed to load VSS extension: {e}")
                self.logger.info("Continuing without VSS extension")

        return conn

    async def init(self) -> None:
        """Initialize DuckDB vector adapter."""
        self.logger.info("Initializing DuckDB vector adapter")
        client = await self.get_client()

        # Create base schema
        client.execute("CREATE SCHEMA IF NOT EXISTS vectors")

        self.logger.info("DuckDB vector adapter initialized successfully")

    def _validate_collection_name(self, collection: str) -> str:
        """Validate and sanitize collection name to prevent SQL injection."""
        if not isinstance(collection, str):
            msg = "Collection name must be a string"
            raise ValueError(msg)

        # Use simple alphanumeric validation with underscores and hyphens
        import string

        valid_chars = set(string.ascii_letters + string.digits + "_-")
        if not all(c in valid_chars for c in collection):
            msg = f"Invalid collection name: {collection}. Only alphanumeric characters, underscores, and hyphens allowed."
            raise ValueError(msg)

        if len(collection) > 63:  # PostgreSQL limit
            msg = f"Collection name too long: {collection}. Maximum 63 characters allowed."
            raise ValueError(msg)

        return collection

    def _build_select_fields(self, include_vectors: bool) -> str:
        """Build SELECT fields clause."""
        select_fields = "id, metadata"
        if include_vectors:
            select_fields += ", vector"
        return select_fields

    def _validate_table_name(self, table_name: str) -> str:
        """Validate and sanitize table name to prevent SQL injection."""
        # Remove any potential SQL injection characters
        if not table_name.replace(".", "").replace("_", "").isalnum():
            msg = f"Invalid table name: {table_name}"
            raise ValueError(msg)
        return table_name

    def _validate_select_fields(self, select_fields: str) -> str:
        """Validate and sanitize SELECT fields to prevent SQL injection."""
        # Allow only safe field names and common SQL tokens
        allowed_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_, .",
        )
        if not all(c in allowed_chars for c in select_fields):
            msg = f"Invalid select fields: {select_fields}"
            raise ValueError(msg)
        return select_fields

    def _build_filter_conditions(self, filter_expr: dict[str, t.Any]) -> list[str]:
        """Build WHERE clause conditions from filter expression."""
        filter_conditions = []
        for key, value in filter_expr.items():
            # Validate key to prevent SQL injection
            if not key.replace("_", "").replace("-", "").isalnum():
                msg = f"Invalid filter key: {key}"
                raise ValueError(msg)

            if isinstance(value, str):
                # Properly escape single quotes in string values
                escaped_value = value.replace("'", "''")
                filter_conditions.append(
                    f"json_extract_string(metadata, '$.{key}') = '{escaped_value}'",
                )
            else:
                filter_conditions.append(f"json_extract(metadata, '$.{key}') = {value}")
        return filter_conditions

    def _build_search_query(
        self,
        table_name: str,
        select_fields: str,
        filter_expr: dict[str, t.Any] | None,
        limit: int,
    ) -> str:
        """Build the main search query with VSS.

        Note: Uses cosine similarity which returns higher scores for more similar vectors.
        DuckDB's array_cosine_similarity returns values in range [0.0, 1.0] where
        1.0 is identical and 0.0 is orthogonal.
        """
        # Validate inputs to prevent SQL injection
        safe_table_name = self._validate_table_name(table_name)
        safe_select_fields = self._validate_select_fields(select_fields)

        # Get dimension from config for proper type casting
        dimension = self.config.vector.default_dimension

        query = f"""
            SELECT {safe_select_fields},
                   array_cosine_similarity(vector, $1::FLOAT[{dimension}]) as score
            FROM {safe_table_name}
        """  # nosec B608 - table and field names are validated

        if filter_expr:
            filter_conditions = self._build_filter_conditions(filter_expr)
            if filter_conditions:
                query += " WHERE " + " AND ".join(filter_conditions)

        query += f" ORDER BY score DESC LIMIT {limit}"  # nosec B608 - DESC for similarity
        return query

    def _build_fallback_query(
        self,
        table_name: str,
        select_fields: str,
        limit: int,
    ) -> str:
        """Build fallback query without VSS."""
        # Validate inputs to prevent SQL injection
        safe_table_name = self._validate_table_name(table_name)
        safe_select_fields = self._validate_select_fields(select_fields)

        return f"""
            SELECT {safe_select_fields}, 0.0 as score
            FROM {safe_table_name}
            LIMIT {limit}
        """  # nosec B608 - table and field names are validated

    def _convert_row_to_result(
        self,
        row: t.Any,
        include_vectors: bool,
    ) -> VectorSearchResult:
        """Convert database row to VectorSearchResult."""
        result_data = {
            "id": row[0],
            "metadata": row[1] if isinstance(row[1], dict) else {},
            "score": float(row[-1]),  # Score is always last column
        }

        if include_vectors and len(row) > 3:
            result_data["vector"] = row[2]

        return VectorSearchResult(**result_data)

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_expr: dict[str, t.Any] | None = None,
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorSearchResult]:
        """Perform vector similarity search."""
        client = await self.get_client()
        collection = self._validate_collection_name(collection)
        table_name = f"vectors.{collection}"

        # Check if table exists (table_name is validated, safe to use in f-string)
        try:
            client.execute(f"SELECT 1 FROM {table_name} LIMIT 1")  # nosec B608
        except Exception:
            return []  # Table doesn't exist, return empty results

        select_fields = self._build_select_fields(include_vectors)

        # Try VSS-based search first, fallback to basic search
        try:
            query = self._build_search_query(
                table_name,
                select_fields,
                filter_expr,
                limit,
            )
            result = client.execute(query, [query_vector]).fetchall()
        except Exception as e:
            self.logger.debug(f"VSS search failed, using fallback: {e}")
            query = self._build_fallback_query(table_name, select_fields, limit)
            result = client.execute(query).fetchall()

        # Convert results to VectorSearchResult objects
        return [self._convert_row_to_result(row, include_vectors) for row in result]

    async def insert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        """Insert documents with vectors."""
        client = await self.get_client()
        collection = self._validate_collection_name(collection)
        table_name = f"vectors.{collection}"

        # Create table if it doesn't exist
        await self._ensure_collection_exists(collection, len(documents[0].vector))

        # Prepare data for insertion
        insert_data = []
        document_ids = []

        for doc in documents:
            doc_id = doc.id or str(uuid4())
            document_ids.append(doc_id)

            insert_data.append((doc_id, doc.vector, doc.metadata))

        # Insert documents (table_name is validated, safe to use in format string)
        client.executemany(
            f"INSERT INTO {table_name} (id, vector, metadata) VALUES (?, ?, ?)",  # nosec B608
            insert_data,
        )

        return document_ids

    async def upsert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs: t.Any,
    ) -> list[str]:
        """Upsert documents with vectors."""
        client = await self.get_client()
        collection = self._validate_collection_name(collection)
        table_name = f"vectors.{collection}"

        # Create table if it doesn't exist
        await self._ensure_collection_exists(collection, len(documents[0].vector))

        # For DuckDB, we'll do a simple replace strategy
        document_ids = []

        for doc in documents:
            doc_id = doc.id or str(uuid4())
            document_ids.append(doc_id)

            # Delete existing document if it exists (table_name is validated)
            client.execute(f"DELETE FROM {table_name} WHERE id = ?", [doc_id])  # nosec B608

            # Insert new document (table_name is validated)
            client.execute(
                f"INSERT INTO {table_name} (id, vector, metadata) VALUES (?, ?, ?)",  # nosec B608
                [doc_id, doc.vector, doc.metadata],
            )

        return document_ids

    async def delete(
        self,
        collection: str,
        ids: list[str],
        **kwargs: t.Any,
    ) -> bool:
        """Delete documents by IDs."""
        client = await self.get_client()
        collection = self._validate_collection_name(collection)
        table_name = f"vectors.{collection}"
        # Validate table name to prevent SQL injection
        safe_table_name = self._validate_table_name(table_name)

        try:
            # Use parameterized query for multiple IDs
            placeholders = ",".join(["?" for _ in ids])
            query = f"DELETE FROM {safe_table_name} WHERE id IN ({placeholders})"  # nosec B608
            client.execute(query, ids)
            return True
        except Exception as e:
            self.logger.exception(f"Failed to delete documents: {e}")
            return False

    async def get(
        self,
        collection: str,
        ids: list[str],
        include_vectors: bool = False,
        **kwargs: t.Any,
    ) -> list[VectorDocument]:
        """Retrieve documents by IDs."""
        client = await self.get_client()
        collection = self._validate_collection_name(collection)
        table_name = f"vectors.{collection}"
        # Validate table name to prevent SQL injection
        safe_table_name = self._validate_table_name(table_name)

        select_fields = "id, metadata"
        if include_vectors:
            select_fields += ", vector"
        # Validate select fields to prevent SQL injection
        safe_select_fields = self._validate_select_fields(select_fields)

        try:
            placeholders = ",".join(["?" for _ in ids])
            query = f"SELECT {safe_select_fields} FROM {safe_table_name} WHERE id IN ({placeholders})"  # nosec B608
            result = client.execute(query, ids).fetchall()

            documents = []
            for row in result:
                doc_data = {
                    "id": row[0],
                    "metadata": row[1] if isinstance(row[1], dict) else {},
                    "vector": row[2] if include_vectors and len(row) > 2 else [],
                }
                documents.append(VectorDocument(**doc_data))

            return documents

        except Exception as e:
            self.logger.exception(f"Failed to retrieve documents: {e}")
            return []

    async def count(
        self,
        collection: str,
        filter_expr: dict[str, t.Any] | None = None,
        **kwargs: t.Any,
    ) -> int:
        """Count documents in collection."""
        client = await self.get_client()
        collection = self._validate_collection_name(collection)
        table_name = f"vectors.{collection}"
        # Validate table name to prevent SQL injection
        safe_table_name = self._validate_table_name(table_name)

        try:
            query = f"SELECT COUNT(*) FROM {safe_table_name}"  # nosec B608

            if filter_expr:
                filter_conditions = self._build_filter_conditions(filter_expr)
                if filter_conditions:
                    query += " WHERE " + " AND ".join(filter_conditions)

            result = client.execute(query).fetchone()
            return result[0] if result else 0

        except Exception:
            return 0

    async def create_collection(
        self,
        name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs: t.Any,
    ) -> bool:
        """Create a new collection."""
        name = self._validate_collection_name(name)
        return await self._ensure_collection_exists(name, dimension, distance_metric)

    async def delete_collection(
        self,
        name: str,
        **kwargs: t.Any,
    ) -> bool:
        """Delete a collection."""
        client = await self.get_client()
        name = self._validate_collection_name(name)
        table_name = f"vectors.{name}"

        try:
            client.execute(f"DROP TABLE IF EXISTS {table_name}")  # nosec B608
            return True
        except Exception as e:
            self.logger.exception(f"Failed to delete collection {name}: {e}")
            return False

    async def list_collections(self, **kwargs: t.Any) -> list[str]:
        """List all collections."""
        client = await self.get_client()

        try:
            result = client.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'vectors'",
            ).fetchall()
            return [row[0] for row in result]
        except Exception as e:
            self.logger.exception(f"Failed to list collections: {e}")
            return []

    async def _ensure_collection_exists(
        self,
        name: str,
        dimension: int,
        distance_metric: str = "cosine",
    ) -> bool:
        """Ensure collection table exists."""
        client = await self.get_client()
        name = self._validate_collection_name(name)
        table_name = f"vectors.{name}"

        try:
            # Create table with vector column
            create_sql = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id VARCHAR PRIMARY KEY,
                    vector FLOAT[{dimension}],
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """  # nosec B608
            client.execute(create_sql)

            # Try to create HNSW index if VSS extension is available
            if self.config.vector.enable_vss:
                try:
                    index_name = f"idx_{name}_vector"
                    # Validate index name to prevent SQL injection
                    if not index_name.replace("_", "").isalnum():
                        msg = f"Invalid index name: {index_name}"
                        raise ValueError(msg)

                    # Check if index already exists using parameterized query
                    index_check = client.execute(
                        """
                        SELECT 1 FROM duckdb_indexes()
                        WHERE index_name = ?
                    """,
                        [index_name],
                    ).fetchone()

                    if not index_check:
                        # Create HNSW index
                        index_sql = f"""
                            CREATE INDEX {index_name} ON {table_name}
                            USING HNSW (vector) WITH (metric = '{distance_metric}')
                        """  # nosec B608
                        client.execute(index_sql)
                        self.logger.debug(f"Created HNSW index for collection {name}")

                except Exception as e:
                    self.logger.debug(f"Failed to create HNSW index: {e}")

            return True

        except Exception as e:
            self.logger.exception(f"Failed to create collection {name}: {e}")
            return False


depends.set(Vector, "duckdb")
