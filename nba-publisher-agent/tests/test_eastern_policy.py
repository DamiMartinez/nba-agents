from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from nba_publisher_agent import game_data
from nba_publisher_agent.agent import root_agent
from nba_publisher_agent.tools import get_current_date_tool as clock_tool


def test_date_tool_freezes_new_york_date_across_midnight(monkeypatch):
    class Clock:
        instant = datetime.fromisoformat("2026-01-02T04:59:00+00:00")

        @classmethod
        def now(cls, tz):
            return cls.instant.astimezone(tz)

    monkeypatch.setattr(clock_tool, "datetime", Clock)
    monkeypatch.setattr(
        clock_tool, "edition_date", lambda: game_data.edition_date(Clock.instant)
    )
    context = SimpleNamespace(state={})
    first = clock_tool.get_current_date_tool(context)
    assert "Edition: 2026-01-01" in first
    assert "America/New_York" in first
    assert "EST" in first
    Clock.instant = datetime.fromisoformat("2026-01-02T05:01:00+00:00")
    second = clock_tool.get_current_date_tool(context)
    assert "Edition: 2026-01-01" in second
    assert context.state["edition_date"] == "2026-01-01"


def test_narration_policy_uses_only_eastern_game_times():
    assert "start_time_eastern" in root_agent.instruction
    assert "All times are Eastern" in root_agent.instruction
    assert "America/New_York" in root_agent.instruction
    assert "start_time_madrid" not in root_agent.instruction
    assert "Europe/Madrid" not in root_agent.instruction


def test_workflow_supports_external_dispatch_without_builtin_schedule():
    workflow = Path(__file__).resolve().parents[2] / ".github/workflows/daily-agent.yml"
    text = workflow.read_text()
    assert "workflow_dispatch:" in text
    assert "edition_date:" in text
    assert "\n  schedule:" not in text
    assert "cron:" not in text


def test_external_caller_timezone_does_not_choose_edition_date():
    for instant, zone, expected in (
        ("2026-01-02T00:30:00", "Europe/Madrid", "2026-01-01"),
        ("2026-07-02T00:30:00", "Europe/Madrid", "2026-07-01"),
        ("2026-11-01T06:30:00", "UTC", "2026-11-01"),
    ):
        called_at = datetime.fromisoformat(instant).replace(tzinfo=ZoneInfo(zone))
        assert game_data.edition_date(called_at).isoformat() == expected
