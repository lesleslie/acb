> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Models](./README.md)

# Models Adapter

The Models adapter provides a universal interface for database models in ACB applications, automatically detecting and handling multiple model frameworks within the same application.

## Overview

The ACB Models adapter offers intelligent model type detection and management:

- **Auto-Detection**: Automatically detects SQLModel, Pydantic, and Redis-OM models
- **Multi-Framework Support**: Use different model types in the same application
- **Universal Query Interface**: Works seamlessly with SQL and NoSQL adapters
- **Type-Safe Operations**: Full type safety with automatic adapter routing
- **Configuration-Driven**: Enable/disable specific model frameworks
- **Zero Configuration**: Works out-of-the-box with sensible defaults

## Supported Model Frameworks

| Framework | Description | Auto-Detection | Status |
|-----------|-------------|----------------|---------|
| **SQLModel** | SQL database models with Pydantic integration | ✅ `SQLModel` base class | ✅ Available |
| **SQLAlchemy** | Pure SQLAlchemy ORM models | ✅ `__table__` attribute or `DeclarativeMeta` | ✅ Available |
| **Pydantic** | Data validation and serialization models | ✅ `BaseModel` base class | ✅ Available |
| **msgspec** | High-performance serialization with validation | ✅ `msgspec.Struct` base class | ✅ Available |
| **attrs** | Mature attribute definition library | ✅ `attrs.has()` detection | ✅ Available |
| **Redis-OM** | Redis object mapping with hash models | ✅ `HashModel` base class | ✅ Available |

## Installation

```bash
# Install with Models support
uv add "acb[models]"

# Or include it with database dependencies
uv add "acb[models,sql,nosql]"

# Complete database stack
uv add "acb[models,sql,nosql,cache]"
```

## Configuration

### Adapter Configuration

Enable the Models adapter in your `settings/adapters.yml` file:

```yaml
# Enable the Models adapter (auto-detects model types)
models: true

# Models adapter works with SQL and NoSQL adapters
sql: pgsql
nosql: mongodb
cache: redis
```

### Model Framework Configuration

Configure which model frameworks are enabled in your `settings/models.yml` file:

```yaml
# Enable SQLModel support (default: true)
# Requires: sqlmodel
sqlmodel: true

# Enable SQLAlchemy support (default: true)
# Requires: sqlalchemy
sqlalchemy: true

# Enable Pydantic support (default: true)
# Requires: pydantic
pydantic: true

# Enable Redis-OM support (default: false)
# Requires: redis-om
redis_om: false

# Enable msgspec support (default: true)
# Requires: msgspec
msgspec: true

# Enable attrs support (default: false)
# Requires: attrs
attrs: false
```

### Advanced Settings

Additional settings can be customized in your `settings/app.yml` file:

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

### Auto-Detection in Action

The Models adapter automatically detects your model types and routes them to the appropriate internal handlers:

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the Models adapter
Models = import_adapter("models")
models = depends.get(Models)

# SQLModel automatically detected
from sqlmodel import Field, SQLModel

class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int = Field(default=None)
    is_active: bool = Field(default=True)

# SQLAlchemy automatically detected
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    price = Column(Integer)  # stored in cents
    in_stock = Column(Boolean, default=True)

# Pydantic automatically detected
from pydantic import BaseModel

class UserDTO(BaseModel):
    name: str
    email: str
    age: int

# msgspec automatically detected
import msgspec

class UserSession(msgspec.Struct):
    user_id: str
    token: str
    expires_at: int

# attrs automatically detected
import attrs

@attrs.define
class UserProfile:
    bio: str
    avatar_url: str

# Redis-OM automatically detected
from redis_om import HashModel

class UserCache(HashModel):
    user_id: str
    data: str

# All models work seamlessly with the universal query interface
print(models.auto_detect_model_type(User))        # "sqlmodel"
print(models.auto_detect_model_type(Product))     # "sqlalchemy"
print(models.auto_detect_model_type(UserDTO))     # "pydantic"
print(models.auto_detect_model_type(UserSession)) # "msgspec"
print(models.auto_detect_model_type(UserProfile)) # "attrs"
print(models.auto_detect_model_type(UserCache))   # "redis_om"
```

### Universal Query Interface

Use any model type with the universal query interface:

```python
from acb.adapters.models._query import QueryBuilder, registry
from acb.adapters.sql._query import SqlDatabaseAdapter
from acb.adapters.models._sqlmodel import SQLModelAdapter

# Register adapters for universal query interface
sql_adapter = SqlDatabaseAdapter()
model_adapter = SQLModelAdapter()

registry.register_database_adapter("sql", sql_adapter, is_default=True)
registry.register_model_adapter("sqlmodel", model_adapter, is_default=True)

# Create query builder
query_builder = registry.create_query_builder()

# Query with auto-detected model type
users = await query_builder.query(User).where("is_active", True).all()
active_users = await query_builder.query(User).where("age", ">", 18).limit(10).all()
```

### Traditional Database Operations

#### SQLModel with SQL Databases

```python
from sqlmodel import Field, SQLModel, select
from acb.depends import depends
from acb.adapters import import_adapter

