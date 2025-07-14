> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [NoSQL](./README.md)

# NoSQL Adapter

The NoSQL adapter provides a standardized interface for document and key-value database operations in ACB applications, supporting MongoDB, Firestore, and Redis implementations. It integrates seamlessly with ACB's universal query interface, providing both traditional NoSQL operations and modern query patterns.

## Table of Contents

- [Overview](#overview)
- [Available Implementations](#available-implementations)
- [Installation](#installation)
- [Configuration](#configuration)
- [Basic Usage](#basic-usage)
- [Universal Query Interface](#universal-query-interface)
  - [Simple Query Style](#simple-query-style)
  - [Repository Pattern](#repository-pattern)
  - [Specification Pattern](#specification-pattern)
  - [Advanced Query Builder](#advanced-query-builder)
  - [Hybrid Query Interface](#hybrid-query-interface)
- [Traditional NoSQL Operations](#traditional-nosql-operations)
  - [MongoDB Implementation](#mongodb-implementation)
  - [Firestore Implementation](#firestore-implementation)
  - [Redis Implementation](#redis-implementation)
- [Advanced Features](#advanced-features)
  - [Transactions](#transactions)
  - [Aggregation Pipelines](#aggregation-pipelines)
  - [Querying with Models](#querying-with-models)
- [Troubleshooting](#troubleshooting)
- [Performance Considerations](#performance-considerations)
- [Related Adapters](#related-adapters)
- [Additional Resources](#additional-resources)

## Overview

The ACB NoSQL adapter offers:

- **Universal Query Interface**: Database and model agnostic query patterns
- **Multiple Query Styles**: Simple, Repository, Specification, and Advanced patterns
- **Consistent Interface**: Works the same across MongoDB, Firestore, and Redis
- **Type Safety**: Full type checking with Python generics
- **Asynchronous Operations**: Built for high-performance async applications
- **Document Validation**: Integrated with Pydantic models
- **Flexible Schema**: Support for dynamic and structured documents

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **MongoDB** | Document-oriented database using Beanie | Complex document storage, queries, aggregations |
| **Firestore** | Google Cloud Firestore | Google Cloud deployments, real-time applications |
| **Redis** | In-memory data structure store using Redis-OM | Caching, pub/sub, simple data structures |

## Installation

```bash
# Install with NoSQL support
uv add "acb[nosql]"

# Or with specific implementation
uv add "acb[mongodb]"
uv add "acb[firestore]"
uv add "acb[redis]"

# Or include it with other dependencies
uv add "acb[nosql,sql,storage]"
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
  # Common settings
  host: "127.0.0.1"
  database: "myapp"
  collection_prefix: ""

  # MongoDB specific settings
  port: 27017
  connection_string: "mongodb://localhost:27017/myapp"
  connection_options: {}

  # Firestore specific settings
  project_id: "my-gcp-project"
  credentials_path: "/path/to/credentials.json"
  emulator_host: null

  # Redis specific settings
  port: 6379
  db: 0
  password: null
  decode_responses: true
  encoding: "utf-8"
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the NoSQL adapter
NoSQL = import_adapter("nosql")

# Get the NoSQL instance via dependency injection
nosql = depends.get(NoSQL)

# Traditional usage - insert a document
user = {
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30,
    "active": True
}
user_id = await nosql.users.insert_one(user)

# Find documents
active_users = await nosql.users.find({"active": True})
```

## Universal Query Interface

ACB provides a universal query interface that works consistently across NoSQL databases while maintaining type safety and providing multiple query styles.

### Simple Query Style

The Simple Query style provides an Active Record-like interface for basic CRUD operations:

```python
from acb.adapters.models._hybrid import ACBQuery
from acb.adapters.models._query import registry
from acb.adapters.nosql._query import NoSQLDatabaseAdapter
from acb.adapters.models._pydantic import PydanticModelAdapter
from pydantic import BaseModel, Field

# Define your model
class Product(BaseModel):
    id: str = Field(default=None, alias="_id")
    name: str
    price: float
    category: str
    active: bool = True

# Register adapters
registry.register_database_adapter("nosql", NoSQLDatabaseAdapter(nosql))
registry.register_model_adapter("pydantic", PydanticModelAdapter())

# Create query interface
query = ACBQuery(database_adapter_name="nosql", model_adapter_name="pydantic")

# Simple CRUD operations
async def product_operations():
    # Get all products
    products = await query.for_model(Product).simple.all()

    # Find product by ID
    product = await query.for_model(Product).simple.find("12345")

    # Create new product
    new_product = await query.for_model(Product).simple.create({
        "name": "Smart Watch",
        "price": 299.99,
        "category": "electronics"
    })

    # Update product
    updated_product = await query.for_model(Product).simple.update("12345", {
        "price": 249.99,
        "on_sale": True
    })

    # Delete product
    await query.for_model(Product).simple.delete("12345")
```

### Repository Pattern

The Repository pattern provides domain-specific query methods with built-in caching and business logic:

```python
from acb.adapters.models._repository import RepositoryOptions

# Configure repository options
repo_options = RepositoryOptions(
    cache_enabled=True,
    cache_ttl=300,  # 5 minutes
    enable_soft_delete=True,
    audit_enabled=True
)

# Create repository
product_repo = query.for_model(Product).repository(repo_options)

async def repository_operations():
    # Find active products (domain-specific method)
    active_products = await product_repo.find_active()

    # Find recent products (last 7 days)
    recent_products = await product_repo.find_recent(days=7)

    # Batch operations
    products_data = [
        {"name": "Product 1", "price": 19.99, "category": "books"},
        {"name": "Product 2", "price": 29.99, "category": "electronics"}
    ]
    created_products = await product_repo.batch_create(products_data)

    # Count with caching
    product_count = await product_repo.count()

    # Exists check
    has_electronics = await product_repo.exists(
        field("category").equals("electronics")
    )
```

### Specification Pattern

The Specification pattern allows you to create composable, reusable business rules:

```python
from acb.adapters.models._specification import field, range_spec, custom_spec

async def specification_operations():
    # Create specifications
    active_spec = field("active").equals(True)
    electronics_spec = field("category").equals("electronics")
    price_range_spec = range_spec("price", 10.0, 500.0, inclusive=True)

    # Combine specifications
    affordable_electronics = active_spec & electronics_spec & price_range_spec

    # Use specifications in queries
    products = await query.for_model(Product).specification.with_spec(affordable_electronics).all()

    # Custom specifications with NoSQL-specific logic
    def trending_product_predicate(product):
        return product.views > 1000 and product.rating > 4.5

    from acb.adapters.models._query import QuerySpec, QueryFilter
    trending_spec = custom_spec(
        predicate=trending_product_predicate,
        query_spec=QuerySpec(filter=QueryFilter()
            .where("views", ">", 1000)
            .where("rating", ">", 4.5)
        ),
        name="TrendingProduct"
    )

    # Complex business rules
    premium_trending = (
        field("price").greater_than(100.0) &
        field("category").in_list(["electronics", "jewelry"]) &
        trending_spec
    )

    premium_products = await query.for_model(Product).specification.with_spec(premium_trending).all()
```

### Advanced Query Builder

The Advanced Query Builder provides full control over NoSQL queries:

```python
async def advanced_nosql_operations():
    # Complex queries with NoSQL-specific features
    advanced_query = query.for_model(Product).advanced

    # Method chaining for complex filters
    products = await (advanced_query
        .where("active", True)
        .where_gt("price", 50.0)
        .where_in("category", ["electronics", "books", "toys"])
        .where_like("name", "%smart%")
        .order_by_desc("created_at")
        .limit(20)
        .offset(10)
        .all())

    # Aggregations
    product_count = await advanced_query.where("category", "electronics").count()

    # Bulk operations
    await advanced_query.where("price", 0).update({"active": False})

    # Complex aggregation pipeline (MongoDB-style, works across implementations)
    pipeline = [
        {"$match": {"active": True}},
        {"$group": {
            "_id": "$category",
            "count": {"$sum": 1},
            "avg_price": {"$avg": "$price"},
            "max_price": {"$max": "$price"}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    category_stats = await advanced_query.aggregate(pipeline)
```

### Hybrid Query Interface

The Hybrid Query Interface allows you to mix and match different query styles:

```python
async def hybrid_nosql_operations():
    # Start with repository pattern
    product_manager = query.for_model(Product)

    # Switch between styles as needed
    async with product_manager.transaction():
        # Use repository for domain logic
        active_products = await product_manager.repository().find_active()

        # Use specifications for complex business rules
        discount_spec = field("discount_percent").greater_than(20)
        discounted_products = await product_manager.specification.with_spec(discount_spec).all()

        # Use advanced queries for bulk operations
        await product_manager.advanced.where_in("id", [p.id for p in discounted_products]).update({
            "featured": True,
            "promotion_end": datetime.now() + timedelta(days=7)
        })

        # Use simple queries for basic operations
        new_product = await product_manager.simple.create({
            "name": "Limited Edition Item",
            "price": 99.99,
            "category": "special"
        })
```

## Traditional NoSQL Operations

### MongoDB Implementation

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the NoSQL adapter
NoSQL = import_adapter("nosql")
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
# Works identically to MongoDB
product = {
    "name": "Smartphone",
    "price": 699.99,
    "category": "electronics",
    "in_stock": True
}
product_id = await nosql.products.insert_one(product)

# Query documents
electronics = await nosql.products.find({"category": "electronics", "in_stock": True})
for item in electronics:
    print(f"Item: {item['name']}, Price: ${item['price']}")
```

### Redis Implementation

```python
# Redis works with the same interface
user = {
    "name": "Jane Smith",
    "email": "jane@example.com",
    "score": 95
}
user_id = await nosql.users.insert_one(user)

# Find and update
user = await nosql.users.find_one({"_id": user_id})
await nosql.users.update_one(
    {"_id": user_id},
    {"$set": {"score": 98}}
)
```

## Advanced Features

### Transactions

```python
# Universal transaction support across implementations
async with query.for_model(Product).transaction():
    # All operations are atomic
    await query.for_model(Product).simple.update("prod1", {"stock": 10})
    await query.for_model(Product).simple.update("prod2", {"stock": 5})
    # Automatically committed or rolled back

# Traditional transaction handling
async with nosql.transaction():
    await nosql.accounts.update_one(
        {"_id": "account1"},
        {"$set": {"balance": 900}}
    )
    await nosql.accounts.update_one(
        {"_id": "account2"},
        {"$set": {"balance": 1100}}
    )
```

### Aggregation Pipelines

```python
# MongoDB-style aggregation that works across implementations
pipeline = [
    {"$match": {"status": "active"}},
    {"$group": {
        "_id": "$category",
        "count": {"$sum": 1},
        "avg_price": {"$avg": "$price"}
    }},
    {"$sort": {"count": -1}}
]

# Works with universal query interface
categories = await query.for_model(Product).advanced.aggregate(pipeline)

# Or traditional approach
categories = await nosql.products.aggregate(pipeline)
```

### Querying with Models

```python
from pydantic import BaseModel, Field
from typing import Optional, List

# Define a model
class Product(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    name: str
    price: float
    category: str
    tags: List[str] = []
    in_stock: bool = True

# Use with universal query interface (automatic serialization/deserialization)
products = await query.for_model(Product).simple.all()
for product in products:
    print(f"Product: {product.name}, Price: ${product.price}")

# Traditional approach with manual conversion
result = await nosql.products.find_one({"_id": product_id})
product = Product(**result)
```

## Performance Considerations

### NoSQL Query Optimization

```python
# Use specifications for reusable queries
frequently_used_spec = field("status").equals("active") & field("verified").equals(True)

# Repository pattern provides automatic caching
repo = query.for_model(Product).repository(RepositoryOptions(cache_enabled=True))
products = await repo.find_by_specification(frequently_used_spec)  # Cached

# Efficient aggregation with universal interface
pipeline = [
    {"$match": {"category": "electronics"}},
    {"$group": {"_id": "$brand", "total_sales": {"$sum": "$sales"}}},
    {"$sort": {"total_sales": -1}},
    {"$limit": 10}
]
top_brands = await query.for_model(Product).advanced.aggregate(pipeline)
```

### Implementation Performance

| Implementation | Universal Query | Traditional NoSQL | Query Flexibility | Best For |
|----------------|----------------|-------------------|-------------------|----------|
| **MongoDB** | Excellent | Excellent | Very High | Complex documents, flexible schemas |
| **Firestore** | Excellent | Good | High | Real-time applications, mobile/web |
| **Redis** | Good | Excellent | Limited | Caching, simple structures |

## Related Adapters

The NoSQL adapter integrates seamlessly with other ACB adapters:

- [**Cache Adapter**](../cache/README.md): Use Redis for both caching and NoSQL operations
- [**SQL Adapter**](../sql/README.md): Combine SQL and NoSQL for hybrid data access patterns
- [**Models Adapter**](../models/README.md): Define Pydantic models for document validation
- [**Storage Adapter**](../storage/README.md): Store file metadata in NoSQL while storing files in object storage

## Additional Resources

- [Universal Query Interface Documentation](../../models/README.md)
- [Specification Pattern Examples](../../models/_specification.py)
- [Repository Pattern Examples](../../models/_repository.py)
- [MongoDB Documentation](https://docs.mongodb.com/manual/)
- [Beanie Documentation](https://beanie-odm.dev/)
- [Google Cloud Firestore Documentation](https://cloud.google.com/firestore/docs)
- [Redis Documentation](https://redis.io/documentation)
- [Redis-OM Documentation](https://redis.io/docs/latest/integrate/redisom-for-python/)
