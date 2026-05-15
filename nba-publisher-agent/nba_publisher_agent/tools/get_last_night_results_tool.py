from nba_api.stats.endpoints import leaguegamelog
from google.adk.tools.tool_context import ToolContext
from datetime import date, timedelta
import json

def get_last_night_results(tool_context: ToolContext) -> str:
    """
    A tool that gets last night's NBA games results in json format.
    """
    yesterday = (date.today() - timedelta(days=1)).strftime('%m/%d/%Y')

    today = date.today()
    season_year = str(today.year if today.month >= 10 else today.year - 1)

    games = []
    matched_season_type = None
    for season_type in ['Playoffs', 'Regular Season']:
        try:
            log = leaguegamelog.LeagueGameLog(
                season=season_year,
                season_type_all_star=season_type,
                date_from_nullable=yesterday,
                date_to_nullable=yesterday,
            )
            data = log.get_dict()['resultSets'][0]
            rows = data['rowSet']
            if rows:
                headers = data['headers']
                games = [dict(zip(headers, row)) for row in rows]
                matched_season_type = season_type
                break
        except Exception:
            continue

    return json.dumps({
        'date': yesterday,
        'season_type': matched_season_type,
        'games': games,
    }, indent=2)