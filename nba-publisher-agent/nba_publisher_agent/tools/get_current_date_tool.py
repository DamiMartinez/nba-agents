from google.adk.tools.tool_context import ToolContext
from datetime import datetime


def get_current_date_tool(tool_context: ToolContext) -> str:
    """
    A tool that gets the current date.
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    return current_date