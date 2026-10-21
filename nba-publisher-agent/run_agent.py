#!/usr/bin/env python3
"""Collect a frozen NBA edition, then generate and publish its podcast."""

import argparse
import asyncio
import json
import os
from datetime import date
from pathlib import Path

import dotenv

dotenv.load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from nba_publisher_agent.agent import root_agent
from nba_publisher_agent.game_data import ResultsNotReady, collect_edition, edition_date

APP_NAME = "nba_publisher_app"
USER_ID = "nba_user"


async def collect_with_wait(day: date, attempts: int = 7, delay: float = 300) -> dict:
    """Allow up to 30 minutes for overtime/delayed finals; fail closed after that."""
    for attempt in range(attempts):
        try:
            return await asyncio.to_thread(collect_edition, day)
        except ResultsNotReady:
            if attempt == attempts - 1:
                raise
            print(f"Waiting for final scores (attempt {attempt + 1}/{attempts})")
            await asyncio.sleep(delay)
    raise ValueError("attempts must be positive")


async def run_nba_agent(day: date | None = None, *, collect_only: bool = False) -> bool:
    day = day or edition_date()
    session_id = f"nba_{day.isoformat()}_{os.getpid()}"
    try:
        snapshot = await collect_with_wait(day)
        reports = Path("reports")
        reports.mkdir(exist_ok=True)
        (reports / f"nba_{day}.json").write_text(
            json.dumps(snapshot, indent=2), encoding="utf-8"
        )
        print(
            f"Collected {snapshot['results']['total_games']} results for {snapshot['results']['date']}"
        )
        if collect_only:
            return True
        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id,
            state={"edition_date": day.isoformat(), "nba_edition": snapshot},
        )
        runner = Runner(
            agent=root_agent, app_name=APP_NAME, session_service=session_service
        )
        final_response = None
        try:
            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=session_id,
                new_message=Content(
                    role="user",
                    parts=[
                        Part(
                            text=f"Create the NBA daily summary podcast for edition {day}."
                        )
                    ],
                ),
            ):
                if (
                    event.is_final_response()
                    and event.author == root_agent.name
                    and event.content
                ):
                    text = " ".join(
                        part.text for part in event.content.parts or [] if part.text
                    )
                    if text:
                        final_response = text
        finally:
            await runner.close()
        session = await session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
        if not final_response or not session or not session.state.get("audio_uploaded"):
            print("Failed: no final response or confirmed audio upload")
            return False
        report = session.state.get("summary_report") or final_response
        (reports / f"nba_{day}.md").write_text(report, encoding="utf-8")
        print(final_response)
        return True
    except Exception as exc:
        # Avoid logging API error bodies that can contain credentials/request data.
        print(f"NBA edition {day} failed ({type(exc).__name__}); no success reported")
        return False


def main() -> bool:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--edition-date",
        type=date.fromisoformat,
        help="Eastern (New York) edition date YYYY-MM-DD (defaults to today in New York)",
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="Collect and save data without LLM calls or uploads",
    )
    args = parser.parse_args()
    return asyncio.run(run_nba_agent(args.edition_date, collect_only=args.collect_only))


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
