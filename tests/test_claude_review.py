"""Offline tests: no Claude service, credentials, or model calls are used."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "claude_review.py"
spec = importlib.util.spec_from_file_location("claude_review", SCRIPT)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "prompt.md").write_text("Review the definition; do not execute code.\n")
        (self.root / "method.md").write_text("Polarization is the norm of the mean unit heading.\n")

    def call(self, **kwargs):
        return review.run_review("prompt.md", ["method.md"], "reviews/run1", root=self.root, **kwargs)

    def mocked_run(self, response, code=0):
        def run(command, **kwargs):
            if command[0] == "git":
                text = "abc123\n" if command[1] == "rev-parse" else "?? method.md\n"
                return subprocess.CompletedProcess(command, 0, text, "")
            return subprocess.CompletedProcess(command, code, response, "diagnostic\n")
        return run

    def status(self):
        return json.loads((self.root / "reviews/run1/status.json").read_text())

    def test_success_saves_exact_snapshot_and_actual_model_without_acceptance(self):
        raw = json.dumps({"is_error": False, "result": "Verdict: CHANGES_REQUESTED", "modelUsage": {"actual-model": {}}, "session_id": "test-session"})
        with patch.object(review.subprocess, "run", side_effect=self.mocked_run(raw)) as run:
            path = self.call(model="chosen-model")
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--model") + 1], "chosen-model")
        self.assertEqual(command[command.index("--tools") + 1], "")
        self.assertNotIn("--fallback-model", command)
        self.assertIn("--safe-mode", command)
        packet = run.call_args.kwargs["input"]
        out = path.parent
        self.assertEqual((out / "snapshot.txt").read_text(), packet)
        self.assertEqual((out / "response.json").read_text(), raw)
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(manifest["packet_sha256"], review.sha256(packet.encode()))
        self.assertTrue(manifest["git"]["dirty"])
        self.assertEqual(self.status()["reported_models"], ["actual-model"])
        self.assertEqual(self.status()["state"], "response_received")
        self.assertEqual(self.status()["scientific_acceptance"], "not_adjudicated")

    def test_default_does_not_select_or_replace_model(self):
        with patch.object(review.subprocess, "run", side_effect=self.mocked_run('{"result":"Review text"}')) as run:
            self.call()
        self.assertNotIn("--model", run.call_args.args[0])

    def test_error_responses_are_recorded_and_rejected(self):
        cases = [('{"is_error":true,"result":"no access"}', 0),
                 ('{"result":""}', 0), ('{"result":42}', 0),
                 ('not json', 0), ('[]', 0), ('denied', 1)]
        for number, (response, code) in enumerate(cases):
            with self.subTest(response=response):
                out = f"reviews/error{number}"
                with patch.object(review.subprocess, "run", side_effect=self.mocked_run(response, code)):
                    with self.assertRaises(review.ReviewError):
                        review.run_review("prompt.md", ["method.md"], out, root=self.root)
                status = json.loads((self.root / out / "status.json").read_text())
                self.assertEqual(status["state"], "failed")
                self.assertFalse((self.root / out / "review.md").exists())
                self.assertEqual((self.root / out / "response.json").read_text(), response)

    def test_timeout_preserves_partial_output(self):
        def run(command, **kwargs):
            if command[0] == "git":
                return subprocess.CompletedProcess(command, 0, "", "")
            raise subprocess.TimeoutExpired(command, 5, output=b"partial", stderr=b"slow")
        with patch.object(review.subprocess, "run", side_effect=run):
            with self.assertRaisesRegex(review.ReviewError, "Timed out"):
                self.call(timeout=5)
        self.assertEqual(self.status()["state"], "failed")
        self.assertEqual((self.root / "reviews/run1/response.json").read_text(), "partial")

    def test_missing_executable_records_failure(self):
        def run(command, **kwargs):
            if command[0] == "git":
                return subprocess.CompletedProcess(command, 0, "", "")
            raise FileNotFoundError("claude")
        with patch.object(review.subprocess, "run", side_effect=run):
            with self.assertRaises(review.ReviewError):
                self.call()
        self.assertEqual(self.status()["state"], "failed")

    def test_unsafe_input_and_output_paths_are_rejected(self):
        for name in [".env", ".env.local", "id_rsa", "secret.pem"]:
            (self.root / name).write_text("example secret")
            with self.assertRaises(review.ReviewError):
                review.read_source(name, self.root)
        with self.assertRaises(review.ReviewError):
            review.repository_path("../outside.md", self.root)
        (self.root / "alias.md").symlink_to(self.root / "method.md")
        with self.assertRaises(review.ReviewError):
            review.read_source("alias.md", self.root)
        (self.root / "outalias").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(review.ReviewError):
            review.repository_path("outalias/review", self.root)

    def test_binary_oversized_and_duplicate_inputs_rejected(self):
        (self.root / "binary.md").write_bytes(b"\xff\x00")
        with self.assertRaises(review.ReviewError):
            review.read_source("binary.md", self.root)
        with patch.object(review, "MAX_FILE_BYTES", 1):
            with self.assertRaises(review.ReviewError):
                review.read_source("method.md", self.root)
        with self.assertRaisesRegex(review.ReviewError, "Duplicate"):
            review.build_packet("prompt.md", ["method.md", "method.md"], self.root)

    def test_prior_output_is_never_overwritten(self):
        with patch.object(review.subprocess, "run", side_effect=self.mocked_run('{"result":"first"}')):
            path = self.call()
            with self.assertRaisesRegex(review.ReviewError, "never overwritten"):
                self.call()
        self.assertEqual(path.read_text(), "first\n")

    def test_invalid_timeout_and_blank_model(self):
        for timeout in [0, -1, float("nan"), float("inf")]:
            with self.assertRaises(review.ReviewError):
                self.call(timeout=timeout)
        with self.assertRaises(review.ReviewError):
            self.call(model=" ")


if __name__ == "__main__":
    unittest.main()
