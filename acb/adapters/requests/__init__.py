"""Requests adapters for ACB.

This module provides HTTP client adapters with RFC 9111 compliant caching
using ACB's configured cache backend.
"""

from ._base import RequestsBase, RequestsBaseSettings
from .httpx import Requests as HttpxRequests
from .httpx import RequestsSettings as HttpxRequestsSettings
from .niquests import Requests as NiquestsRequests
from .niquests import RequestsSettings as NiquestsRequestsSettings

__all__ = [
    "HttpxRequests",
    "HttpxRequestsSettings",
    "NiquestsRequests",
    "NiquestsRequestsSettings",
    "RequestsBase",
    "RequestsBaseSettings",
]
