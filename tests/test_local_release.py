"""Regression checks for dispatch authorization, retries and release results."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import local_release as worker


def dispatch(**fields):
    return {
        "id": 123,
        "display_title": f"Halo local release {'a' * 40} install",
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
            {"display_title": f"Halo local release {'a' * 40} install-and-smoke"},
        ):
            with self.subTest(fields=fields):
                self.assertIsNone(worker.enrolled_job(dispatch(**fields)))

    @patch.object(worker, "git")
    def test_worker_rejects_commit_outside_main_before_checkout(self, git):
        checkout = self.home / "checkout"
        (checkout / ".git").mkdir(parents=True)
        job = worker.enrolled_job(dispatch())
        git.side_effect = [None, None, subprocess.CalledProcessError(1, "merge-base")]
        with self.assertRaises(subprocess.CalledProcessError):
            worker.prepare(checkout, job)
        self.assertEqual(git.call_args.args,
                         (checkout, "merge-base", "--is-ancestor", job["commit"], "FETCH_HEAD"))

    @patch.object(worker, "execute")
    def test_source_gate_and_completed_job_deduplication(self, execute):
        worker.process(self.home, [dispatch(conclusion="failure")])
        worker.process(self.home, [dispatch(status="in_progress"), dispatch(id=124)])
        execute.assert_not_called()
        done = self.home / "jobs/123.json"
        worker.write(done, {"status": "cache_verified"})
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
    def test_package_and_install_stop_at_release_result(self, run, _prepare):
        results = iter(("packaged", "cache_verified"))

        def release(command, **_kwargs):
            path = Path(command[command.index("--result") + 1])
            worker.write(path, {"status": next(results)})
            return subprocess.CompletedProcess(command, 0)

        run.side_effect = release
        for mode, expected in (("package", "packaged"), ("install", "cache_verified")):
            with self.subTest(mode=mode):
                run.reset_mock()
                path = self.home / "jobs/123.json"
                job = worker.enrolled_job(dispatch(display_title=f"Halo local release {'a' * 40} {mode}"))
                worker.execute(self.home, job, None, path)
                run.assert_called_once()
                command = run.call_args.args[0]
                self.assertEqual(command[1:6], ["-B", "tools/project.py", "release", "--native", "--result"])
                self.assertEqual(command[7:], ["--install"] if mode == "install" else [])
                self.assertEqual(worker.read(path)["status"], expected)


if __name__ == "__main__":
    unittest.main()
