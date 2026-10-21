from datetime import datetime

from google.adk.tools.tool_context import ToolContext

from ..game_data import EASTERN, edition_date


def get_current_date_tool(tool_context: ToolContext) -> str:
    """Return the frozen edition date and an explicitly zoned current timestamp."""
    day = tool_context.state.get("edition_date", edition_date().isoformat())
    tool_context.state["edition_date"] = day
    now = datetime.now(EASTERN)
    return f"Edition: {day} (America/New_York); current time: {now.isoformat()} ({now.tzname()}, Eastern Time)"
