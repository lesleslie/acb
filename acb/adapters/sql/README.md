Error - Could not find the file by path /Users/les/Projects/acb/acb/adapters/sql/README.md for qodo_structured_read_files> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [SQL](./README.md)

# SQL Adapter

The SQL adapter provides a standardized interface for relational database operations in ACB applications, with support for MySQL/MariaDB, PostgreSQL, and SQLite (including Turso).

## Table of Contents

- [Overview](#overview)
- [Available Implementations](#available-implementations)
- [Installation](#installation)
- [Configuration](#configuration)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
  - [Using SQLModel with Type Safety](#using-sqlmodel-with-type-safety)
  - [Transactions](#transactions)
  - [Raw Connection Access](#raw-connection-access)
  - [Working with Database Migrations](#working-with-database-migrations)
  - [Database Backup and Restore](#database-backup-and-restore)
- [Troubleshooting](#troubleshooting)
- [Implementation Details](#implementation-details)
- [Performance Considerations](#performance-considerations)
- [Related Adapters](#related-adapters)
- [Additional Resources](#additional-resources)

## Overview

The ACB SQL adapter offers a consistent way to interact with relational databases:

- Asynchronous database operations using SQLAlchemy and SQLModel
- Support for multiple database implementations
- Automatic schema creation and migration
- Connection pooling for efficient resource usage
- Session management and transaction support

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **MySQL** | MySQL/MariaDB database adapter | Applications using MySQL/MariaDB |
| **PostgreSQL** | PostgreSQL database adapter | Applications using PostgreSQL |
| **SQLite** | SQLite/Turso database adapter | Local development, testing, edge deployments, Turso cloud databases |

## Installation

```bash
# Install with SQL database support
pdm add "acb[sql]"

# Or include it with other dependencies
pdm add "acb[sql,redis,storage]"
```

## Configuration

### Settings

Configure the SQL adapter in your `settings/adapters.yml` file:

```yaml
# Use MySQL implementation
sql: mysql

# Or use PostgreSQL implementation
sql: pgsql

# Or use SQLite implementation (local or Turso)
sql: sqlite
```

### SQL Settings

The SQL adapter settings can be customized in your `settings/app.yml` file:

```yaml
sql:
  # For MySQL/PostgreSQL:
  # Database host (defaults to 127.0.0.1 for local development)
  host: "db.example.com"

  # Database port
  port: 5432  # PostgreSQL default

  # Database credentials
  user: "dbuser"
  password: "dbpassword"

  # For SQLite:
  # Local SQLite database
  database_url: "sqlite:///data/app.db"

  # Or Turso cloud database
  database_url: "libsql://mydb.turso.io?authToken=your_token&secure=true"
  auth_token: "your_turso_auth_token"  # Alternative way to provide token
  wal_mode: true  # Enable WAL mode for SQLite (ignored for Turso)

  # Connection pool settings
  pool_pre_ping: true
  poolclass: "QueuePool"

  # Engine-specific settings
  engine_kwargs:
    echo: true  # Log SQL queries
    pool_size: 5
    max_overflow: 10

  # Backup settings
  backup_enabled: false
  backup_bucket: "db-backups"
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the SQL adapter
SQL = import_adapter("sql")

# Get the SQL instance via dependency injection
sql = depends.get(SQL)

# Execute a query using a context manager for the session
async with sql.get_session() as session:
    result = await session.execute("SELECT * FROM users WHERE active = TRUE")
    users = result.fetchall()

    # Work with the results
    for user in users:
        print(f"User: {user.name}, Email: {user.email}")
```

## SQLite and Turso Usage

### Local SQLite Database

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Configure for local SQLite (in settings/app.yml)
# sql:
#   database_url: "sqlite:///data/app.db"
#   wal_mode: true

SQL = import_adapter("sql")
sql = depends.get(SQL)

# The adapter automatically:
# - Creates the data directory if it doesn't exist
# - Enables WAL mode for better concurrency
# - Uses aiosqlite driver for async operations

async with sql.get_session() as session:
    result = await session.execute("SELECT sqlite_version()")
    version = result.scalar()
    print(f"SQLite version: {version}")
```

### Turso Cloud Database

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Configure for Turso (in settings/app.yml)
# sql:
#   database_url: "libsql://mydb.turso.io?authToken=your_token&secure=true"
#   # Or provide token separately:
#   # auth_token: "your_turso_auth_token"

SQL = import_adapter("sql")
sql = depends.get(SQL)

# The adapter automatically:
# - Detects Turso URL pattern
# - Uses sqlalchemy-libsql driver for HTTP access
# - Handles authentication tokens
# - Supports secure connections

async with sql.get_session() as session:
    # Works exactly the same as local SQLite!
    result = await session.execute("SELECT COUNT(*) FROM users")
    count = result.scalar()
    print(f"Users in Turso database: {count}")
```

### Dual Mode Development

```python
import os
from acb.depends import depends
from acb.adapters import import_adapter

# Switch between local and remote based on environment
def get_database_url():
    if os.getenv("ENVIRONMENT") == "production":
        return "libsql://prod-db.turso.io?authToken=prod_token&secure=true"
    else:
        return "sqlite:///data/dev.db"

# Use the same code for both local and remote!
SQL = import_adapter("sql")
sql = depends.get(SQL)

async with sql.get_session() as session:
    # This works identically for both SQLite and Turso
    users = await session.execute("SELECT * FROM users LIMIT 10")
    for user in users:
        print(user)
```

## Advanced Usage

### Using SQLModel with Type Safety

```python
from sqlmodel import Field, SQLModel, select
from acb.depends import depends
from acb.adapters import import_adapter

# Define your models
class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    active: bool = True

# Import the SQL adapter
SQL = import_adapter("sql")
sql = depends.get(SQL)

# Create a new user
async with sql.get_session() as session:
    new_user = User(name="John Doe", email="john@example.com")
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    print(f"Created user with ID: {new_user.id}")

# Query with type safety
async with sql.get_session() as session:
    statement = select(User).where(User.active == True)
    result = await session.execute(statement)
    users = result.scalars().all()

    for user in users:
        print(f"User: {user.name}, Email: {user.email}")
```

### Transactions

```python
from acb.depends import depends
from acb.adapters import import_adapter

SQL = import_adapter("sql")
sql = depends.get(SQL)

# Using transactions
async with sql.get_session() as session:
    try:
        # Start a transaction
        async with session.begin():
            # All operations within this block are part of the same transaction
            await session.execute("UPDATE accounts SET balance = balance - 100 WHERE id = 1")
            await session.execute("UPDATE accounts SET balance = balance + 100 WHERE id = 2")

            # If any operation fails, the entire transaction is rolled back
            # If all succeed, the transaction is committed automatically
    except Exception as e:
        print(f"Transaction failed: {e}")
```

### Raw Connection Access

```python
# For operations that need direct connection access
async with sql.get_conn() as conn:
    # Execute a raw SQL statement
    result = await conn.execute("SHOW TABLES")
    tables = result.fetchall()

    # Or execute multiple statements in a transaction
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
```

### Working with Database Migrations

```python
from acb.depends import depends
from acb.adapters import import_adapter

SQL = import_adapter("sql")
sql = depends.get(SQL)

# Run migrations
async def run_migrations():
    # The SQL adapter initializes and runs migrations automatically
    # during application startup, but you can also trigger it manually:
    await sql.run_migrations()

    # Or run specific migrations:
    await sql.run_migration("20230501_add_user_roles.sql")
```

### Database Backup and Restore

```python
# Create a database backup
backup_id = await sql.create_backup()
print(f"Created backup with ID: {backup_id}")

# Restore from a backup
success = await sql.restore_backup(backup_id)
if success:
    print("Database restored successfully")
else:
    print("Backup restoration failed")
```

## Troubleshooting

### Common Issues

1. **Connection Error**
   - **Problem**: `ConnectionError: Cannot connect to MySQL server`
   - **Solution**: Check your database host, port, and credentials

2. **Table Not Found**
   - **Problem**: `TableNotFoundError: Table 'users' doesn't exist`
   - **Solution**: Ensure your models are properly defined and migrations have run

3. **Pool Exhaustion**
   - **Problem**: `TimeoutError: Connection pool exhausted`
   - **Solution**: Increase pool size or fix connection leaks in your code

4. **Deadlock**
   - **Problem**: `DeadlockError: Deadlock found when trying to get lock`
   - **Solution**: Review your transaction logic and consider restructuring queries

## Implementation Details

The SQL adapter implements these core methods:

```python
class SqlBase:
    @property
    def engine(self) -> AsyncEngine: ...
    @property
    def session(self) -> AsyncSession: ...

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]: ...

    @asynccontextmanager
    async def get_conn(self) -> AsyncGenerator[AsyncConnection, None]: ...

    async def init(self) -> None: ...
    async def run_migrations(self) -> None: ...
    async def create_backup(self) -> str: ...
    async def restore_backup(self, backup_id: str) -> bool: ...
```

## Performance Considerations

When working with the SQL adapter, keep these performance factors in mind:

1. **Connection Pooling**: The SQL adapter uses connection pooling to efficiently manage database connections. Configure pool size based on your application's needs:

```yaml
sql:
  engine_kwargs:
    pool_size: 10  # Adjust based on expected concurrent connections
    max_overflow: 20  # Additional connections when pool is exhausted
    pool_timeout: 30  # Seconds to wait for a connection from the pool
```

2. **Query Optimization**:
   - Use specific column selection instead of `SELECT *`
   - Add appropriate indexes for frequently queried columns
   - Use pagination for large result sets
   - Consider using compiled queries for frequently executed statements

3. **Batch Operations**: For bulk inserts or updates, use batch operations:

```python
# Efficient batch insert
async with sql.get_session() as session:
    session.add_all([
        User(name="User 1", email="user1@example.com"),
        User(name="User 2", email="user2@example.com"),
        User(name="User 3", email="user3@example.com")
    ])
    await session.commit()
```

4. **Implementation Performance**:

| Implementation | Read Performance | Write Performance | Best For |
|----------------|------------------|-------------------|----------|
| **MySQL** | Fast | Very Fast | High write workloads, simpler queries |
| **PostgreSQL** | Very Fast | Fast | Complex queries, JSONB data, full-text search |
| **SQLite** | Very Fast | Fast | Local development, testing, single-user apps, edge deployments |
| **Turso** | Fast | Fast | Globally distributed SQLite, serverless apps, edge computing |

5. **Async Execution**: Remember that database operations are asynchronous and should be properly awaited:

```python
# Correct async usage
async with sql.get_session() as session:
    result = await session.execute(select(User))
    users = result.scalars().all()
```

## Related Adapters

The SQL adapter works well with these other ACB adapters:

- [**Models Adapter**](../models/README.md): Define and work with SQLModel models
- [**Cache Adapter**](../cache/README.md): Cache database query results to improve performance
- [**NoSQL Adapter**](../nosql/README.md): Use alongside SQL for hybrid database architectures
- [**Storage Adapter**](../storage/README.md): Store file metadata in SQL while storing actual files in object storage

Integration example:

```python
# Using SQL and Cache adapters together for efficient data access
from acb.depends import depends
from acb.adapters import import_adapter
from sqlmodel import select

SQL = import_adapter("sql")
Cache = import_adapter("cache")

sql = depends.get(SQL)
cache = depends.get(Cache)

async def get_user(user_id: int):
    # Try to get from cache first
    cache_key = f"user:{user_id}"
    user = await cache.get(cache_key)

    if not user:
        # Cache miss - get from database
        async with sql.get_session() as session:
            statement = select(User).where(User.id == user_id)
            result = await session.execute(statement)
            user = result.scalar_one_or_none()

            if user:
                # Store in cache for future requests
                await cache.set(cache_key, user, ttl=300)  # Cache for 5 minutes

    return user
```

## Additional Resources

- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html)
- [MySQL Documentation](https://dev.mysql.com/doc/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Database Indexing Strategies](https://use-the-index-luke.com/)
- [ACB Models Adapter](../models/README.md)
- [ACB NoSQL Adapter](../nosql/README.md)
- [ACB Cache Adapter](../cache/README.md)
