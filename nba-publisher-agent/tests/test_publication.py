import asyncio
import hashlib
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.adk.sessions.state import State
from google.genai.types import Content, Part

import run_agent
from nba_publisher_agent.tools import generate_podcast_audio_tool as audio_tool
from nba_publisher_agent.tools import upload_to_gcs_tool as upload_tool
from nba_publisher_agent.tools.set_episode_metadata_tool import set_episode_metadata


def upload_context(tmp_path):
    audio = tmp_path / "nba_daily_summary_podcast_2026-01-02.wav"
    audio.write_bytes(b"audio fixture")
    context = SimpleNamespace(
        state=State(
            {
                "edition_date": "2026-01-02",
                "audio_generated": True,
                "audio_file_path": str(audio),
            },
            {},
        )
    )
    assert (
        set_episode_metadata(
            "Boston edges New York in a tense NBA finish",
            "Boston and New York deliver a close basketball finish worth revisiting. "
            "Our NBA results recap explores the verified highlights and the rest of the night's games. "
            "Then catch the upcoming matchups with tip-off times in Eastern Time.",
            context,
        )["status"]
        == "success"
    )
    return context, audio


def test_audio_rejects_incomplete_snapshot(monkeypatch):
    context = SimpleNamespace(
        state={"nba_edition": {"results": {"status": "incomplete"}}}
    )
    client = MagicMock()
    monkeypatch.setattr(audio_tool.genai, "Client", client)
    assert (
        asyncio.run(audio_tool.generate_podcast_audio("Script", context))["status"]
        == "error"
    )
    client.assert_not_called()


@pytest.mark.parametrize("uploaded", [True, False])
def test_runner_requires_confirmed_upload(monkeypatch, tmp_path, uploaded):
    monkeypatch.chdir(tmp_path)
    snapshot = {"results": {"total_games": 1, "date": "2026-01-01"}}
    monkeypatch.setattr(
        run_agent, "collect_with_wait", AsyncMock(return_value=snapshot)
    )
    service = SimpleNamespace(
        create_session=AsyncMock(),
        get_session=AsyncMock(
            return_value=SimpleNamespace(
                state={"audio_uploaded": uploaded, "summary_report": "Report"}
            )
        ),
    )
    monkeypatch.setattr(run_agent, "InMemorySessionService", lambda: service)

    async def events(**kwargs):
        yield SimpleNamespace(
            is_final_response=lambda: True,
            author=run_agent.root_agent.name,
            content=Content(parts=[Part(text="Done")]),
        )

    runner = SimpleNamespace(run_async=events, close=AsyncMock())
    monkeypatch.setattr(run_agent, "Runner", lambda **kwargs: runner)
    assert asyncio.run(run_agent.run_nba_agent(date(2026, 1, 2))) is uploaded
    assert (tmp_path / "reports/nba_2026-01-02.md").exists() is uploaded
    assert (
        service.create_session.call_args.kwargs["state"]["edition_date"] == "2026-01-02"
    )
    runner.close.assert_awaited_once()


def test_upload_success_sets_state(monkeypatch, tmp_path):
    path = tmp_path / "credentials.json"
    path.write_text("{}")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(path))
    client = MagicMock()
    monkeypatch.setattr(upload_tool.storage, "Client", lambda: client)
    monkeypatch.chdir(tmp_path)
    context, audio = upload_context(tmp_path)
    result = upload_tool.upload_to_gcs(str(audio), context)
    assert result["status"] == "success"
    assert context.state["audio_uploaded"] is True
    client.bucket.return_value.blob.return_value.upload_from_filename.assert_called_once_with(
        str(audio)
    )
    sidecar = json.loads(
        client.bucket.return_value.blob.return_value.upload_from_string.call_args.args[
            0
        ]
    )
    assert sidecar["title"] == context.state["episode_metadata"]["title"]
    assert sidecar["audio_sha256"] == hashlib.sha256(audio.read_bytes()).hexdigest()
    assert (tmp_path / "reports/nba_2026-01-02.metadata.json").exists()


def test_failed_upload_does_not_report_success(monkeypatch, tmp_path):
    path = tmp_path / "credentials.json"
    path.write_text("{}")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(path))
    client = MagicMock()
    client.bucket.return_value.blob.return_value.make_public.side_effect = RuntimeError(
        "sensitive upstream body"
    )
    monkeypatch.setattr(upload_tool.storage, "Client", lambda: client)
    monkeypatch.chdir(tmp_path)
    context, audio = upload_context(tmp_path)
    result = upload_tool.upload_to_gcs(str(audio), context)
    assert result["status"] == "error"
    assert context.state["audio_uploaded"] is False
    assert "sensitive upstream body" not in result["message"]
