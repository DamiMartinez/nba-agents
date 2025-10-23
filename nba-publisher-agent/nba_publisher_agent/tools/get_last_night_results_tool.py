from nba_api.live.nba.endpoints import scoreboard
from google.adk.tools.tool_context import ToolContext
import json

def get_last_night_results(tool_context: ToolContext) -> str:
    """
    A tool that gets the last night's NBA games results in json format.
    """
    sb_json = json.loads(scoreboard.ScoreBoard().get_json())
    return json.dumps(sb_json['scoreboard']['games'], indent=2)