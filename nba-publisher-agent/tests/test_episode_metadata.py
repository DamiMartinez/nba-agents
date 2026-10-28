"""Editorial metadata validation and fail-closed publication."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nba_publisher_agent.tools.set_episode_metadata_tool import set_episode_metadata
from nba_publisher_agent.tools import upload_to_gcs_tool as upload_tool
from test_publication import upload_context


@pytest.mark.parametrize(
    "title,description",
    [
        ("Too short", "D" * 200),
        ("T" * 111, "D" * 200),
        ("T" * 20 + "\n", "short"),
        ("A valid title\nwith another line", "D" * 200),
        ("T" * 20, "D" * 1001),
    ],
)
def test_invalid_copy_clears_stale_metadata(title, description):
    context = SimpleNamespace(
        state={"edition_date": "2026-01-02", "episode_metadata": {"old": True}}
    )
    assert set_episode_metadata(title, description, context)["status"] == "error"
    assert "episode_metadata" not in context.state


@pytest.mark.parametrize("metadata", [None, {"edition_date": "2026-01-01"}])
def test_upload_requires_current_metadata(monkeypatch, tmp_path, metadata):
    context, audio = upload_context(tmp_path)
    context.state["episode_metadata"] = metadata
    client = MagicMock()
    monkeypatch.setattr(upload_tool.storage, "Client", client)
    assert upload_tool.upload_to_gcs(str(audio), context)["status"] == "error"
    client.assert_not_called()


def test_sidecar_failure_blocks_success(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    credentials = tmp_path / "credentials.json"
    credentials.write_text("{}")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(credentials))
    context, audio = upload_context(tmp_path)
    client = MagicMock()
    client.bucket.return_value.blob.return_value.upload_from_string.side_effect = (
        RuntimeError()
    )
    monkeypatch.setattr(upload_tool.storage, "Client", lambda: client)
    assert upload_tool.upload_to_gcs(str(audio), context)["status"] == "error"
    assert context.state["audio_uploaded"] is False
