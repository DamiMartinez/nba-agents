"""Explicit, overridable model IDs (not moving 'latest' aliases)."""

import os

AGENT_MODEL = os.environ.get("NBA_AGENT_MODEL", "gemini-3.8-flash")
TTS_MODEL = os.environ.get("NBA_TTS_MODEL", "gemini-3.8-flash-tts")
TTS_VOICE = os.environ.get("NBA_TTS_VOICE", "Rasalgethi")