# Models automatically detected as SQLModel
class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    age: int = Field(default=None)
    is_active: bool = Field(default=True)

# Use with SQL adapter
SQL = import_adapter("sql")
sql = depends.get(SQL)

async with sql.get_session() as session:
    # Create a new user
    new_user = User(name="John Doe", email="john@example.com", age=30)
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    # Query users
    statement = select(User).where(User.is_active == True)
    result = await session.execute(statement)
    users = result.scalars().all()
```

#### SQLAlchemy with SQL Databases

```python
from sqlalchemy import Column, Integer, String, Boolean, select
from sqlalchemy.orm import DeclarativeBase
from acb.depends import depends
from acb.adapters import import_adapter

# Models automatically detected as SQLAlchemy
class Base(DeclarativeBase):
    pass

class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    price = Column(Integer)  # stored in cents
    in_stock = Column(Boolean, default=True)
    category_id = Column(Integer)

# Use with SQL adapter
SQL = import_adapter("sql")
sql = depends.get(SQL)

async with sql.get_session() as session:
    # Create a new product
    new_product = Product(
        name="Awesome Widget",
        price=2999,  # $29.99 in cents
        in_stock=True,
        category_id=1
    )
    session.add(new_product)
    await session.commit()
    await session.refresh(new_product)

    # Query products using SQLAlchemy Core syntax
    statement = select(Product).where(Product.in_stock == True)
    result = await session.execute(statement)
    products = result.scalars().all()

    # Complex queries
    expensive_products = await session.execute(
        select(Product)
        .where(Product.price > 5000)
        .where(Product.in_stock == True)
        .order_by(Product.name)
    )
```

#### Pydantic with NoSQL Databases

```python
from pydantic import BaseModel, Field
from acb.depends import depends
from acb.adapters import import_adapter

# Models automatically detected as Pydantic
class Product(BaseModel):
    id: str = Field(default=None, alias="_id")
    name: str
    price: float
    in_stock: bool = True
    tags: list[str] = []

    class Config:
        collection_name = "products"

# Use with NoSQL adapter
NoSQL = import_adapter("nosql")
nosql = depends.get(NoSQL)

# Create a new product
new_product = Product(
    name="Widget Pro",
    price=19.99,
    tags=["electronics", "gadgets"]
)

# Save to database
product_id = await nosql.products.insert_one(new_product.model_dump())
new_product.id = str(product_id)

# Query products
products = await nosql.products.find({"in_stock": True, "price": {"$lt": 20}})
```

## Advanced Usage

### Mixed Model Types in One Application

```python
from sqlmodel import Field, SQLModel
from pydantic import BaseModel
from acb.depends import depends
from acb.adapters import import_adapter

Models = import_adapter("models")
models = depends.get(Models)

# SQL model for persistent data
class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    created_at: datetime = Field(default_factory=datetime.now)

# Pydantic model for API DTOs
class UserCreateRequest(BaseModel):
    name: str
    email: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

# Auto-detection routes to appropriate adapters
print(models.auto_detect_model_type(User))              # "sqlmodel"
print(models.auto_detect_model_type(UserCreateRequest)) # "pydantic"
print(models.auto_detect_model_type(UserResponse))      # "pydantic"

# Get the right adapter for each model type
user_adapter = models.get_adapter_for_model(User)
dto_adapter = models.get_adapter_for_model(UserCreateRequest)
```

### Model Relationships

```python
from sqlmodel import Field, Relationship, SQLModel
from typing import List, Optional

# SQLModel relationships automatically detected
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

# Both models automatically detected as SQLModel
adapter = models.get_adapter_for_model(Author)
print(adapter.is_relationship_field(Author, "books"))  # True
print(adapter.get_nested_model_class(Author, "books")) # <class 'Book'>
```

### Custom Model Validation

```python
from sqlmodel import Field, SQLModel
from datetime import datetime

