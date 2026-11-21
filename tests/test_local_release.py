"""Regression checks for dispatch authorization, retries and boot evidence."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import local_release as worker
import project


def dispatch(**fields):
    return {
        "id": 123,
        "display_title": f"Halo local release {'a' * 40} install-and-smoke",
        "event": "workflow_dispatch",
        "head_branch": worker.BRANCH,
        "head_repository": {"full_name": worker.REPOSITORY},
        "actor": {"login": worker.OWNER},
        "triggering_actor": {"login": worker.OWNER},
        "head_sha": "b" * 40,
        "status": "completed",
        "conclusion": "success",
        **fields,
    }


class LocalReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        (self.home / "jobs").mkdir()

    def test_only_owner_dispatch_on_default_branch_with_exact_sha(self):
        self.assertEqual(worker.enrolled_job(dispatch())["commit"], "a" * 40)
        for fields in (
            {"event": "pull_request"},
            {"head_branch": "feature"},
            {"head_repository": {"full_name": "other/halo-glass-hud"}},
            {"actor": {"login": "other"}},
            {"triggering_actor": {"login": "other"}},
            {"head_sha": "main"},
            {"display_title": "Halo local release main install"},
        ):
            with self.subTest(fields=fields):
                self.assertIsNone(worker.enrolled_job(dispatch(**fields)))

    @patch.object(worker, "execute")
    def test_source_gate_and_completed_job_deduplication(self, execute):
        worker.process(self.home, [dispatch(conclusion="failure")])
        worker.process(self.home, [dispatch(status="in_progress"), dispatch(id=124)])
        execute.assert_not_called()
        done = self.home / "jobs/123.json"
        worker.write(done, {"status": "smoke_passed"})
        worker.process(self.home, [dispatch(), dispatch(id=124)])
        self.assertEqual(execute.call_args.args[1]["run"], 124)

    @patch.object(worker, "execute")
    def test_waiting_resumes_but_interrupted_job_stops(self, execute):
        path = self.home / "jobs/123.json"
        worker.write(path, {"status": "waiting_for_game_close"})
        worker.process(self.home, [dispatch()])
        self.assertEqual(execute.call_args.args[2], "waiting_for_game_close")
        execute.reset_mock()
        worker.write(path, {"status": "running"})
        worker.process(self.home, [dispatch()])
        execute.assert_not_called()
        self.assertEqual(worker.read(path)["status"], "interrupted")

    @patch.object(worker.subprocess, "run", return_value=Mock(stdout='"F1_25.exe","987"'))
    @patch.object(worker, "prepare")
    def test_wait_for_existing_game_without_building_again(self, prepare, run):
        worker.execute(self.home, worker.enrolled_job(dispatch()), "waiting_for_game_close",
                       self.home / "jobs/123.json")
        prepare.assert_not_called()
        self.assertEqual(run.call_args.args[0][0], "tasklist.exe")

    @patch.object(worker, "prepare")
    @patch.object(worker.subprocess, "run")
    def test_pass_structured_release_modes_and_record_failures(self, run, _prepare):
        def release(command, **_kwargs):
            path = Path(command[command.index("--result") + 1])
            worker.write(path, {"status": "smoke_failed"})
            return subprocess.CompletedProcess(command, 1)

        run.side_effect = release
        path = self.home / "jobs/123.json"
        worker.execute(self.home, worker.enrolled_job(dispatch()), None, path)
        self.assertEqual(run.call_args.args[0][-2:], ["--install", "--smoke"])
        self.assertEqual(worker.read(path)["status"], "smoke_failed")

    @patch.object(project, "game_running", return_value=False)
    @patch.object(project, "run")
    def test_smoke_requires_evidence_and_never_takes_over(self, run, _busy):
        settings = {"launcher": "swofty", "data_dir": "store", "game": "game"}
        record = {"profile": "default", "status": "cache_verified"}
        timings = project.Timings(self.home / "timings.json")
        with self.assertRaisesRegex(RuntimeError, "without writing the smoke report"):
            project.boot_smoke(settings, self.home, timings, record)
        self.assertEqual(record["status"], "smoke_failed")
        report = Path(record["smoke_report"])
        report.parent.mkdir()
        report.write_text("{}", encoding="utf-8")
        project.boot_smoke(settings, self.home, timings, record)
        self.assertEqual(record["status"], "smoke_passed")
        command = run.call_args.args[0]
        self.assertNotIn("--take-over", command)
        self.assertEqual(command[-2:], ["--wait", "0"])


if __name__ == "__main__":
    unittest.main()
