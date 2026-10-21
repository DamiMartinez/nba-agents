"""Generate WAV audio using the Gemini 3.8 Interactions TTS API."""

import asyncio
import base64
import io
import pathlib
import wave
from datetime import date

from google import genai
from google.adk.tools.tool_context import ToolContext

from ..config import TTS_MODEL, TTS_VOICE
from ..game_data import collect_edition, edition_date


async def generate_podcast_audio(
    summary_report: str, tool_context: ToolContext
) -> dict:
    """Generate the edition's podcast; refuse publication without complete game data."""
    tool_context.state["audio_generated"] = False
    tool_context.state["audio_uploaded"] = False
    try:
        day = tool_context.state.get("edition_date", edition_date().isoformat())
        if not tool_context.state.get("nba_edition"):
            tool_context.state["nba_edition"] = await asyncio.to_thread(
                collect_edition, date.fromisoformat(day)
            )
        results = tool_context.state["nba_edition"]["results"]
        if results.get("status") != "ok" or results.get("unresolved_game_ids"):
            raise ValueError("Cannot generate audio from incomplete results")
        if not summary_report.strip():
            raise ValueError("Podcast script is empty")
        reports = pathlib.Path.cwd() / "reports"
        reports.mkdir(exist_ok=True)
        (reports / f"nba_{day}.script.txt").write_text(summary_report, encoding="utf-8")
        tool_context.state["podcast_script"] = summary_report
        async with genai.Client(http_options={"timeout": 180_000}).aio as client:
            interaction = await client.interactions.create(
                model=TTS_MODEL,
                input=[
                    {
                        "type": "user_input",
                        "content": [
                            {
                                "type": "text",
                                "text": summary_report,
                                "annotations": [
                                    {
                                        "type": "speech_metadata",
                                        "style": "Engaging, informative sports podcast narration",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                response_format={"type": "audio", "mime_type": "audio/wav"},
                generation_config={"speech_config": [{"voice": TTS_VOICE}]},
            )
        audio = interaction.output_audio
        if not audio or not audio.data:
            raise ValueError("TTS returned no audio")
        data = base64.b64decode(audio.data, validate=True)
        # Unary 3.8 TTS already returns a WAV container; don't wrap it in another.
        with wave.open(io.BytesIO(data), "rb") as wav:
            if not wav.getnframes():
                raise ValueError("TTS returned empty WAV audio")
        directory = pathlib.Path.cwd() / "audios"
        directory.mkdir(exist_ok=True)
        file_path = directory / f"nba_daily_summary_podcast_{day}.wav"
        file_path.write_bytes(data)
        tool_context.state["audio_generated"] = True
        tool_context.state["audio_file_path"] = str(file_path.resolve())
        return {
            "status": "success",
            "file_path": str(file_path.resolve()),
            "file_size": len(data),
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Audio generation failed ({type(exc).__name__})",
        }
