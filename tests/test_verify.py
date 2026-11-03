import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify.py"
SPEC = importlib.util.spec_from_file_location("korea5_verify", SCRIPT)
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


class TokenVerificationTests(unittest.TestCase):
    def test_live_match_is_verified(self):
        with patch.object(verify, "fetch", return_value=(200, "Week 1 Titans")):
            self.assertEqual(verify.check_tokens("https://official.example/schedule", ["Week 1", "Titans"]),
                             (True, [], 200))

    def test_successful_live_response_missing_tokens_is_mismatch(self):
        with patch.object(verify, "fetch", side_effect=[(200, "A different schedule"),
                                                           (200, "A different schedule")]):
            result, missing, status = verify.check_tokens("https://official.example/schedule", ["Titans"])
        self.assertIs(result, False)
        self.assertEqual(missing, ["Titans"])
        self.assertEqual(status, 200)

    def test_network_failure_without_snapshot_is_unavailable_not_mismatch(self):
        with patch.object(verify, "fetch", return_value=(None, "__ERROR__ blocked")), \
                patch.dict(verify.SNAPSHOTS, {}, clear=True):
            result, missing, status = verify.check_tokens("https://official.example/schedule", ["Titans"])
        self.assertIsNone(result)
        self.assertEqual(missing, ["Titans"])
        self.assertIsNone(status)

    def test_network_failure_can_be_verified_against_snapshot_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = Path(temp_dir) / "official.txt"
            snapshot.write_text("Week 1 Titans", encoding="utf-8")
            with patch.object(verify, "fetch", return_value=(None, "__ERROR__ blocked")), \
                    patch.dict(verify.SNAPSHOTS, {"https://official.example/schedule": str(snapshot)}):
                result, missing, status = verify.check_tokens("https://official.example/schedule", ["Titans"])
        self.assertEqual(result, "snapshot")
        self.assertEqual(missing, [])
        self.assertIsNone(status)

    def test_snapshot_fallback_is_explicit_even_when_live_schedule_differs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot = Path(temp_dir) / "official.txt"
            snapshot.write_text("Titans", encoding="utf-8")
            with patch.object(verify, "fetch", side_effect=[(200, "Updated schedule"),
                                                               (200, "Updated schedule")]), \
                    patch.dict(verify.SNAPSHOTS, {"https://official.example/schedule": str(snapshot)}):
                result, missing, status = verify.check_tokens("https://official.example/schedule", ["Titans"])
        self.assertIs(result, "snapshot")
        self.assertEqual(missing, [])
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
