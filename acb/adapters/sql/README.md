> **ACB Documentation**: [Main](<../../../README.md>) | [Core Systems](<../../README.md>) | [Actions](<../../actions/README.md>) | [Adapters](<../README.md>) | [SQL](<./README.md>)

# SQL Adapter

The SQL adapter provides a standardized interface for relational database operations in ACB applications, with support for MySQL/MariaDB, PostgreSQL, SQLite (including Turso), and DuckDB. It integrates seamlessly with ACB's universal query interface, providing both traditional database operations and modern query patterns.

## Table of Contents

- [Overview](<#overview>)
- [Available Implementations](<#available-implementations>)
- [Installation](<#installation>)
- [Configuration](<#configuration>)
- [Basic Usage](<#basic-usage>)
- [Universal Query Interface](<#universal-query-interface>)
  - [Simple Query Style](<#simple-query-style>)
  - [Repository Pattern](<#repository-pattern>)
  - [Specification Pattern](<#specification-pattern>)
  - [Advanced Query Builder](<#advanced-query-builder>)
  - [Hybrid Query Interface](<#hybrid-query-interface>)
- [Traditional SQL Operations](<#traditional-sql-operations>)
  - [Using SQLModel with Type Safety](<#using-sqlmodel-with-type-safety>)
  - [Transactions](<#transactions>)
  - [Raw Connection Access](<#raw-connection-access>)
- [Advanced Features](<#advanced-features>)
  - [Working with Database Migrations](<#working-with-database-migrations>)
  - [Database Backup and Restore](<#database-backup-and-restore>)
- [Troubleshooting](<#troubleshooting>)
- [Performance Considerations](<#performance-considerations>)
- [Related Adapters](<#related-adapters>)
- [Additional Resources](<#additional-resources>)

## Overview

The ACB SQL adapter offers a consistent way to interact with relational databases:

- **Universal Query Interface**: Database and model agnostic query patterns
- **Multiple Query Styles**: Simple, Repository, Specification, and Advanced patterns
- **Asynchronous Operations**: Built on SQLAlchemy and SQLModel
- **Type Safety**: Full TypeScript-style type checking with Python generics
- **Multiple Database Support**: MySQL, PostgreSQL, SQLite, DuckDB, and Turso
- **Connection Management**: Automatic pooling and session management
- **Transaction Support**: Robust transaction handling with rollback capabilities

## Available Implementations

| Implementation | Description | Best For |
| -------------- | ------------------------------ | ------------------------------------------------------------------- |
| **MySQL** | MySQL/MariaDB database adapter | Applications using MySQL/MariaDB |
| **PostgreSQL** | PostgreSQL database adapter | Applications using PostgreSQL |
| **SQLite** | SQLite/Turso database adapter | Local development, testing, edge deployments, Turso cloud databases |
| **DuckDB** | DuckDB analytics adapter | Embedded analytics, columnar workloads, read-heavy pipelines |

## Installation

```bash
# Install with SQL database support
uv add --group sql

# Or include it with other dependencies
uv add --group sql --group cache --group storage
```

## Configuration

### Settings

Configure the SQL adapter in your `settings/adapters.yaml` file:

```yaml
# Use MySQL implementation
sql: mysql

# Or use PostgreSQL implementation
sql: pgsql

# Or use SQLite implementation (local or Turso)
sql: sqlite

# Or use DuckDB implementation
sql: duckdb
```

### SQL Settings

The SQL adapter settings can be customized in your `settings/app.yaml` file:

```yaml
sql:
  # For MySQL/PostgreSQL:
  host: "db.example.com"
  port: 5432
  user: "dbuser"
  password: "dbpassword"
  database: "myapp"

  # For SQLite:
  database_url: "sqlite:///data/app.db"
  # Or Turso cloud database
  # database_url: "libsql://mydb.turso.io?authToken=your_token&secure=true"

  # For DuckDB:
  # database_url: "duckdb:///data/warehouse.duckdb"
  # threads: 4
  # pragmas:
  #   memory_limit: "4GB"
  # extensions:
  #   - httpfs

  # Connection pool settings
  pool_pre_ping: true
  poolclass: "QueuePool"

  # Engine-specific settings
  engine_kwargs:
    echo: false
    pool_size: 5
    max_overflow: 10
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the SQL adapter
SQL = import_adapter("sql")

# Get the SQL instance via dependency injection
sql = depends.get(SQL)

# Traditional session-based usage
async with sql.get_session() as session:
    result = await session.execute("SELECT * FROM users WHERE active = TRUE")
    users = result.fetchall()
```

## Universal Query Interface

ACB provides a universal query interface that works consistently across SQL and NoSQL databases while maintaining type safety and providing multiple query styles.

### Simple Query Style

The Simple Query style provides an Active Record-like interface for basic CRUD operations:

```python
from acb.adapters.models._hybrid import ACBQuery
from acb.adapters.models._query import registry
from acb.adapters.sql._query import SQLDatabaseAdapter
from acb.adapters.models._sqlmodel import SQLModelAdapter
from sqlmodel import SQLModel, Field


# Define your model
class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    active: bool = True


# Register adapters
registry.register_database_adapter("sql", SQLDatabaseAdapter(sql))
registry.register_model_adapter("sqlmodel", SQLModelAdapter())

# Create query interface
query = ACBQuery(database_adapter_name="sql", model_adapter_name="sqlmodel")


# Simple CRUD operations
async def user_operations():
    # Get all users
    users = await query.for_model(User).simple.all()

    # Find user by ID
    user = await query.for_model(User).simple.find(1)

    # Create new user
    new_user = await query.for_model(User).simple.create(
        {"name": "John Doe", "email": "john@example.com"}
    )

    # Update user
    updated_user = await query.for_model(User).simple.update(1, {"active": False})

    # Delete user
    await query.for_model(User).simple.delete(1)
```

### Repository Pattern

The Repository pattern provides domain-specific query methods with built-in caching, soft delete, and audit support:

```python
from acb.adapters.models._repository import RepositoryOptions

# Configure repository options
repo_options = RepositoryOptions(
    cache_enabled=True,
    cache_ttl=300,  # 5 minutes
    enable_soft_delete=True,
    audit_enabled=True,
)

# Create repository
user_repo = query.for_model(User).repository(repo_options)


async def repository_operations():
    # Find active users (domain-specific method)
    active_users = await user_repo.find_active()

    # Find recent users (last 7 days)
    recent_users = await user_repo.find_recent(days=7)

    # Batch operations
    users_data = [
        {"name": "User 1", "email": "user1@example.com"},
        {"name": "User 2", "email": "user2@example.com"},
    ]
    created_users = await user_repo.batch_create(users_data)

    # Soft delete (sets deleted_at timestamp)
    await user_repo.delete(user_id)

    # Count with caching
    user_count = await user_repo.count()
```

### Specification Pattern

The Specification pattern allows you to create composable, reusable business rules:

```python
from acb.adapters.models._specification import field, range_spec, custom_spec


async def specification_operations():
    # Create specifications
    active_spec = field("active").equals(True)
    email_spec = field("email").like("%@company.com")
    age_spec = range_spec("age", 18, 65, inclusive=True)

    # Combine specifications
    company_employees = active_spec & email_spec & age_spec

    # Use specifications in queries
    users = await query.for_model(User).specification.with_spec(company_employees).all()

    # Custom specifications
    def high_activity_predicate(user):
        return user.login_count > 100 and user.last_login_days_ago < 7

    from acb.adapters.models._query import QuerySpec, QueryFilter

    high_activity_spec = custom_spec(
        predicate=high_activity_predicate,
        query_spec=QuerySpec(filter=QueryFilter().where("login_count", ">", 100)),
        name="HighActivityUser",
    )

    # Complex business rules
    premium_active_users = (
        field("subscription_type").equals("premium")
        & field("active").equals(True)
        & high_activity_spec
    )

    premium_users = (
        await query.for_model(User).specification.with_spec(premium_active_users).all()
    )
```

### Advanced Query Builder

The Advanced Query Builder provides full control over query construction:

```python
async def advanced_query_operations():
    # Complex queries with joins, aggregations, and filtering
    advanced_query = query.for_model(User).advanced

    # Method chaining
    users = await (
        advanced_query.where("active", True)
        .where_gt("age", 21)
        .where_in("role", ["admin", "moderator"])
        .order_by_desc("created_at")
        .limit(10)
        .offset(20)
        .all()
    )

    # Aggregations
    user_count = await advanced_query.where("active", True).count()

    # Exists check
    has_admins = await advanced_query.where("role", "admin").exists()

    # Bulk operations
    await advanced_query.where("active", False).update({"archived": True})

    # Complex aggregation pipeline
    pipeline = [
        {"$match": {"active": True}},
        {"$group": {"_id": "$role", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    role_stats = await advanced_query.aggregate(pipeline)
```

### Hybrid Query Interface

The Hybrid Query Interface allows you to mix and match different query styles:

```python
async def hybrid_operations():
    # Start with repository pattern
    user_manager = query.for_model(User)

    # Switch between styles as needed
    async with user_manager.transaction():
        # Use repository for domain logic
        active_users = await user_manager.repository().find_active()

        # Use specifications for complex business rules
        premium_spec = field("subscription_type").equals("premium")
        premium_users = await user_manager.specification.with_spec(premium_spec).all()

        # Use advanced queries for complex operations
        await user_manager.advanced.where_in(
            "id", [u.id for u in premium_users]
        ).update({"premium_expires_at": datetime.now() + timedelta(days=30)})

        # Use simple queries for basic operations
        new_user = await user_manager.simple.create(
            {"name": "New User", "email": "new@example.com"}
        )
```

## Traditional SQL Operations

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


# Traditional SQLModel usage
SQL = import_adapter("sql")
sql = depends.get(SQL)

async with sql.get_session() as session:
    # Create
    new_user = User(name="John Doe", email="john@example.com")
    session.add(new_user)
    await session.commit()

    # Query
    statement = select(User).where(User.active == True)
    result = await session.execute(statement)
    users = result.scalars().all()
```

### Transactions

```python
# Using the universal query interface with transactions
async with query.for_model(User).transaction():
    # All operations in this block are part of the same transaction
    await query.for_model(User).simple.update(1, {"balance": 1000})
    await query.for_model(User).simple.update(2, {"balance": 2000})
    # Transaction is automatically committed or rolled back

# Traditional transaction handling
async with sql.get_session() as session:
    async with session.begin():
        await session.execute(
            "UPDATE accounts SET balance = balance - 100 WHERE id = 1"
        )
        await session.execute(
            "UPDATE accounts SET balance = balance + 100 WHERE id = 2"
        )
```

### Raw Connection Access

```python
# For operations that need direct connection access
async with sql.get_conn() as conn:
    result = await conn.execute("SHOW TABLES")
    tables = result.fetchall()
```

## Advanced Features

### Working with Database Migrations

```python
# The SQL adapter initializes and runs migrations automatically
await sql.run_migrations()

# Run specific migrations
await sql.run_migration("20230501_add_user_roles.sql")
```

### Database Backup and Restore

```python
# Create a database backup
backup_id = await sql.create_backup()

# Restore from a backup
success = await sql.restore_backup(backup_id)
```

## Performance Considerations

### Query Optimization with Universal Interface

```python
# Use specifications for reusable business logic
frequently_used_spec = field("status").equals("active") & field("verified").equals(True)

# Repository pattern automatically handles caching
repo = query.for_model(User).repository(
    RepositoryOptions(cache_enabled=True, cache_ttl=300)
)
users = await repo.find_by_specification(frequently_used_spec)  # Cached result

# Efficient batch operations
await repo.batch_create([...])  # Automatically batched
```

### Connection Pool Configuration

```yaml
sql:
  engine_kwargs:
    pool_size: 10
    max_overflow: 20
    pool_timeout: 30
```

### Implementation Performance

| Implementation | Universal Query | Traditional SQL | Best For |
| -------------- | --------------- | --------------- | ---------------------- |
| **MySQL** | Excellent | Excellent | High write workloads |
| **PostgreSQL** | Excellent | Excellent | Complex queries, JSONB |
| **SQLite** | Excellent | Excellent | Local development |
| **Turso** | Excellent | Excellent | Edge deployments |

## Related Adapters

The SQL adapter integrates seamlessly with other ACB adapters:

- [**Models Adapter**](<../models/README.md>): Define SQLModel and Pydantic models
- [**Cache Adapter**](<../cache/README.md>): Automatic query result caching
- [**NoSQL Adapter**](<../nosql/README.md>): Hybrid database architectures
- [**Storage Adapter**](<../storage/README.md>): File metadata storage

## Additional Resources

- [Universal Query Interface Documentation](<../models/README.md>)
- [Specification Pattern Examples](<../models/README.md#specification-pattern>)
- [Repository Pattern Examples](<../models/README.md#repository-pattern>)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html)
