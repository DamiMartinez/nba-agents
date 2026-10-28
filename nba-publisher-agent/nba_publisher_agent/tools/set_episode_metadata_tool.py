"""Store editorial copy separately from the spoken podcast script."""

from datetime import date

from google.adk.tools.tool_context import ToolContext


def set_episode_metadata(
    title: str, description: str, tool_context: ToolContext
) -> dict:
    """Save a verified story-led title and description for the current edition.

    Call after drafting the narration, before handing it to the podcaster.
    Neither field is spoken by TTS. Facts must come from that narration.
    """
    tool_context.state.pop("episode_metadata", None)
    day = tool_context.state.get("edition_date", "")
    try:
        date.fromisoformat(day)
        title = title.strip()
        description = description.strip()
        if not 20 <= len(title) <= 110 or "\n" in title or "\r" in title:
            raise ValueError("Title must be a single line of 20–110 characters")
        if not 200 <= len(description) <= 1000:
            raise ValueError("Description must contain 200–1000 characters")
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    metadata = {
        "edition_date": day,
        "title": title,
        "description": description,
    }
    tool_context.state["episode_metadata"] = metadata
    return {"status": "success", **metadata}
