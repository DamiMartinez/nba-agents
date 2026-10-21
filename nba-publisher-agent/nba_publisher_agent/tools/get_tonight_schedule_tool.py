import json
from datetime import date

from google.adk.tools.tool_context import ToolContext

from ..game_data import edition_date, fetch_slate


def get_tonight_schedule_tool(tool_context: ToolContext) -> str:
    """Return the edition's Eastern-date slate with all game times in New York time."""
    snapshot = tool_context.state.get("nba_edition")
    if snapshot:
        return json.dumps(snapshot["schedule"], indent=2)
    day = date.fromisoformat(
        tool_context.state.get("edition_date", edition_date().isoformat())
    )
    slate = fetch_slate(day)
    slate["status"] = "ok"
    return json.dumps(slate, indent=2)
