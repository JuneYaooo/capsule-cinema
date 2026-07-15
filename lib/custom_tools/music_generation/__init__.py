"""Optional local-only music generators.

The public runtime accepts user-provided or capsule-packaged audio. A local
registry may expose an additional generator without publishing its adapter.
"""

from importlib import import_module

__all__: list[str] = []


def __getattr__(name: str):
    from src.config_registry import load_tool_registry

    module_path = (load_tool_registry().get(name) or {}).get("module")
    if not module_path:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value
