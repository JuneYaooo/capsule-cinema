"""Compatibility shim for tools copied from video_workflow.

The current video-agent runtime uses CrewAI's BaseTool directly, while newer
video_workflow tools import custom_tools.base_tool.BaseTool. Keeping this tiny
shim avoids editing those copied tools.
"""

from crewai.tools import BaseTool

__all__ = ["BaseTool"]
