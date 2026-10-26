"""Execute the workflow's control flow locally with fake cloud/GitHub calls.

Requires PyYAML. This small interpreter covers the DSL constructs used here;
Google's deployment compiler remains the authoritative syntax validation.
No real credentials, network calls, sleeps, or production writes are used.
"""

import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo

import yaml


class Record(dict):
    def __getattr__(self, key):
        return self[key]


def record(value):
    if isinstance(value, dict):
        return Record({k: record(v) for k, v in value.items()})
    if isinstance(value, list):
        return [record(v) for v in value]
    return value


class Returned(Exception):
    def __init__(self, value):
        self.value = value


class Raised(Exception):
    def __init__(self, value):
        self.value = value


class Engine:
    def __init__(self, conclusions=None, duplicate=False, uncertain=False, active=0):
        self.source = yaml.safe_load(Path(__file__).with_name("orchestrator.yaml").read_text())
        self.clock = datetime.datetime(2026, 10, 26, 0, 30, tzinfo=datetime.timezone.utc).timestamp()
        self.conclusions = conclusions or ["success", "success"]
        self.duplicate = duplicate
        self.uncertain = uncertain
        self.active = active
        self.events = []
        self.dispatches = 0

    def value(self, value, scope):
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            helpers = {
                "null": None, "true": True, "false": False, "string": str,
                "default": lambda v, d: d if v is None else v,
                "map": SimpleNamespace(get=lambda m, k: m.get(k)),
                "text": SimpleNamespace(substring=lambda s, a, b: s[a:b]),
                "time": SimpleNamespace(format=lambda ts, zone: datetime.datetime.fromtimestamp(ts, ZoneInfo(zone)).isoformat()),
                "sys": SimpleNamespace(now=lambda: self.clock, get_env=lambda key: "fixture-" + key.lower()),
            }
            return record(eval(value[2:-1], {"__builtins__": {}}, helpers | scope))
        if isinstance(value, dict):
            return record({k: self.value(v, scope) for k, v in value.items()})
        if isinstance(value, list):
            return [self.value(v, scope) for v in value]
        return value

    def run(self, args=None):
        return self.call("main", {"args": record(args or {})})

    def call(self, name, args):
        if name in self.source:
            try:
                self.steps(self.source[name]["steps"], dict(args))
            except Returned as result:
                return result.value
            return None
        if name.endswith("accessString"):
            return "test-placeholder"
        if name == "sys.sleep":
            self.clock += args["seconds"]
            return None
        url = args["url"]
        if name == "http.get":
            if "/runs?" in url:
                return record({"body": {"total_count": self.active}})
            if "/actions/runs/" in url:
                index = int(url.rsplit("/", 1)[1]) - 100
                self.events.append("read-" + str(index))
                conclusion = self.conclusions[index]
                return record({"body": {"status": "in_progress" if conclusion is None else "completed", "conclusion": conclusion}})
            return record({"body": {"state": "active"}})
        if "/dispatches" in url:
            index = self.dispatches
            self.dispatches += 1
            self.events.append(("dispatch", url, args["body"]["inputs"]["edition_date"]))
            if self.uncertain:
                raise Raised(record({"code": 504}))
            return record({"code": 200, "body": {"workflow_run_id": 100 + index, "html_url": "https://github.com/run/" + str(100 + index)}})
        if name == "http.post" and "storage.googleapis.com" in url:
            self.events.append("claim" if args["query"]["name"].startswith("editions/") else "persist")
            if self.duplicate and self.events[-1] == "claim":
                raise Raised(record({"code": 412}))
            return record({"code": 200})
        raise AssertionError("Unexpected call " + name)

    def execute(self, operation, scope):
        if "try" in operation:
            try:
                self.execute(operation["try"], scope)
            except Raised as error:
                handler = operation["except"]
                scope[handler["as"]] = error.value
                self.steps(handler["steps"], scope)
        elif "assign" in operation:
            for assignment in operation["assign"]:
                for key, value in assignment.items():
                    scope[key] = self.value(value, scope)
        elif "call" in operation:
            result = self.call(operation["call"], self.value(operation.get("args", {}), scope))
            if "result" in operation:
                scope[operation["result"]] = result
        elif "for" in operation:
            loop = operation["for"]
            values = self.value(loop["in"], scope) if "in" in loop else range(loop["range"][0], loop["range"][1] + 1)
            for value in values:
                scope[loop["value"]] = value
                self.steps(loop["steps"], scope)
        elif "switch" in operation:
            for branch in operation["switch"]:
                if self.value(branch["condition"], scope):
                    self.execute({k: v for k, v in branch.items() if k != "condition"}, scope)
                    break
        elif "return" in operation:
            raise Returned(self.value(operation["return"], scope))
        elif "raise" in operation:
            raise Raised(self.value(operation["raise"], scope))
        else:
            raise AssertionError("Unsupported operation")

    def steps(self, steps, scope):
        index = 0
        positions = {next(iter(step)): n for n, step in enumerate(steps)}
        while index < len(steps):
            operation = next(iter(steps[index].values()))
            self.execute(operation, scope)
            index = positions[operation["next"]] if "next" in operation else index + 1


class OrchestrationTests(unittest.TestCase):
    def test_success_waits_for_generation_and_shares_eastern_date(self):
        engine = Engine()
        result = engine.run()
        self.assertEqual(result["status"], "success")
        dispatches = [e for e in engine.events if isinstance(e, tuple)]
        self.assertIn("nba-agents/actions/workflows/daily-agent.yml", dispatches[0][1])
        self.assertIn("nba-daily-summary-podcast/actions/workflows/publish_podcast.yml", dispatches[1][1])
        self.assertEqual([e[2] for e in dispatches], ["2026-10-25", "2026-10-25"])
        self.assertLess(engine.events.index("read-0"), engine.events.index(dispatches[1]))

    def test_failure_and_cancellation_stop_publication(self):
        for conclusion in ["failure", "cancelled", "timed_out", "skipped"]:
            with self.subTest(conclusion=conclusion):
                engine = Engine([conclusion])
                with self.assertRaises(Raised):
                    engine.run()
                self.assertEqual(engine.dispatches, 1)

    def test_dry_run_has_no_dispatches_or_claims(self):
        engine = Engine()
        self.assertEqual(engine.run({"dry_run": True})["status"], "preflight_passed")
        self.assertEqual(engine.events, [])

    def test_duplicate_cannot_dispatch(self):
        engine = Engine(duplicate=True)
        self.assertEqual(engine.run()["status"], "duplicate_skipped")
        self.assertEqual(engine.dispatches, 0)

    def test_uncertain_dispatch_is_not_retried(self):
        engine = Engine(uncertain=True)
        with self.assertRaises(Raised):
            engine.run()
        self.assertEqual(engine.dispatches, 1)

    def test_active_prior_run_blocks_dispatch(self):
        engine = Engine(active=1)
        with self.assertRaises(Raised):
            engine.run()
        self.assertEqual(engine.dispatches, 0)

    def test_timeout_stops_before_publication(self):
        engine = Engine([None])
        with self.assertRaises(Raised):
            engine.run()
        self.assertEqual(engine.dispatches, 1)

    def test_publisher_failure_is_reported(self):
        engine = Engine(["success", "failure"])
        with self.assertRaises(Raised):
            engine.run()
        self.assertEqual(engine.dispatches, 2)


if __name__ == "__main__":
    unittest.main()
