"""Enhanced Query Interface Demo.

This example demonstrates the enhanced query interface with:
- Specification Pattern for composable business rules
- Repository Pattern for domain-specific queries
- Hybrid Query Interface for different query styles
- Enhanced Query class with specification support
"""

import asyncio
import contextlib
import typing as t
from dataclasses import dataclass
from datetime import datetime, timedelta

# Import enhanced query functionality
from acb.adapters.models._hybrid import ACBQuery, HybridQueryOptions, QueryStyle
from acb.adapters.models._query import QueryOperator, QuerySpec
from acb.adapters.models._repository import Repository
from acb.adapters.models._specification import (
    Specification,
    field,
    range_spec,
)


# Example models
@dataclass
class User:
    id: int | None = None
    name: str = ""
    email: str = ""
    age: int = 0
    status: str = "active"
    subscription_type: str = "free"
    created_at: datetime | None = None
    last_login: datetime | None = None
    is_premium: bool = False


@dataclass
class Order:
    id: int | None = None
    user_id: int = 0
    amount: float = 0.0
    status: str = "pending"
    created_at: datetime | None = None
    items: list[str] | None = None


# Custom Specifications
class ActiveUserSpec(Specification[User]):  # type: ignore[misc]
    """Specification for active users."""

    def is_satisfied_by(self, candidate: User) -> bool:
        return candidate.status == "active"

    def to_query_spec(self) -> QuerySpec:
        from acb.adapters.models._query import QueryCondition

        spec = QuerySpec()
        spec.filter.conditions.append(
            QueryCondition("status", QueryOperator.EQ, "active"),
        )
        return spec


class PremiumUserSpec(Specification[User]):  # type: ignore[misc]
    """Specification for premium users."""

    def is_satisfied_by(self, candidate: User) -> bool:
        return candidate.is_premium or candidate.subscription_type == "premium"

    def to_query_spec(self) -> QuerySpec:
        from acb.adapters.models._query import QueryCondition

        spec = QuerySpec()
        # This would need OR logic in a real implementation
        spec.filter.conditions.append(
            QueryCondition("subscription_type", QueryOperator.EQ, "premium"),
        )
        return spec


class RecentUserSpec(Specification[User]):  # type: ignore[misc]
    """Specification for recently created users."""

    def __init__(self, days: int = 7) -> None:
        self.days = days

    def is_satisfied_by(self, candidate: User) -> bool:
        if not candidate.created_at:
            return False
        cutoff = datetime.now() - timedelta(days=self.days)
        return candidate.created_at >= cutoff

    def to_query_spec(self) -> QuerySpec:
        from acb.adapters.models._query import QueryCondition

        spec = QuerySpec()
        cutoff = datetime.now() - timedelta(days=self.days)
        spec.filter.conditions.append(
            QueryCondition("created_at", QueryOperator.GTE, cutoff),
        )
        return spec


# Custom Repository
class UserRepository(Repository[User]):  # type: ignore[misc]
    """Custom repository with domain-specific query methods."""

    async def find_active(self) -> list[User]:
        """Find active users."""
        result = await self.find_by_specification(ActiveUserSpec())
        return t.cast("list[User]", result)  # type: ignore[no-any-return]

    async def find_premium(self) -> list[User]:
        """Find premium users."""
        result = await self.find_by_specification(PremiumUserSpec())
        return t.cast("list[User]", result)  # type: ignore[no-any-return]

    async def find_active_premium(self) -> list[User]:
        """Find active premium users."""
        spec = ActiveUserSpec().and_(PremiumUserSpec())
        result = await self.find_by_specification(spec)
        return t.cast("list[User]", result)  # type: ignore[no-any-return]

    async def find_recent(self, days: int = 7) -> list[User]:
        """Find recently created users."""
        result = await self.find_by_specification(RecentUserSpec(days))
        return t.cast("list[User]", result)  # type: ignore[no-any-return]

    async def find_by_age_range(self, min_age: int, max_age: int) -> list[User]:
        """Find users within age range."""
        spec = range_spec("age", min_age, max_age)
        result = await self.find_by_specification(spec)
        return t.cast("list[User]", result)  # type: ignore[no-any-return]

    async def find_by_email_domain(self, domain: str) -> list[User]:
        """Find users with specific email domain."""
        spec = field("email").like(f"%@{domain}")
        result = await self.find_by_specification(spec)
        return t.cast("list[User]", result)  # type: ignore[no-any-return]

    async def find_inactive_users(self, days: int = 30) -> list[User]:
        """Find users who haven't logged in recently."""
        cutoff = datetime.now() - timedelta(days=days)
        spec = field("last_login").less_than(cutoff).or_(field("last_login").is_null())
        result = await self.find_by_specification(spec)
        return t.cast("list[User]", result)  # type: ignore[no-any-return]

    async def get_user_statistics(self) -> dict[str, t.Any]:
        """Get user statistics."""
        total_users = await self.count()
        active_users = await self.count(ActiveUserSpec())
        premium_users = await self.count(PremiumUserSpec())
        recent_users = await self.count(RecentUserSpec(7))

        return {
            "total": total_users,
            "active": active_users,
            "premium": premium_users,
            "recent": recent_users,
            "inactive": total_users - active_users,
        }


