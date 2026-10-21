from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from nba_publisher_agent import game_data as data


def event(
    game_id="1",
    start="2026-01-02T03:30Z",
    *,
    state="post",
    status="STATUS_FINAL",
    completed=True,
    season=2
):
    return {
        "id": game_id,
        "season": {"year": 2026, "type": season},
        "competitions": [
            {
                "date": start,
                "timeValid": True,
                "status": {
                    "type": {"name": status, "state": state, "completed": completed}
                },
                "competitors": [
                    {
                        "id": "a",
                        "homeAway": "away",
                        "score": "110",
                        "team": {"displayName": "Away"},
                    },
                    {
                        "id": "h",
                        "homeAway": "home",
                        "score": "112",
                        "team": {"displayName": "Home"},
                        "leaders": [
                            {
                                "name": "points",
                                "leaders": [
                                    {"athlete": {"displayName": "Scorer"}, "value": 35}
                                ],
                            }
                        ],
                    },
                ],
            }
        ],
    }


def source(monkeypatch, payloads):
    session = MagicMock()
    session.__enter__.return_value = session
    responses = []
    for payload in payloads:
        response = MagicMock()
        response.json.return_value = payload
        responses.append(response)
    session.get.side_effect = responses
    monkeypatch.setattr(data.requests, "Session", lambda: session)
    return session


def payload(*events):
    return {"leagues": [{"abbreviation": "NBA"}], "events": list(events)}


@pytest.mark.parametrize(
    "instant, expected",
    [
        ("2026-01-01T23:30+00:00", "2026-01-01"),
        ("2026-07-01T22:30+00:00", "2026-07-01"),
        ("2026-01-01T08:00+09:00", "2025-12-31"),
        ("2026-01-02T04:59+00:00", "2026-01-01"),
        ("2026-01-02T05:00+00:00", "2026-01-02"),
        ("2026-07-02T03:59+00:00", "2026-07-01"),
        ("2026-07-02T04:00+00:00", "2026-07-02"),
    ],
)
def test_edition_uses_new_york_not_host(instant, expected):
    assert data.edition_date(datetime.fromisoformat(instant)).isoformat() == expected


def test_naive_clock_rejected():
    with pytest.raises(ValueError):
        data.edition_date(datetime(2026, 1, 1))


@pytest.mark.parametrize(
    "start, eastern, abbreviation",
    [
        ("2026-01-02T03:30Z", "2026-01-01T22:30:00-05:00", "EST"),
        ("2026-07-02T02:30Z", "2026-07-01T22:30:00-04:00", "EDT"),
        # Europe changes clocks on different dates: it must have no effect.
        ("2026-03-15T02:30Z", "2026-03-14T22:30:00-04:00", "EDT"),
        ("2026-10-28T02:30Z", "2026-10-27T22:30:00-04:00", "EDT"),
        # New York spring-forward and repeated fall-back hour.
        ("2026-03-08T06:59Z", "2026-03-08T01:59:00-05:00", "EST"),
        ("2026-03-08T07:00Z", "2026-03-08T03:00:00-04:00", "EDT"),
        ("2026-11-01T05:30Z", "2026-11-01T01:30:00-04:00", "EDT"),
        ("2026-11-01T06:30Z", "2026-11-01T01:30:00-05:00", "EST"),
    ],
)
def test_eastern_display_and_dst(start, eastern, abbreviation):
    game = data._normalize(event(start=start))
    assert game["start_time_eastern"] == eastern
    assert game["time_zone_abbreviation"] == abbreviation
    assert game["league_date"] == eastern[:10]
    assert "start_time_madrid" not in game


