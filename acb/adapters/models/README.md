Error - Could not find the file by path /Users/les/Projects/acb/acb/adapters/models/README.md for qodo_structured_read_files> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Models](./README.md)

# Models Adapter

The Models adapter provides a standardized interface for database models in ACB applications, supporting both SQL and NoSQL database access patterns.

## Overview

The ACB Models adapter offers a consistent way to define and use data models:

- Unified model definition for SQL and NoSQL databases
- Type-safe data access with Pydantic integration
- Automatic schema creation and validation
- Integration with SQLModel for SQL databases
- Separation of data models from database access code

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **SQLModel** | SQL database models using SQLModel | Applications using SQL databases |

## Installation

```bash
# Install with Models support
pdm add "acb[models]"

# Or include it with SQL dependencies
pdm add "acb[models,sql]"

# Complete database stack
pdm add "acb[models,sql,nosql]"
```

## Configuration

### Settings

Configure the Models adapter in your `settings/adapters.yml` file:

```yaml
# Use SQLModel implementation
models: sqlmodel

# Models adapter usually works with SQL and NoSQL adapters
sql: pgsql
nosql: mongodb
```

### Models Settings

The Models adapter settings can be customized in your `settings/app.yml` file:

```yaml
models:
  # Schema naming convention
  schema_naming: "snake_case"

  # Default table schema
  default_schema: "public"

  # Table naming convention
  table_naming: "plural"

  # Enable model validation
  validate: true
```

## Basic Usage

### SQL Models

```python
from sqlmodel import Field, SQLModel
from acb.depends import depends
from acb.adapters import import_adapter

# Import the Models adapter
Models = import_adapter("models")
models = depends.get(Models)

# Define a SQL model
class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int = Field(default=None)
    is_active: bool = Field(default=True)

# Register the model with ACB
models.sql.User = User

# Now you can use it with the SQL adapter
SQL = import_adapter("sql")
sql = depends.get(SQL)

async with sql.get_session() as session:
    # Create a new user
    new_user = User(name="John Doe", email="john@example.com", age=30)
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    # Query users
    from sqlmodel import select
    statement = select(User).where(User.is_active == True)
    result = await session.execute(statement)
    users = result.scalars().all()
```

### NoSQL Models

```python
from pydantic import BaseModel, Field
from acb.depends import depends
from acb.adapters import import_adapter

# Import the Models adapter
Models = import_adapter("models")
models = depends.get(Models)

# Define a NoSQL model
class Product(BaseModel):
    id: str = Field(default=None)
    name: str
    price: float
    in_stock: bool = True
    tags: list[str] = []

# Register the model with ACB
models.nosql.Product = Product

# Now you can use it with the NoSQL adapter
NoSQL = import_adapter("nosql")
nosql = depends.get(NoSQL)

# Create a new product
new_product = Product(
    name="Widget Pro",
    price=19.99,
    tags=["electronics", "gadgets"]
)

# Save to database
product_id = await nosql.products.insert_one(new_product.dict())
new_product.id = str(product_id)

# Query products
products = await nosql.products.find({"in_stock": True, "price": {"$lt": 20}})
```

## Advanced Usage

### Relationships in SQL Models

```python
from sqlmodel import Field, Relationship, SQLModel
from typing import List, Optional
from acb.depends import depends
from acb.adapters import import_adapter

Models = import_adapter("models")
models = depends.get(Models)

# Define models with relationships
class Author(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    bio: Optional[str] = None

    # Relationship to books
    books: List["Book"] = Relationship(back_populates="author")

class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    year: int

    # Foreign key
    author_id: int = Field(foreign_key="author.id")

    # Relationship to author
    author: Author = Relationship(back_populates="books")

# Register models
models.sql.Author = Author
models.sql.Book = Book
```

### Custom Model Methods

```python
from sqlmodel import Field, SQLModel
from datetime import datetime
from acb.depends import depends
from acb.adapters import import_adapter

Models = import_adapter("models")
models = depends.get(Models)

# Define a model with custom methods
class Order(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    customer_id: int
    total_amount: float
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "pending"

    # Custom method to calculate tax
    def calculate_tax(self, tax_rate: float = 0.1) -> float:
        return self.total_amount * tax_rate

    # Custom method to mark as complete
    def mark_as_complete(self) -> None:
        self.status = "completed"

# Register the model
models.sql.Order = Order
```

## Troubleshooting

### Common Issues

1. **Model Not Found**
   - **Problem**: `AttributeError: 'SqlModels' object has no attribute 'User'`
   - **Solution**: Ensure you've registered your model with `models.sql.User = User`

2. **Table Creation Failed**
   - **Problem**: `SQLAlchemyError: Error creating tables`
   - **Solution**: Check your model definitions and database connection

3. **Validation Error**
   - **Problem**: `ValidationError: value is not a valid integer`
   - **Solution**: Ensure data matches the model's field types and constraints

4. **Relationship Issues**
   - **Problem**: `SQLAlchemyError: Could not determine relationship direction`
   - **Solution**: Properly define both sides of relationships with `back_populates`

## Implementation Details

The Models adapter organizes models into SQL and NoSQL categories:

```python
class ModelsBase:
    class SqlModels:
        # SQL models are registered here
        User = None
        Product = None
        Order = None
        # ...

    sql = SqlModels()

    class NosqlModels:
        # NoSQL models are registered here
        User = None
        Product = None
        Order = None
        # ...

    nosql = NosqlModels()
```

## Additional Resources

- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [Pydantic Documentation](https://pydantic-docs.helpmanual.io/)
- [ACB SQL Adapter](../sql/README.md)
- [ACB NoSQL Adapter](../nosql/README.md)
- [ACB Adapters Overview](../README.md)
