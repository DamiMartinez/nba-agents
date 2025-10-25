import wave
from typing import Dict
import pathlib

from google.adk.tools.tool_context import ToolContext
from google import genai
from google.genai import types
from datetime import datetime


def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    """Helper function to save audio data as a wave file"""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)
        

async def generate_podcast_audio(summary_report: str, tool_context: ToolContext) -> Dict[str, str]:
    """
    Generates audio from a podcast script using Gemini API and saves it as a WAV file.
    The filename is automatically generated based on the current date in the format:
    nba_daily_summary_podcast_YYYY-MM-DD.wav

    Args:
        summary_report: The summary report to be converted to audio.
        tool_context: The ADK tool context.

    Returns:
        Dictionary with status and file information.
    """
    try:
        client = genai.Client()
        prompt = f"TTS the following summary report narrated by Rasalgethi:\n\n{summary_report}"

        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name='Rasalgethi',
                        )
                    )
                )
            )
        )

        data = response.candidates[0].content.parts[0].inline_data.data

        # Generate deterministic filename based on current date
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename = f"nba_daily_summary_podcast_{current_date}.wav"

        current_directory = pathlib.Path.cwd()
        audios_directory = current_directory / "audios"
        
        # Create audios directory if it doesn't exist
        audios_directory.mkdir(exist_ok=True)
        
        file_path = audios_directory / filename
        wave_file(str(file_path), data)

        return {
            "status": "success",
            "message": f"Successfully generated and saved podcast audio to {file_path.resolve()}",
            "file_path": str(file_path.resolve()),
            "file_size": len(data)
        }

    except Exception as e:
        error_msg = str(e)[:200]
        return {"status": "error", "message": f"Audio generation failed: {error_msg}"}