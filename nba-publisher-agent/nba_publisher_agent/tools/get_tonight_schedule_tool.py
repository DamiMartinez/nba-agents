import requests
import json
from datetime import datetime
from google.adk.tools.tool_context import ToolContext


def get_tonight_schedule_tool(tool_context: ToolContext) -> str:
    """
    A tool that gets tonight's NBA games schedule from the NBA API.
    Returns the schedule data in JSON format.
    """
    try:
        # Get current date in the format required by the API (MM/DD/YYYY)
        current_date = datetime.now().strftime("%m/%d/%Y")
        
        # NBA API endpoint for international broadcaster schedule
        url = "https://stats.nba.com/stats/internationalbroadcasterschedule"
        
        # Parameters for the API request
        params = {
            "LeagueID": "00",
            "Season": "2025",
            "RegionID": 1,
            "Date": current_date,
            "EST": "Y"
        }
        
        # Headers to mimic a browser request (NBA API sometimes blocks requests without proper headers)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nba.com/",
            "Connection": "keep-alive"
        }
        
        # Make the API request
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse and return the JSON response
        schedule_data = response.json()
        
        # Return the full response as a JSON string
        return json.dumps(schedule_data, indent=2)
        
    except requests.exceptions.RequestException as e:
        return json.dumps({
            "error": "Failed to fetch NBA schedule",
            "message": str(e),
            "date": current_date
        })
    except Exception as e:
        return json.dumps({
            "error": "Unexpected error occurred",
            "message": str(e),
            "date": current_date
        })
