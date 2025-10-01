import typing as t
from contextlib import suppress
from inspect import currentframe

# Rich.repr import removed - not used in refactored code
from anyio import Path as AsyncPath
from rich import box
from rich.padding import Padding
from rich.table import Table

# Re-exports for backward compatibility
from .actions import Action as Action
from .actions import action_registry
from .adapters import Adapter as Adapter
from .adapters import get_adapters
from .console import console
from .context import Pkg as Pkg
from .context import get_context

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

if t.TYPE_CHECKING:
    from rich.console import RenderableType


def register_pkg(name: str | None = None, path: AsyncPath | None = None) -> None:
    """Register a package with ACB.

    Args:
        name: Package name (optional, will be inferred from caller if not provided)
        path: Package path (optional, will be inferred from caller if not provided)
    """
    context = get_context()

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
    context._lazy_registration_queue.append((name, path))


async def ensure_registration() -> None:
    """Ensure all packages are registered."""
    context = get_context()
    await context.ensure_registration()


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
    """Display registered components in a formatted table."""
    context = get_context()
    await ensure_registration()

    if not context.is_deployed():
        pkgs = Table(
            title="[b][u bright_white]A[/u bright_white][bright_green]synchronous [u bright_white]C[/u bright_white][bright_green]omponent [u bright_white]B[/u bright_white][bright_green]ase[/b]",
            **table_args,
        )
        for prop in ("Pkg", "Path"):
            pkgs.add_column(prop)
        for i, pkg in enumerate(context.pkg_registry.get()):
            pkgs.add_row(
                pkg.name,
                str(pkg.path),
                style="bold white" if i % 2 else "bold white on blue",
            )
        pkgs_padded: RenderableType = Padding(pkgs, (2, 4, 0, 4))
        console.print(pkgs_padded)
        actns = Table(
            title="[b][u bright_white]A[/u bright_white][bright_green]ctions",
            **table_args,
        )
        for prop in ("Name", "Pkg", "Methods"):
            actns.add_column(prop)
        for i, action in enumerate(action_registry.get()):
            actns.add_row(
                action.name,
                action.pkg,
                ", ".join(action.methods),
                style="bold white" if i % 2 else "bold white on blue",
            )
        actns_padded: RenderableType = Padding(actns, (0, 4, 1, 4))
        console.print(actns_padded)
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
        adptrs_padded: RenderableType = Padding(adptrs, (0, 4, 1, 4))
        console.print(adptrs_padded)

        # Display services if available
        if HAS_SERVICES:
            with suppress(Exception):
                from .services import get_registry

                registry = get_registry()
                service_ids = registry.list_services()

                srvcs = Table(
                    title="[b][u bright_white]S[/u bright_white][bright_green]ervices",  # codespell:ignore
                    **table_args,
                )
                for prop in ("Service ID", "Name", "Status"):
                    srvcs.add_column(prop)

                for i, service_id in enumerate(service_ids):
                    try:
                        service = registry.get_service(service_id)
                        srvcs.add_row(
                            service_id,
                            service.name,
                            service.status.value,
                            style="bold white" if i % 2 else "bold white on blue",
                        )
                    except Exception:
                        srvcs.add_row(
                            service_id,
                            "Unknown",
                            "error",
                            style="bold white" if i % 2 else "bold white on blue",
                        )

                srvcs_padded: RenderableType = Padding(srvcs, (0, 4, 1, 4))
                console.print(srvcs_padded)
