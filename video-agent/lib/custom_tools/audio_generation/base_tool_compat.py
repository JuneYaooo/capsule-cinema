"""Compatibility wrapper for optional CrewAI BaseTool imports.

The local runtime is normally executed with Python 3.12, but some lightweight
helpers are imported from the system ``python3`` as well. Older Python versions
can fail while importing CrewAI before a tool even reaches provider code. For
plain ``_run`` calls, a minimal BaseTool shim is sufficient.
"""

from __future__ import annotations


try:
    from crewai.tools import BaseTool as BaseTool  # type: ignore
except Exception:  # noqa: BLE001

    class BaseTool:  # type: ignore[no-redef]
        name: str = ""
        description: str = ""
        args_schema = None

        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs
