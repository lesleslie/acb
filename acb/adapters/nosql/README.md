Error - Could not find the file by path /Users/les/Projects/acb/acb/adapters/nosql/README.md for qodo_structured_read_files> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [NoSQL](./README.md)

# NoSQL Adapter

The NoSQL adapter provides a standardized interface for document and key-value database operations in ACB applications, supporting MongoDB, Firestore, and Redis implementations.

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

## Additional Resources

- [MongoDB Documentation](https://docs.mongodb.com/manual/)
- [Firestore Documentation](https://firebase.google.com/docs/firestore)
- [Redis Documentation](https://redis.io/documentation)
- [ACB Models Adapter](../models/README.md)
- [ACB SQL Adapter](../sql/README.md)
- [ACB Adapters Overview](../README.md)