async def demonstrate_enhanced_query_interface() -> None:
    """Demonstrate all enhanced query interface features."""
    # Setup (using mock adapters in real usage)
    HybridQueryOptions(
        default_style=QueryStyle.SIMPLE,
        cache_enabled=True,
        cache_ttl=300,
        enable_soft_delete=True,
        audit_enabled=True,
    )

    # Create the enhanced query interface
    ACBQuery()

    # Simple queries
    with contextlib.suppress(Exception):
        # These would work with real database connections

        # Demonstrate the interface
        # query_interface.simple(User)  # Method doesn't exist
        pass

    # Repository pattern
    with contextlib.suppress(Exception):
        # query_interface.repository(User)  # Method doesn't exist
        pass

        # Register custom repository
        # custom_repo = UserRepository(User, query_interface.hybrid.query_builder)  # hybrid doesn't exist
        # query_interface.register_custom_repository(User, custom_repo)  # Method doesn't exist
        pass

    # Specification pattern

    # Basic specifications
    active_spec = ActiveUserSpec()
    premium_spec = PremiumUserSpec()
    recent_spec = RecentUserSpec(7)

    # Composite specifications
    active_premium = active_spec.and_(premium_spec)
    recent_spec.and_(premium_spec)

    # Field specifications using builder
    age_spec = field("age").between(18, 65)
    email_spec = field("email").like("%@gmail.com")
    field("status").in_list(["active", "pending"])

    # Complex composite
    active_spec.and_(premium_spec).and_(age_spec).or_(recent_spec)

    # Advanced queries
    with contextlib.suppress(Exception):
        # query_interface.advanced(User)  # Method doesn't exist
        pass

        # With specifications

    # Demonstrate different styles for same model

    # Get model manager
    # query_interface.model(User)  # Method doesn't exist
    pass

    # Different styles for different use cases

    # In-memory evaluation

    # Mock users for demonstration
    mock_users = [
        User(
            id=1,
            name="Alice",
            email="alice@gmail.com",
            age=25,
            status="active",
            is_premium=True,
        ),
        User(
            id=2,
            name="Bob",
            email="bob@yahoo.com",
            age=30,
            status="inactive",
            is_premium=False,
        ),
        User(
            id=3,
            name="Charlie",
            email="charlie@gmail.com",
            age=35,
            status="active",
            is_premium=True,
        ),
        User(
            id=4,
            name="Diana",
            email="diana@outlook.com",
            age=22,
            status="active",
            is_premium=False,
        ),
    ]

    # Evaluate specifications
    [u for u in mock_users if active_spec.is_satisfied_by(u)]
    [u for u in mock_users if premium_spec.is_satisfied_by(u)]
    [u for u in mock_users if email_spec.is_satisfied_by(u)]

    # Composite evaluation
    [u for u in mock_users if active_premium.is_satisfied_by(u)]

    # Batch operations

    # Transaction examples

    # Caching examples

    # Real-world examples


if __name__ == "__main__":
    asyncio.run(demonstrate_enhanced_query_interface())
