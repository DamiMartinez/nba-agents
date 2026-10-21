"""Date-safe NBA scoreboard collection, independent of the host timezone.

An edition dated D in America/New_York covers Eastern calendar date D-1
for results and D for the upcoming slate. All displayed dates/times are also
Eastern; UTC timestamps are retained only for internal source auditing.
"""

import html
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

EASTERN = ZoneInfo("America/New_York")
SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
)


class GameDataError(RuntimeError):
    """The source did not provide a trustworthy, complete response."""


class ResultsNotReady(GameDataError):
    """Some games in the results slate have not finished yet."""


def edition_date(now: datetime | None = None) -> date:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("An aware datetime is required")
    return now.astimezone(EASTERN).date()


def _timestamp(value: str) -> datetime:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Source timestamp has no timezone")
    return stamp.astimezone(timezone.utc)


def _normalize(event: dict) -> dict:
    competition = event["competitions"][0]
    start = _timestamp(competition["date"])
    status = competition["status"]["type"]
    teams = {}
    leaders = []
    for team in competition["competitors"]:
        side = team["homeAway"]
        teams[side] = {
            "id": team["id"],
            "name": team["team"]["displayName"],
            "score": int(team["score"]) if team.get("score") is not None else None,
        }
        for category in team.get("leaders", []):
            if category["name"] == "points":
                for leader in category.get("leaders", []):
                    leaders.append(
                        {
                            "team": teams[side]["name"],
                            "player": leader["athlete"]["displayName"],
                            "points": leader["value"],
                        }
                    )
    if set(teams) != {"home", "away"}:
        raise ValueError("Expected one home and one away team")
    if status["completed"] and any(t["score"] is None for t in teams.values()):
        raise ValueError("Final game has no score")
    return {
        "game_id": str(event["id"]),
        "league_date": start.astimezone(EASTERN).date().isoformat(),
        "start_time_utc": start.isoformat(),
        "start_time_eastern": start.astimezone(EASTERN).isoformat(),
        "time_zone_abbreviation": start.astimezone(EASTERN).tzname(),
        "time_confirmed": competition.get("timeValid", True),
        "season": event.get("season"),
        "status": status["name"],
        "status_detail": status.get("detail", status.get("description", "")),
        "state": status["state"],
        "completed": status["completed"],
        "home": teams["home"],
        "away": teams["away"],
        "top_scorers": leaders,
    }


def fetch_slate(day: date) -> dict:
    """Query adjacent source dates, then filter by the actual Eastern tip date.

    Adjacent queries cover UTC/provider date boundaries. A failed query or bad
    event fails the whole collection: neither is evidence of an empty slate.
    """
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=False,
    )
    games = {}
    queried_dates = []
    try:
        with requests.Session() as session:
            session.mount("https://", HTTPAdapter(max_retries=retries))
            for offset in (-1, 0, 1):
                query_day = (day + timedelta(days=offset)).strftime("%Y%m%d")
                queried_dates.append(query_day)
                response = session.get(
                    SCOREBOARD_URL,
                    params={"dates": query_day, "limit": 1000},
                    timeout=(5, 30),
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload.get("events"), list) or not any(
                    league.get("abbreviation") == "NBA" for league in payload["leagues"]
                ):
                    raise ValueError("Invalid NBA scoreboard response")
                for event in payload["events"]:
                    game = _normalize(event)
                    if game["league_date"] == day.isoformat():
                        games[game["game_id"]] = game
    except (
        requests.RequestException,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
    ) as exc:
        raise GameDataError(
            f"Unable to collect NBA slate for {day}: {type(exc).__name__}"
        ) from exc
    return {
        "date": day.isoformat(),
        "league_timezone": EASTERN.key,
        "display_timezone": EASTERN.key,
        "source": SCOREBOARD_URL,
        "queried_dates": queried_dates,
        "fetched_at": datetime.now(EASTERN).isoformat(),
        "games": sorted(
            games.values(), key=lambda g: (g["start_time_utc"], g["game_id"])
        ),
    }


def fetch_game_details(game: dict) -> dict:
    """Attach structured box scores; never let stale prose override player stats.

    Details are optional editorial enrichment. If unavailable, keep the verified
    scoreboard result and explicitly prohibit unsupported additional statistics.
    """
    url = SCOREBOARD_URL.removesuffix("scoreboard") + "summary"
    try:
        response = requests.get(url, params={"event": game["game_id"]}, timeout=(5, 30))
        response.raise_for_status()
        payload = response.json()
        header = payload["header"]
        if str(header["id"]) != game["game_id"]:
            raise ValueError("Summary game ID does not match")
        competitors = header["competitions"][0]["competitors"]
        actual = {str(t["id"]): int(t["score"]) for t in competitors}
        expected = {
            str(game[side]["id"]): game[side]["score"] for side in ("home", "away")
        }
        if actual != expected:
            raise ValueError("Summary and scoreboard scores disagree")
        players = []
        for team in payload["boxscore"]["players"]:
            if str(team["team"]["id"]) not in expected:
                raise ValueError("Unexpected box score team")
            for group in team["statistics"]:
                for athlete in group["athletes"]:
                    stats = athlete.get("stats", [])
                    if not stats:  # DNP / inactive
                        continue
                    if len(stats) != len(group["labels"]):
                        raise ValueError("Box score labels and values disagree")
                    players.append(
                        {
                            "player": athlete["athlete"]["displayName"],
                            "starter": athlete.get("starter"),
                            "team": team["team"]["displayName"],
                            "statistics": dict(zip(group["labels"], stats)),
                        }
                    )
        if not players:
            raise ValueError("No player statistics returned")
        article = payload.get("article") or {}
        recap = html.unescape(re.sub(r"<[^>]+>", " ", article.get("story", "")))
        return {
            "details_status": "ok",
            "details_source": f"{url}?event={game['game_id']}",
            "player_stats": players,
            "recap": recap[:12000],
            "statistics_policy": "Structured player_stats override recap/search if they disagree. Do not quote unsupported statistics.",
        }
    except (
        requests.RequestException,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
    ) as exc:
        return {
            "details_status": "unavailable",
            "details_error": type(exc).__name__,
            "player_stats": [],
            "recap": "",
            "statistics_policy": "Only scoreboard scores and top_scorers are verified. Omit all other numerical player/game claims.",
        }


def results_for(day: date) -> dict:
    slate = fetch_slate(day)
    # Postponed/cancelled games must remain visible but aren't pending results.
    excluded = {"STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED"}
    unresolved = [
        g["game_id"]
        for g in slate["games"]
        if not g["completed"] and g["status"] not in excluded
    ]
    if not unresolved:
        for game in slate["games"]:
            if game["completed"]:
                game.update(fetch_game_details(game))
    slate.update(
        status="incomplete" if unresolved else "ok",
        unresolved_game_ids=unresolved,
        total_games=len(slate["games"]),
        completed_games=sum(g["completed"] for g in slate["games"]),
    )
    return slate


def collect_edition(day: date) -> dict:
    """Freeze both slates before asking an LLM to write or publish anything."""
    results = results_for(day - timedelta(days=1))
    if results["unresolved_game_ids"]:
        raise ResultsNotReady(
            f"Results for {results['date']} are not final: "
            + ", ".join(results["unresolved_game_ids"])
        )
    schedule = fetch_slate(day)
    schedule["status"] = "ok"
    return {
        "edition_date": day.isoformat(),
        "edition_timezone": EASTERN.key,
        "results": results,
        "schedule": schedule,
    }