def test_adjacent_dates_deduplicate_and_filter_eastern_day(monkeypatch):
    early = event("early", "2026-01-01T18:00Z")  # 13:00 EST
    west = event("west", "2026-01-02T03:30Z")  # 22:30 EST, despite next UTC date
    boundary = event("boundary", "2026-01-02T04:59Z")
    next_day = event("next", "2026-01-02T05:00Z")  # midnight ET excluded
    previous = event("previous", "2026-01-01T04:59Z")
    session = source(
        monkeypatch,
        [
            payload(previous, early),
            payload(early, west),
            payload(west, boundary, next_day),
        ],
    )
    slate = data.fetch_slate(date(2026, 1, 1))
    assert [g["game_id"] for g in slate["games"]] == ["early", "west", "boundary"]
    assert slate["queried_dates"] == ["20251231", "20260101", "20260102"]
    assert slate["display_timezone"] == slate["league_timezone"] == "America/New_York"
    assert session.get.call_count == 3
    assert slate["games"][1]["top_scorers"][0]["points"] == 35
    assert slate["games"][1]["home"]["score"] == 112


@pytest.mark.parametrize("season", [1, 2, 3, 5])
def test_no_season_type_filter(monkeypatch, season):
    source(monkeypatch, [payload(), payload(event(season=season)), payload()])
    assert len(data.fetch_slate(date(2026, 1, 1))["games"]) == 1


def test_empty_slate_is_explicit_success(monkeypatch):
    source(monkeypatch, [payload()] * 3)
    slate = data.results_for(date(2026, 1, 1))
    assert slate["status"] == "ok"
    assert slate["total_games"] == 0


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"events": []},
        {"leagues": [{"abbreviation": "NFL"}], "events": []},
        payload({"id": "bad"}),
    ],
)
def test_bad_payload_never_becomes_no_games(monkeypatch, bad):
    source(monkeypatch, [bad])
    with pytest.raises(data.GameDataError):
        data.fetch_slate(date(2026, 1, 1))


def test_partial_query_failure_is_not_success(monkeypatch):
    session = source(monkeypatch, [payload(event())])
    session.get.side_effect = [session.get.side_effect.__next__(), requests.Timeout()]
    with pytest.raises(data.GameDataError):
        data.fetch_slate(date(2026, 1, 1))


@pytest.mark.parametrize(
    "state, status",
    [
        ("in", "STATUS_IN_PROGRESS"),
        ("pre", "STATUS_SCHEDULED"),
        ("in", "STATUS_DELAYED"),
    ],
)
def test_unfinished_game_blocks_edition(monkeypatch, state, status):
    source(
        monkeypatch,
        [
            payload(),
            payload(event(state=state, status=status, completed=False)),
            payload(),
        ],
    )
    with pytest.raises(data.ResultsNotReady):
        data.collect_edition(date(2026, 1, 2))


@pytest.mark.parametrize(
    "status", ["STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED"]
)
def test_postponed_cancelled_remain_visible(monkeypatch, status):
    source(
        monkeypatch,
        [payload(), payload(event(status=status, completed=False)), payload()]
        + [payload()] * 3,
    )
    edition = data.collect_edition(date(2026, 1, 2))
    assert edition["results"]["total_games"] == 1
    assert edition["results"]["completed_games"] == 0
    assert edition["schedule"]["date"] == "2026-01-02"


def test_missing_final_score_fails(monkeypatch):
    bad = event()
    del bad["competitions"][0]["competitors"][0]["score"]
    source(monkeypatch, [payload(bad)])
    with pytest.raises(data.GameDataError):
        data.fetch_slate(date(2026, 1, 1))


def test_missing_timestamp_timezone_fails(monkeypatch):
    source(monkeypatch, [payload(event(start="2026-01-02T03:30"))])
    with pytest.raises(data.GameDataError):
        data.fetch_slate(date(2026, 1, 1))


def test_tools_share_frozen_snapshot():
    import json
    from nba_publisher_agent.tools.get_last_night_results_tool import (
        get_last_night_results,
    )
    from nba_publisher_agent.tools.get_tonight_schedule_tool import (
        get_tonight_schedule_tool,
    )

    snapshot = {
        "results": {"games": ["frozen-result"]},
        "schedule": {"games": ["frozen-schedule"]},
    }
    context = SimpleNamespace(state={"nba_edition": snapshot})
    assert json.loads(get_last_night_results(context)) == snapshot["results"]
    assert json.loads(get_tonight_schedule_tool(context)) == snapshot["schedule"]
