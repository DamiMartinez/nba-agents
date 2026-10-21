import json
from datetime import date, timedelta

from google.adk.tools.tool_context import ToolContext

from ..game_data import edition_date, results_for


def get_last_night_results(tool_context: ToolContext) -> str:
    """Return the previous Eastern-date slate, with Eastern times and explicit status."""
    snapshot = tool_context.state.get("nba_edition")
    if snapshot:
        return json.dumps(snapshot["results"], indent=2)
    day = date.fromisoformat(
        tool_context.state.get("edition_date", edition_date().isoformat())
    )
    return json.dumps(results_for(day - timedelta(days=1)), indent=2)
