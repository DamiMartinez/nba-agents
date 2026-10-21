import asyncio
import base64
import io
import wave
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import run_agent
from nba_publisher_agent import game_data
from nba_publisher_agent.tools import generate_podcast_audio_tool as audio_tool
from nba_publisher_agent.tools.upload_to_gcs_tool import upload_to_gcs


def test_wait_retries_only_pending_results(monkeypatch):
    collect = MagicMock(side_effect=[game_data.ResultsNotReady(), {"ready": True}])
    monkeypatch.setattr(run_agent, "collect_edition", collect)
    assert asyncio.run(
        run_agent.collect_with_wait(date(2026, 1, 2), attempts=2, delay=0)
    ) == {"ready": True}
    assert collect.call_count == 2


def test_wait_exhaustion(monkeypatch):
    monkeypatch.setattr(
        run_agent, "collect_edition", MagicMock(side_effect=game_data.ResultsNotReady())
    )
    with pytest.raises(game_data.ResultsNotReady):
        asyncio.run(run_agent.collect_with_wait(date(2026, 1, 2), attempts=2, delay=0))


def test_source_error_never_starts_llm(monkeypatch):
    monkeypatch.setattr(
        run_agent, "collect_with_wait", AsyncMock(side_effect=game_data.GameDataError())
    )
    runner = MagicMock()
    monkeypatch.setattr(run_agent, "Runner", runner)
    assert asyncio.run(run_agent.run_nba_agent(date(2026, 1, 2))) is False
    runner.assert_not_called()


def test_collect_only_no_llm(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    snapshot = {"results": {"total_games": 0, "date": "2026-01-01"}}
    monkeypatch.setattr(
        run_agent, "collect_with_wait", AsyncMock(return_value=snapshot)
    )
    runner = MagicMock()
    monkeypatch.setattr(run_agent, "Runner", runner)
    assert (
        asyncio.run(run_agent.run_nba_agent(date(2026, 1, 2), collect_only=True))
        is True
    )
    assert (tmp_path / "reports/nba_2026-01-02.json").exists()
    runner.assert_not_called()


def fake_tts(monkeypatch, encoded):
    create = AsyncMock(
        return_value=SimpleNamespace(output_audio=SimpleNamespace(data=encoded))
    )
    client = MagicMock()
    client.aio.__aenter__ = AsyncMock(
        return_value=SimpleNamespace(interactions=SimpleNamespace(create=create))
    )
    client.aio.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(audio_tool.genai, "Client", lambda **kwargs: client)
    return create


def test_tts_saves_wav_without_double_header(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        wav.writeframes(b"\x00\x00" * 100)
    encoded = base64.b64encode(buf.getvalue()).decode()
    create = fake_tts(monkeypatch, encoded)
    context = SimpleNamespace(
        state={
            "edition_date": "2026-01-02",
            "nba_edition": {"results": {"status": "ok"}},
        }
    )
    result = asyncio.run(audio_tool.generate_podcast_audio("Podcast script", context))
    assert result["status"] == "success"
    saved = tmp_path / "audios/nba_daily_summary_podcast_2026-01-02.wav"
    assert saved.read_bytes() == buf.getvalue()
    assert context.state["audio_generated"] is True
    assert create.call_args.kwargs["input"][0]["content"][0]["text"] == "Podcast script"


@pytest.mark.parametrize(
    "encoded", [None, "", "invalid-base64", base64.b64encode(b"not wav").decode()]
)
def test_bad_tts_never_sets_success(monkeypatch, encoded):
    fake_tts(monkeypatch, encoded)
    context = SimpleNamespace(state={"nba_edition": {"results": {"status": "ok"}}})
    result = asyncio.run(audio_tool.generate_podcast_audio("Podcast script", context))
    assert result["status"] == "error"
    assert not context.state["audio_generated"]
    assert not context.state["audio_uploaded"]


def test_interactive_audio_also_requires_ready_data(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(audio_tool.genai, "Client", client)
    monkeypatch.setattr(
        audio_tool,
        "collect_edition",
        MagicMock(side_effect=game_data.ResultsNotReady()),
    )
    context = SimpleNamespace(state={})
    assert (
        asyncio.run(audio_tool.generate_podcast_audio("Script", context))["status"]
        == "error"
    )
    client.assert_not_called()


def test_upload_rejects_other_files():
    context = SimpleNamespace(
        state={"audio_generated": True, "audio_file_path": "/expected.wav"}
    )
    assert upload_to_gcs("/other.wav", context)["status"] == "error"
    assert not context.state["audio_uploaded"]


def test_no_final_response_is_failure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    snapshot = {"results": {"total_games": 0, "date": "2026-01-01"}}
    monkeypatch.setattr(
        run_agent, "collect_with_wait", AsyncMock(return_value=snapshot)
    )

    async def no_events(**kwargs):
        if False:
            yield

    runner = SimpleNamespace(run_async=no_events, close=AsyncMock())
    monkeypatch.setattr(run_agent, "Runner", lambda **kwargs: runner)
    assert asyncio.run(run_agent.run_nba_agent(date(2026, 1, 2))) is False
