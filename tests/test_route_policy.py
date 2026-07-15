import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("route_policy", ROOT / "scripts" / "route_policy.py")
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


def current(model="gpt-5.6-sol", effort="ultra"):
    return {
        "status": "verified",
        "thread_id": "019f6001-95ae-7411-a5ba-7895a1897e49",
        "model": model,
        "effort": effort,
        "source": "test",
        "reason": None,
    }


class RoutePolicyTests(unittest.TestCase):
    def test_detects_latest_current_route_for_exact_thread(self):
        with tempfile.TemporaryDirectory() as directory:
            thread_id = "019f6001-95ae-7411-a5ba-7895a1897e49"
            session = Path(directory) / f"rollout-{thread_id}.jsonl"
            rows = [
                {"type": "session_meta", "payload": {"id": thread_id}},
                {"type": "event_msg", "payload": {"type": "thread_settings_applied", "thread_settings": {"model": "gpt-5.6-luna", "reasoning_effort": "low"}}},
                {"type": "event_msg", "payload": {"type": "thread_settings_applied", "thread_settings": {"model": "gpt-5.6-sol", "reasoning_effort": "ultra"}}},
            ]
            session.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            detected = POLICY.detect_current_route(directory, {"CODEX_THREAD_ID": thread_id})
            self.assertEqual((detected["model"], detected["effort"]), ("gpt-5.6-sol", "ultra"))
            self.assertEqual(detected["status"], "verified")

    def test_detects_turn_context_when_settings_event_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            thread_id = "019f6001-95ae-7411-a5ba-7895a1897e49"
            session = Path(directory) / f"rollout-{thread_id}.jsonl"
            row = {
                "type": "turn_context",
                "payload": {
                    "model": "gpt-5.6-terra",
                    "effort": "high",
                    "collaboration_mode": {
                        "settings": {"model": "gpt-5.6-terra", "reasoning_effort": "high"}
                    },
                },
            }
            metadata = {"type": "session_meta", "payload": {"session_id": thread_id}}
            session.write_text(json.dumps(metadata) + "\n" + json.dumps(row) + "\n")
            detected = POLICY.detect_current_route(directory, {"CODEX_THREAD_ID": thread_id})
            self.assertEqual((detected["model"], detected["effort"]), ("gpt-5.6-terra", "high"))
            self.assertEqual(detected["source"], "local-session-metadata:turn_context")

    def test_rejects_filename_match_with_wrong_session_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            thread_id = "019f6001-95ae-7411-a5ba-7895a1897e49"
            session = Path(directory) / f"backup-{thread_id}.jsonl"
            rows = [
                {"type": "session_meta", "payload": {"id": "019f6002-95ae-7411-a5ba-7895a1897e49"}},
                {"type": "turn_context", "payload": {"model": "gpt-5.6-luna", "effort": "low"}},
            ]
            session.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            detected = POLICY.detect_current_route(directory, {"CODEX_THREAD_ID": thread_id})
            self.assertEqual(detected["status"], "unavailable")
            self.assertEqual(detected["reason"], "verified-settings-not-found")

    def test_ordinary_apply_uses_terra_medium_and_restores(self):
        route = POLICY.select_route("apply", current=current())
        self.assertEqual(route["recommended"]["model"], "gpt-5.6-terra")
        self.assertEqual(route["recommended"]["effort"], "medium")
        self.assertEqual(route["execution"]["dispatch"], "same-task-switch")
        self.assertTrue(route["restore_required"])

    def test_tiny_apply_skips_switch_and_keeps_verified_current_route(self):
        route = POLICY.select_route("apply", task_kind="mechanical", risk="low", size="tiny", current=current())
        self.assertEqual(route["recommended"]["model"], "gpt-5.6-luna")
        self.assertEqual(route["execution"]["model"], "gpt-5.6-sol")
        self.assertEqual(route["execution"]["dispatch"], "local")
        self.assertFalse(route["restore_required"])

    def test_explicit_override_bypasses_tiny_switch_budget(self):
        route = POLICY.select_route(
            "apply", task_kind="mechanical", risk="low", size="tiny",
            model_override="luna", effort_override="low", current=current(),
        )
        self.assertEqual(route["execution"]["dispatch"], "same-task-switch")
        self.assertTrue(route["explicit_override"])

    def test_complex_task_cannot_use_tiny_fast_path(self):
        route = POLICY.select_route("apply", task_kind="complex", risk="normal", size="tiny", current=current())
        self.assertEqual(route["recommended"]["model"], "gpt-5.6-sol")
        self.assertEqual(route["execution"]["dispatch"], "same-task-switch")

    def test_spaced_sol_alias_is_supported(self):
        route = POLICY.select_route("assess", model_override="GPT-5.6 Sol", current=current())
        self.assertEqual(route["recommended"]["model"], "gpt-5.6-sol")

    def test_spaced_terra_and_very_high_aliases_are_supported(self):
        route = POLICY.select_route(
            "apply", model_override="GPT-5.6 Terra", effort_override="very high", current=current()
        )
        self.assertEqual(
            (route["recommended"]["model"], route["recommended"]["effort"]),
            ("gpt-5.6-terra", "xhigh"),
        )

    def test_unknown_original_never_uses_persistent_same_task_switch(self):
        route = POLICY.select_route("assess", current=POLICY.unavailable_current())
        self.assertEqual(route["execution"]["dispatch"], "selectable-subagent-or-local")
        self.assertFalse(route["restore_required"])

    def test_high_risk_apply_uses_sol_high(self):
        route = POLICY.select_route("apply", risk="high", current=current("gpt-5.6-terra", "medium"))
        self.assertEqual((route["recommended"]["model"], route["recommended"]["effort"]), ("gpt-5.6-sol", "high"))


if __name__ == "__main__":
    unittest.main()
