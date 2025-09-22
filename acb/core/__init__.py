"""ACB Core Infrastructure.

This module contains essential infrastructure components used by ACB adapters:
- SSL/TLS configuration
- Simple resource cleanup
"""

from .cleanup import CleanupMixin
from .ssl_config import SSLConfigMixin

__all__ = [
    "CleanupMixin",
    "SSLConfigMixin",
]
