Error - Could not find the file by path /Users/les/Projects/acb/acb/adapters/sql/README.md for qodo_structured_read_files> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [SQL](./README.md)

# SQL Adapter

The SQL adapter provides a standardized interface for relational database operations in ACB applications, with support for MySQL/MariaDB and PostgreSQL.

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
```

### SQL Settings

The SQL adapter settings can be customized in your `settings/app.yml` file:

```yaml
sql:
  # Database host (defaults to 127.0.0.1 for local development)
  host: "db.example.com"

  # Database port
  port: 5432  # PostgreSQL default

  # Database credentials
  user: "dbuser"
  password: "dbpassword"

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

## Additional Resources

- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html)
- [MySQL Documentation](https://dev.mysql.com/doc/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [ACB Models Adapter](../models/README.md)
- [ACB NoSQL Adapter](../nosql/README.md)
