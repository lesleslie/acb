"""Project-wide runtime tweaks loaded by Python at startup.

Currently forces urllib3 clients (e.g. pip-audit via requests) to avoid
opportunistic HTTP/3 upgrades that intermittently fail against some
vulnerability APIs. Set ``ACB_HTTP3_DISABLE=0`` to opt back in.
"""

from __future__ import annotations

import os

from typing import Any

_PATCH_FLAG = "_acb_http3_patch"
_HTTP3_SENTINEL = None


def _should_disable_http3() -> bool:
    raw_value = os.environ.get("ACB_HTTP3_DISABLE", "1").strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


def _with_h3_disabled(values: dict[str, Any]) -> dict[str, Any]:
    sentinel = _HTTP3_SENTINEL
    if sentinel is None:
        return values

    disabled = values.get("disabled_svn")
    disabled_set = set(disabled or ())
    disabled_set.add(sentinel)
    values["disabled_svn"] = disabled_set
    return values


def _patch_init(cls: type) -> None:
    original_init = getattr(cls, "__init__", None)
    if original_init is None or getattr(original_init, _PATCH_FLAG, False):
        return

    def wrapped(self, *args: Any, **kwargs: Any) -> None:
        kwargs = dict(kwargs)
        _with_h3_disabled(kwargs)
        original_init(self, *args, **kwargs)

    setattr(wrapped, _PATCH_FLAG, True)
    cls.__init__ = wrapped  # type: ignore[assignment]


if _should_disable_http3():
    try:
        from urllib3 import connectionpool, poolmanager
        from urllib3.backend import HttpVersion
    except Exception:
        pass
    else:
        _HTTP3_SENTINEL = HttpVersion.h3
        for _candidate in (
            poolmanager.PoolManager,
            connectionpool.HTTPConnectionPool,
            connectionpool.HTTPSConnectionPool,
        ):
            _patch_init(_candidate)
