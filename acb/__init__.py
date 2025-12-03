from inspect import currentframe

import typing as t
from anyio import Path as AsyncPath
from contextlib import suppress
from rich import box
from rich.padding import Padding
from rich.table import Table

from acb.console import Console
from acb.depends import Inject, depends

# Re-exports for backward compatibility
from .actions import _ensure_action_registry_initialized, action_registry
from .adapters import get_adapters
from .context import get_context

__all__ = [
    "ACMCPServer",
    "Console",
    "Inject",
    "PerformanceOptimizer",
    "ServiceBase",
    "ServiceRegistry",
    "action_registry",
    "create_mcp_server",
    "depends",
    "display_components",
    "ensure_registration",
    "ensure_registration_async",
    "get_adapters",
    "get_context",
    "register_pkg",
    "setup_services",
    "shutdown_services_layer",
]

# Services layer imports
try:
    from .services import (
        PerformanceOptimizer as PerformanceOptimizer,
    )
    from .services import (
        ServiceBase as ServiceBase,
    )
    from .services import (
        ServiceRegistry as ServiceRegistry,
    )
    from .services import (
        setup_services as setup_services,
    )
    from .services import (
        shutdown_services_layer as shutdown_services_layer,
    )

    HAS_SERVICES = True
except ImportError:
    HAS_SERVICES = False
    ServiceBase = None  # type: ignore
    ServiceRegistry = None  # type: ignore
    PerformanceOptimizer = None  # type: ignore
    setup_services = None  # type: ignore
    shutdown_services_layer = None  # type: ignore

# MCP Server imports
try:
    from .mcp import ACMCPServer as ACMCPServer
    from .mcp import create_mcp_server as create_mcp_server

    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    ACMCPServer = None  # type: ignore
    create_mcp_server = None  # type: ignore


def register_pkg(name: str | None = None, path: AsyncPath | None = None) -> None:
    """Register a package with ACB.

    Args:
        name: Package name (optional, will be inferred from caller if not provided)
        path: Package path (optional, will be inferred from caller if not provided)
    """
    ctx = get_context()

    if name is None or path is None:
        # Fallback to frame inspection only if arguments not provided
        frame = currentframe()
        if frame is not None and frame.f_back is not None:
            inferred_path = AsyncPath(frame.f_back.f_code.co_filename).parent
            inferred_name = inferred_path.stem
        else:
            msg = "Could not determine caller frame and no explicit name/path provided"
            raise RuntimeError(msg)

        name = name or inferred_name
        path = path or inferred_path

    # Use async-safe context method - register immediately to queue
    ctx._lazy_registration_queue.append((name, path))


async def ensure_registration() -> None:
    """Ensure all packages are registered."""
    ctx = get_context()
    await ctx.ensure_registration()


# Backward compatibility alias
async def ensure_registration_async() -> None:
    """Backward compatibility alias for ensure_registration."""
    await ensure_registration()


table_args: dict[str, t.Any] = {
    "show_lines": True,
    "box": box.ROUNDED,
    "min_width": 100,
    "border_style": "bold blue",
}


async def display_components() -> None:
    """Public-facing function to display components."""
    await _display_components()


@depends.inject
async def _display_components(console: Inject[Console]) -> None:
    """Display registered components in a formatted table."""
    ctx = get_context()
    await ensure_registration()

    if not ctx.is_deployed():
        _display_packages_table(ctx, console)
        _display_actions_table(console)
        _display_adapters_table(console)
        _display_services_table(console)


def _display_packages_table(ctx: t.Any, console: Console) -> None:
    """Display packages table."""
    pkgs = Table(
        title="[b][u bright_white]A[/u bright_white][bright_green]synchronous [u bright_white]C[/u bright_white][bright_green]omponent [u bright_white]B[/u bright_white][bright_green]ase[/b]",
        **table_args,
    )
    for prop in ("Pkg", "Path"):
        pkgs.add_column(prop)
    for i, pkg in enumerate(ctx.pkg_registry.get()):
        pkgs.add_row(
            pkg.name,
            str(pkg.path),
            style="bold white" if i % 2 else "bold white on blue",
        )
    pkgs_padded = Padding(pkgs, (2, 4, 0, 4))
    console.print(pkgs_padded)


def _display_actions_table(console: Console) -> None:
    """Display actions table."""
    actns = Table(
        title="[b][u bright_white]A[/u bright_white][bright_green]ctions",
        **table_args,
    )
    for prop in ("Name", "Pkg", "Methods"):
        actns.add_column(prop)
    for i, action in enumerate(_ensure_action_registry_initialized()):
        actns.add_row(
            action.name,
            action.pkg,
            ", ".join(action.methods),
            style="bold white" if i % 2 else "bold white on blue",
        )
    actns_padded = Padding(actns, (0, 4, 1, 4))
    console.print(actns_padded)


def _display_adapters_table(console: Console) -> None:
    """Display adapters table."""
    adptrs = Table(
        title="[b][u bright_white]A[/u bright_white][bright_green]datpters",
        **table_args,
    )
    for prop in ("Category", "Name", "Pkg"):
        adptrs.add_column(prop)
    for i, adapter in enumerate(get_adapters()):
        adptrs.add_row(
            adapter.category,
            adapter.name,
            adapter.pkg,
            style="bold white" if i % 2 else "bold white on blue",
        )
    adptrs_padded = Padding(adptrs, (0, 4, 1, 4))
    console.print(adptrs_padded)


def _display_services_table(console: Console) -> None:
    """Display services table if available."""
    if not HAS_SERVICES:
        return

    with suppress(Exception):
        from .services import get_registry

        registry = get_registry()
        service_ids = registry.list_services()

        srvcs = Table(
            title="[b][u bright_white][bright_green]Services[/bright_green][/u bright_white]",
            **table_args,
        )
        for prop in ("Service ID", "Name", "Status"):
            srvcs.add_column(prop)

        for i, service_id in enumerate(service_ids):
            _add_service_row(srvcs, registry, service_id, i)

        srvcs_padded = Padding(srvcs, (0, 4, 1, 4))
        console.print(srvcs_padded)


def _add_service_row(
    table: Table,
    registry: t.Any,
    service_id: str,
    index: int,
) -> None:
    """Add a service row to the table."""
    try:
        service = registry.get_service(service_id)
        table.add_row(
            service_id,
            service.name,
            service.status.value,
            style="bold white" if index % 2 else "bold white on blue",
        )
    except Exception:
        table.add_row(
            service_id,
            "Unknown",
            "error",
            style="bold white" if index % 2 else "bold white on blue",
        )
