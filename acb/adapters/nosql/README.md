Error - Could not find the file by path /Users/les/Projects/acb/acb/adapters/nosql/README.md for qodo_structured_read_files> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [NoSQL](./README.md)

# NoSQL Adapter

The NoSQL adapter provides a standardized interface for document and key-value database operations in ACB applications, supporting MongoDB, Firestore, and Redis implementations.

## Table of Contents

- [Overview](#overview)
- [Available Implementations](#available-implementations)
- [Installation](#installation)
- [Configuration](#configuration)
- [Basic Usage](#basic-usage)
  - [MongoDB Implementation](#mongodb-implementation)
  - [Firestore Implementation](#firestore-implementation)
  - [Redis Implementation](#redis-implementation)
- [Advanced Usage](#advanced-usage)
  - [Transactions](#transactions)
  - [Aggregation Pipelines](#aggregation-pipelines)
  - [Querying with Models](#querying-with-models)
- [Troubleshooting](#troubleshooting)
- [Implementation Details](#implementation-details)
- [Performance Considerations](#performance-considerations)
- [Related Adapters](#related-adapters)
- [Additional Resources](#additional-resources)

## Overview

The ACB NoSQL adapter offers:

- Consistent interface for document/key-value databases
- Support for multiple NoSQL implementations
- Asynchronous operations
- Document validation
- Query building capabilities
- Collection/database management

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **MongoDB** | Document-oriented database | Complex document storage, queries, aggregations |
| **Firestore** | Google Cloud Firestore | Google Cloud deployments, real-time applications |
| **Redis** | In-memory data structure store | Caching, pub/sub, simple data structures |

## Installation

```bash
# Install with NoSQL support
pdm add "acb[nosql]"

# Or with specific implementation
pdm add "acb[mongodb]"
pdm add "acb[firestore]"
pdm add "acb[redis]"

# Or include it with other dependencies
pdm add "acb[nosql,sql,storage]"
```

## Configuration

### Settings

Configure the NoSQL adapter in your `settings/adapters.yml` file:

```yaml
# Use MongoDB implementation
nosql: mongodb

# Or use Firestore implementation
nosql: firestore

# Or use Redis implementation
nosql: redis
```

### NoSQL Settings

The NoSQL adapter settings can be customized in your `settings/app.yml` file:

```yaml
nosql:
  # MongoDB specific settings
  connection_string: "mongodb://localhost:27017"
  database: "myapp"

  # Firestore specific settings
  project_id: "my-gcp-project"
  collection_prefix: "myapp"

  # Redis specific settings (for NoSQL usage, not caching)
  host: "localhost"
  port: 6379
  db: 0
  password: null
```

## Basic Usage

### MongoDB Implementation

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the NoSQL adapter
NoSQL = import_adapter("nosql")

# Get the NoSQL instance via dependency injection
nosql = depends.get(NoSQL)

# Insert a document
user = {
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30,
    "active": True
}
user_id = await nosql.users.insert_one(user)

# Find documents
active_users = await nosql.users.find({"active": True})
for user in active_users:
    print(f"User: {user['name']}, Email: {user['email']}")

# Update a document
await nosql.users.update_one(
    {"_id": user_id},
    {"$set": {"last_login": datetime.now()}}
)

# Delete a document
await nosql.users.delete_one({"email": "john@example.com"})
```

### Firestore Implementation

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the NoSQL adapter
NoSQL = import_adapter("nosql")
nosql = depends.get(NoSQL)

# Add a document
product = {
    "name": "Smartphone",
    "price": 699.99,
    "category": "electronics",
    "in_stock": True
}
product_id = await nosql.products.add(product)

# Get a document by ID
product = await nosql.products.get(product_id)
print(f"Product: {product['name']}, Price: ${product['price']}")

# Query documents
electronics = await nosql.products.where("category", "==", "electronics").where("in_stock", "==", True).get()
for item in electronics:
    print(f"Item: {item['name']}, Price: ${item['price']}")

# Update a document
await nosql.products.update(product_id, {"price": 649.99, "on_sale": True})

# Delete a document
await nosql.products.delete(product_id)
```

### Redis Implementation

```python
from acb.depends import depends
from acb.adapters import import_adapter
import json

# Import the NoSQL adapter
NoSQL = import_adapter("nosql")
nosql = depends.get(NoSQL)

# Store a simple key-value
await nosql.set("greeting", "Hello, World!")
value = await nosql.get("greeting")
print(value)  # "Hello, World!"

# Store a hash (for document-like data)
await nosql.hmset("user:1001", {
    "name": "Jane Smith",
    "email": "jane@example.com",
    "score": 95
})

# Get hash fields
email = await nosql.hget("user:1001", "email")
print(email)  # "jane@example.com"

# Get all hash fields
user = await nosql.hgetall("user:1001")
print(user)  # {"name": "Jane Smith", "email": "jane@example.com", "score": "95"}

# Store a complex object (using JSON serialization)
settings = {
    "theme": "dark",
    "notifications": True,
    "favorites": [1, 5, 9]
}
await nosql.set("settings:1001", json.dumps(settings))

# Delete a key
await nosql.delete("greeting")
```

## Advanced Usage

### Transactions

```python
from acb.depends import depends
from acb.adapters import import_adapter

NoSQL = import_adapter("nosql")
nosql = depends.get(NoSQL)

# Using transactions (MongoDB example)
async with await nosql.start_transaction() as session:
    try:
        # Withdraw from one account
        await nosql.accounts.update_one(
            {"_id": "account1"},
            {"$inc": {"balance": -100}},
            session=session
        )

        # Deposit to another account
        await nosql.accounts.update_one(
            {"_id": "account2"},
            {"$inc": {"balance": 100}},
            session=session
        )

        # Transaction commits automatically if no exceptions occur
    except Exception as e:
        # Transaction rolls back automatically on exception
        print(f"Transaction failed: {e}")
        raise
```

### Aggregation Pipelines

```python
# MongoDB aggregation example
pipeline = [
    {"$match": {"status": "active"}},
    {"$group": {
        "_id": "$category",
        "count": {"$sum": 1},
        "avg_price": {"$avg": "$price"}
    }},
    {"$sort": {"count": -1}}
]

categories = await nosql.products.aggregate(pipeline)
for category in categories:
    print(f"Category: {category['_id']}")
    print(f"  Product count: {category['count']}")
    print(f"  Average price: ${category['avg_price']:.2f}")
```

### Querying with Models

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from acb.depends import depends
from acb.adapters import import_adapter

# Define a model
class Product(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    name: str
    price: float
    category: str
    tags: List[str] = []
    in_stock: bool = True

# Use the model with NoSQL
NoSQL = import_adapter("nosql")
nosql = depends.get(NoSQL)

# Create a product
new_product = Product(
    name="Smart Watch",
    price=299.99,
    category="wearables",
    tags=["electronics", "fitness"]
)

# Save to database
product_dict = new_product.dict(by_alias=True, exclude={"id": True})
product_id = await nosql.products.insert_one(product_dict)

# Query and convert to model
result = await nosql.products.find_one({"_id": product_id})
product = Product(**result)
print(f"Product: {product.name}, Price: ${product.price}")
```

## Troubleshooting

### Common Issues

1. **Connection Errors**
   - **Problem**: `ConnectionError: Cannot connect to MongoDB server`
   - **Solution**: Verify connection string, credentials, and network connectivity

2. **Authentication Failures**
   - **Problem**: `AuthenticationError: Authentication failed`
   - **Solution**: Check username, password, and authentication database

3. **Document Not Found**
   - **Problem**: `None` returned when querying for a document
   - **Solution**: Verify the document ID or query criteria

4. **Schema Validation Errors**
   - **Problem**: `ValidationError: Document failed validation`
   - **Solution**: Ensure document structure matches schema requirements

## Implementation Details

The NoSQL adapter dynamically creates collection/table properties based on usage:

```python
class NoSQLBase:
    # Collections are accessed as properties:
    # nosql.users -> users collection
    # nosql.products -> products collection

    # Core methods include:
    async def find(self, filter, **kwargs): ...
    async def find_one(self, filter, **kwargs): ...
    async def insert_one(self, document, **kwargs): ...
    async def insert_many(self, documents, **kwargs): ...
    async def update_one(self, filter, update, **kwargs): ...
    async def update_many(self, filter, update, **kwargs): ...
    async def delete_one(self, filter, **kwargs): ...
    async def delete_many(self, filter, **kwargs): ...
    async def count(self, filter=None, **kwargs): ...
    async def aggregate(self, pipeline, **kwargs): ...
    async def start_transaction(self, **kwargs): ...
```

## Performance Considerations

When working with the NoSQL adapter, keep these performance factors in mind:

1. **Implementation Performance**:

| Implementation | Read Performance | Write Performance | Query Flexibility | Best For |
|----------------|------------------|-------------------|-------------------|----------|
| **MongoDB** | Fast | Fast | Very High | Complex documents, flexible schemas, aggregations |
| **Firestore** | Fast | Medium | High | Real-time applications, mobile/web apps |
| **Redis** | Very Fast | Very Fast | Limited | Caching, simple data structures, high throughput |

2. **Indexing Strategy**:
   - Create indexes for frequently queried fields
   - Avoid over-indexing as it slows down writes
   - Use compound indexes for multi-field queries
   - Consider index size and memory impact

```python
# MongoDB indexing example
await nosql.users.create_index([('email', 1)], unique=True)
await nosql.products.create_index([('category', 1), ('price', -1)])
```

3. **Query Optimization**:
   - Use specific queries instead of retrieving entire documents
   - Limit result sets for pagination
   - Use projections to return only needed fields
   - Structure documents to match access patterns

```python
# Optimized query with projection and limit
results = await nosql.products.find(
    {"category": "electronics", "price": {"$lt": 500}},
    projection={"name": 1, "price": 1, "_id": 1},
    limit=20
)
```

4. **Batch Operations**:
   - Use bulk operations for multiple documents
   - Consider chunking very large operations

```python
# Efficient batch insert
await nosql.logs.insert_many([
    {"level": "info", "message": "User login", "timestamp": datetime.now()},
    {"level": "error", "message": "Database connection failed", "timestamp": datetime.now()},
    {"level": "info", "message": "Task completed", "timestamp": datetime.now()}
])
```

5. **Connection Management**:
   - Use connection pooling (configured automatically)
   - Monitor connection usage in high-traffic applications
   - Consider read replicas for read-heavy workloads

## Related Adapters

The NoSQL adapter works well with these other ACB adapters:

- [**Cache Adapter**](../cache/README.md): Use Redis for both caching and NoSQL operations
- [**SQL Adapter**](../sql/README.md): Combine SQL and NoSQL for hybrid data access patterns
- [**Models Adapter**](../models/README.md): Define Pydantic models for document validation
- [**Storage Adapter**](../storage/README.md): Store file metadata in NoSQL while storing files in object storage

Integration example:

```python
# Using NoSQL and Cache adapters together
from acb.depends import depends
from acb.adapters import import_adapter

NoSQL = import_adapter("nosql")
Cache = import_adapter("cache")

nosql = depends.get(NoSQL)
cache = depends.get(Cache)

async def get_product(product_id: str):
    # Try to get from cache first
    cache_key = f"product:{product_id}"
    product = await cache.get(cache_key)

    if not product:
        # Cache miss - get from database
        product = await nosql.products.find_one({"_id": product_id})

        if product:
            # Store in cache for future requests
            await cache.set(cache_key, product, ttl=300)  # Cache for 5 minutes

    return product

# Hybrid SQL/NoSQL example
from acb.depends import depends
from acb.adapters import import_adapter
from sqlmodel import select

SQL = import_adapter("sql")
NoSQL = import_adapter("nosql")

sql = depends.get(SQL)
nosql = depends.get(NoSQL)

async def get_user_with_activity(user_id: int):
    # Get user profile from SQL database
    async with sql.get_session() as session:
        statement = select(User).where(User.id == user_id)
        result = await session.execute(statement)
        user = result.scalar_one_or_none()

    if not user:
        return None

    # Get user activity from NoSQL database
    activity = await nosql.user_activity.find(
        {"user_id": str(user_id)},
        sort=[("timestamp", -1)],
        limit=10
    ).to_list()

    # Combine the data
    return {
        "profile": user.dict(),
        "recent_activity": activity
    }
```

## Additional Resources

- [MongoDB Documentation](https://docs.mongodb.com/manual/)
- [MongoDB Performance Best Practices](https://www.mongodb.com/docs/manual/core/query-optimization/)
- [Firestore Documentation](https://firebase.google.com/docs/firestore)
- [Firestore Best Practices](https://firebase.google.com/docs/firestore/best-practices)
- [Redis Documentation](https://redis.io/documentation)
- [Redis Performance Optimization](https://redis.io/topics/optimization)
- [ACB Models Adapter](../models/README.md)
- [ACB SQL Adapter](../sql/README.md)
- [ACB Cache Adapter](../cache/README.md)
- [ACB Adapters Overview](../README.md)
