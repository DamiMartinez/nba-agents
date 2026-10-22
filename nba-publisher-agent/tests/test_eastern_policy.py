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


def test_workflow_starts_at_eleven_ten_madrid_with_native_dst_support():
    workflow = Path(__file__).resolve().parents[2] / ".github/workflows/daily-agent.yml"
    text = workflow.read_text()
    assert "cron: '10 11 * * *'" in text
    assert "timezone: 'Europe/Madrid'" in text


def test_madrid_schedule_keeps_eastern_edition_date_in_all_dst_seasons():
    for day in ("2026-01-15", "2026-03-20", "2026-07-15", "2026-10-28"):
        scheduled = datetime.fromisoformat(day + "T11:10:00").replace(
            tzinfo=ZoneInfo("Europe/Madrid")
        )
        assert game_data.edition_date(scheduled).isoformat() == day
