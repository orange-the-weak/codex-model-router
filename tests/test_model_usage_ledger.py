import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("model_usage_ledger", ROOT / "scripts" / "model_usage_ledger.py")
LEDGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LEDGER)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ledger = self.root / "history.jsonl"

    def tearDown(self):
        self.temp.cleanup()

    def test_deduplicates_event_ids(self):
        event = {"event": "skill_run", "event_id": "same", "mode": "query", "analysis_model": "local-script", "effort": "none"}
        self.assertTrue(LEDGER.append_event(self.ledger, event.copy()))
        self.assertFalse(LEDGER.append_event(self.ledger, event.copy()))

    def test_apply_is_a_valid_skill_run_mode(self):
        parser = LEDGER.parser()
        args = parser.parse_args([
            "record", "--ledger", str(self.ledger), "--event", "skill_run",
            "--mode", "apply", "--analysis-model", "gpt-5.6-terra", "--effort", "medium",
        ])
        with redirect_stdout(io.StringIO()):
            args.func(args)
        events, warnings = LEDGER.read_events(self.ledger)
        self.assertEqual(warnings, [])
        self.assertEqual(events[0]["mode"], "apply")

    def test_reports_model_and_effort_usage(self):
        LEDGER.append_event(self.ledger, {
            "event": "execution", "model": "GPT-5.6 Terra", "effort": "low",
            "task_class": "ui", "outcome": "completed", "source": "user-confirmed",
        })
        events, warnings = LEDGER.read_events(self.ledger)
        summary = LEDGER.build_summary(events, warnings)
        self.assertEqual(summary["actual_execution"]["items"]["GPT-5.6 Terra"]["percent"], 100.0)
        self.assertEqual(summary["model_effort_usage"]["items"]["GPT-5.6 Terra | low"]["count"], 1)

    def test_retune_signals_use_thresholds(self):
        events = []
        for outcome in ("failed", "escalated", "reworked", "completed", "completed"):
            events.append({"event": "execution", "model": "Luna", "effort": "low", "task_class": "auth", "outcome": outcome})
        for _ in range(10):
            events.append({
                "event": "execution", "model": "Terra", "effort": "medium",
                "task_class": "docs", "outcome": "completed", "verification": "deterministic",
            })
        summary = LEDGER.build_summary(events, [])
        self.assertEqual(summary["route_performance"]["auth | Luna | low"]["retune_signal"], "raise_candidate")
        self.assertEqual(summary["route_performance"]["docs | Terra | medium"]["retune_signal"], "lower_candidate")

    def test_skips_malformed_lines(self):
        valid = {"event": "skill_run", "mode": "query", "analysis_model": "local-script", "effort": "none"}
        self.ledger.write_text('{bad json}\n' + json.dumps(valid) + "\n")
        events, warnings = LEDGER.read_events(self.ledger)
        self.assertEqual(len(events), 1)
        self.assertEqual(len(warnings), 1)

    def test_skips_schema_invalid_events(self):
        invalid = {"event": "execution", "model": "Terra", "effort": "turbo", "task_class": "docs", "outcome": "completed", "source": "task-metadata"}
        self.ledger.write_text(json.dumps(invalid) + "\n")
        events, warnings = LEDGER.read_events(self.ledger)
        self.assertEqual(events, [])
        self.assertEqual(len(warnings), 1)

    def test_lowering_requires_deterministic_verification(self):
        events = [
            {
                "event": "execution", "model": "Terra", "effort": "medium",
                "task_class": "docs", "outcome": "completed", "verification": "manual",
            }
            for _ in range(10)
        ]
        summary = LEDGER.build_summary(events, [])
        self.assertEqual(summary["route_performance"]["docs | Terra | medium"]["retune_signal"], "hold")

    def test_cancelled_duration_is_excluded(self):
        events = [
            {"event": "execution", "model": "Terra", "effort": "medium", "task_class": "docs", "outcome": "completed", "duration_seconds": 10},
            {"event": "execution", "model": "Terra", "effort": "medium", "task_class": "docs", "outcome": "cancelled", "duration_seconds": 1000},
        ]
        summary = LEDGER.build_summary(events, [])
        performance = summary["route_performance"]["docs | Terra | medium"]
        self.assertEqual(performance["duration_median_seconds"], 10)
        self.assertEqual(performance["duration_p75_seconds"], 10)

    def test_report_markers_preserve_surrounding_content(self):
        report = self.root / "report.md"
        report.write_text("before\n\n<!-- MODEL_USAGE_START -->\nstale\n<!-- MODEL_USAGE_END -->\n\nafter\n")
        LEDGER.update_report(report, "<!-- MODEL_USAGE_START -->\nnew\n<!-- MODEL_USAGE_END -->")
        text = report.read_text()
        self.assertIn("before", text)
        self.assertIn("after", text)
        self.assertIn("new", text)
        self.assertNotIn("stale", text)


if __name__ == "__main__":
    unittest.main()