class Order(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    customer_id: int
    total_amount: float
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "pending"

    # Custom validation method
    def calculate_tax(self, tax_rate: float = 0.1) -> float:
        return self.total_amount * tax_rate

    # Custom business logic
    def mark_as_complete(self) -> None:
        self.status = "completed"

# Automatic detection and validation
adapter = models.get_adapter_for_model(Order)
order_data = {
    "customer_id": 123,
    "total_amount": 99.99,
    "status": "pending"
}

# Validate data using the auto-detected adapter
validated_data = adapter.validate_data(Order, order_data)
```

## Redis-OM Integration (Coming Soon)

When Redis-OM support is implemented, it will work seamlessly with auto-detection:

```python
# Future Redis-OM support
from redis_om import HashModel

class UserSession(HashModel):
    user_id: str
    token: str
    expires_at: datetime

    class Meta:
        database = redis_client

# Will be automatically detected as "redis_om"
adapter = models.get_adapter_for_model(UserSession)
```

## Advanced Framework Examples

### msgspec for High-Performance Applications

```python
import msgspec
from typing import Any

class HighThroughputEvent(msgspec.Struct):
    event_id: str
    user_id: str
    event_type: str
    timestamp: int
    data: dict[str, Any]

# Extremely fast serialization/deserialization
adapter = models.get_adapter_for_model(HighThroughputEvent)
event_data = {
    "event_id": "evt_123",
    "user_id": "usr_456",
    "event_type": "click",
    "timestamp": 1640995200,
    "data": {"page": "/home"}
}
validated = adapter.validate_data(HighThroughputEvent, event_data)
```

### attrs for Enterprise Applications

```python
import attrs
from typing import Optional

@attrs.define
class EnterpriseUser:
    employee_id: str = attrs.field(metadata={"primary_key": True})
    department: str
    role: str
    manager_id: Optional[str] = None
    salary_band: str = attrs.field(metadata={"alias": "band"})

# Rich metadata support
adapter = models.get_adapter_for_model(EnterpriseUser)
print(adapter.get_primary_key_field(EnterpriseUser))  # "employee_id"
print(adapter.get_field_mapping(EnterpriseUser))      # {"salary_band": "band", ...}
```

## Troubleshooting

### Common Issues

1. **Model Type Not Detected**
   - **Problem**: `Models adapter defaults to 'pydantic' for unknown types`
   - **Solution**: Ensure your model inherits from the correct base class (SQLModel, BaseModel, etc.)

2. **Framework Not Available**
   - **Problem**: `ImportError: SQLModel is required for SQLModelAdapter`
   - **Solution**: Install the required framework: `uv add sqlmodel` or `uv add pydantic`

3. **Framework Disabled**
   - **Problem**: Model framework not working despite correct base class
   - **Solution**: Check `settings/models.yml` to ensure the framework is enabled

4. **Auto-Detection Issues**
   - **Problem**: Wrong adapter selected for model
   - **Solution**: Manually specify adapter: `adapter = models._get_sqlmodel_adapter()`

### Configuration Troubleshooting

1. **Settings File Not Found**
   - **Problem**: `FileNotFoundError: settings/models.yml`
   - **Solution**: Create the file or use default settings (all frameworks enabled)

2. **Invalid Configuration**
   - **Problem**: `ValidationError in models settings`
   - **Solution**: Ensure boolean values in `models.yml`: `sqlmodel: true` not `sqlmodel: "true"`

## Implementation Details

The Models adapter uses an intelligent routing system:

```python
class ModelsAdapter(ModelsBase):
    def auto_detect_model_type(self, model_class: type) -> str:
        """Auto-detect the model type based on the class."""
        # Check for SQLModel first (it's also a Pydantic model and SQLAlchemy model)
        if issubclass(model_class, SQLModel):
            return "sqlmodel"

        # Check for pure SQLAlchemy models (before Pydantic)
        if (hasattr(model_class, "__table__") or
            (hasattr(model_class, "__mro__") and
             any(isinstance(base, DeclarativeMeta) for base in model_class.__mro__))):
            return "sqlalchemy"

        # Check for Pydantic BaseModel
        if issubclass(model_class, BaseModel):
            return "pydantic"

        # Check for Redis-OM HashModel
        if issubclass(model_class, HashModel):
            return "redis_om"

        # Check for msgspec Struct
        if issubclass(model_class, msgspec.Struct):
            return "msgspec"

        # Check for attrs classes
        if attrs.has(model_class):
            return "attrs"

        # Default fallback
        return "pydantic"

    def get_adapter_for_model(self, model_class: type):
        """Get the appropriate adapter for a model class."""
        model_type = self.auto_detect_model_type(model_class)

        if model_type == "sqlmodel":
            return self._get_sqlmodel_adapter()
        elif model_type == "sqlalchemy":
            return self._get_sqlalchemy_adapter()
        elif model_type == "pydantic":
            return self._get_pydantic_adapter()
        elif model_type == "redis_om":
            return self._get_redis_om_adapter()
        elif model_type == "msgspec":
            return self._get_msgspec_adapter()
        elif model_type == "attrs":
            return self._get_attrs_adapter()
```

### Internal Architecture

- **`_pydantic.py`**: Internal Pydantic model adapter
- **`_sqlmodel.py`**: Internal SQLModel adapter
- **`_sqlalchemy.py`**: Internal SQLAlchemy ORM adapter
- **`_redis_om.py`**: Internal Redis-OM adapter
- **`_msgspec.py`**: Internal msgspec adapter
- **`_attrs.py`**: Internal attrs adapter
- **`_query.py`**: Universal query interface protocols
- **`_repository.py`**: Repository pattern implementation
- **`_specification.py`**: Specification pattern implementation

## Additional Resources

- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Redis-OM Documentation](https://redis.io/docs/stack/search/object-mapping/)
- [ACB SQL Adapter](../sql/README.md)
- [ACB NoSQL Adapter](../nosql/README.md)
- [ACB Universal Query Interface](./examples/query_interface_demo.py)
- [ACB Adapters Overview](../README.md)
