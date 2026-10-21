from unittest.mock import MagicMock

import pytest
import requests

from nba_publisher_agent.game_data import fetch_game_details


def game():
    return {
        "game_id": "123",
        "home": {"id": "h", "score": 100},
        "away": {"id": "a", "score": 106},
    }


def summary():
    return {
        "header": {
            "id": "123",
            "competitions": [
                {
                    "competitors": [
                        {"id": "h", "score": "100"},
                        {"id": "a", "score": "106"},
                    ]
                }
            ],
        },
        "boxscore": {
            "players": [
                {
                    "team": {"id": "a", "displayName": "Away"},
                    "statistics": [
                        {
                            "labels": ["PTS", "REB", "AST"],
                            "athletes": [
                                {
                                    "athlete": {"displayName": "Player"},
                                    "stats": ["14", "9", "7"],
                                },
                                {"athlete": {"displayName": "Inactive"}, "stats": []},
                            ],
                        }
                    ],
                }
            ]
        },
        "article": {"story": "<p>Player had six assists &amp; a win.</p>"},
    }


def response(monkeypatch, payload):
    result = MagicMock()
    result.json.return_value = payload
    monkeypatch.setattr(requests, "get", MagicMock(return_value=result))
    return result


def test_boxscore_retained_over_conflicting_recap(monkeypatch):
    response(monkeypatch, summary())
    details = fetch_game_details(game())
    assert details["details_status"] == "ok"
    assert details["player_stats"][0]["statistics"]["AST"] == "7"
    assert "six assists" in details["recap"]
    assert "override" in details["statistics_policy"]
    assert "<p>" not in details["recap"]
    assert len(details["player_stats"]) == 1


@pytest.mark.parametrize("invalid", ["id", "score", "team", "labels", "missing"])
def test_invalid_summary_omits_unverified_detail(monkeypatch, invalid):
    value = summary()
    if invalid == "id":
        value["header"]["id"] = "other"
    elif invalid == "score":
        value["header"]["competitions"][0]["competitors"][0]["score"] = "99"
    elif invalid == "team":
        value["boxscore"]["players"][0]["team"]["id"] = "other"
    elif invalid == "labels":
        value["boxscore"]["players"][0]["statistics"][0]["labels"] = ["PTS"]
    else:
        value = {}
    response(monkeypatch, value)
    details = fetch_game_details(game())
    assert details["details_status"] == "unavailable"
    assert details["player_stats"] == []
    assert details["recap"] == ""


def test_detail_timeout_preserves_scoreboard_result(monkeypatch):
    monkeypatch.setattr(requests, "get", MagicMock(side_effect=requests.Timeout()))
    details = fetch_game_details(game())
    assert details["details_status"] == "unavailable"
    assert details["details_error"] == "Timeout"
