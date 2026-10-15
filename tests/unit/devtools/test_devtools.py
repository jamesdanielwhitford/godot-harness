"""Self-tests for tools/dev scripts. Run with pytest or `python3 -m unittest`."""
import os, shutil, subprocess, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEV = REPO / "tools" / "dev"


def sh(args, cwd, env=None):
    e = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    e.pop("HARNESS_ROOT", None)
    e.update(env or {})
    return subprocess.run(args, cwd=cwd, env=e, capture_output=True, text=True)


class Tree(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        (self.d / "tools").mkdir()
        shutil.copytree(DEV, self.d / "tools" / "dev", ignore=shutil.ignore_patterns("__pycache__"))
        sh(["git", "init", "-q", "-b", "main"], self.d)
        self.w("README.md", "x")
        self.commit("init")

    def w(self, rel, text="x"):
        p = self.d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg):
        sh(["git", "add", "-A"], self.d)
        sh(["git", "commit", "-qm", msg], self.d)

    def run_dev(self, name, *a, env=None):
        return sh([str(self.d / "tools" / "dev" / name), *a], self.d, env)


class PathguardTest(Tree):
    def test_clean_builder_working_tree(self):
        self.w("tools/harness/harness/x.py")
        self.w(".claude/handoff/A2/status.md")
        r = self.run_dev("pathguard.sh", "builder", "A2", "working-tree")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_builder_touching_tests_fails_and_lists_path(self):
        self.w("tests/unit/a2/test_x.py")
        self.w("tools/harness/ok.py")
        r = self.run_dev("pathguard.sh", "builder", "A2", "working-tree")
        self.assertEqual(r.returncode, 1)
        self.assertIn("tests/unit/a2/test_x.py", r.stdout)
        self.assertNotIn("tools/harness/ok.py", r.stdout)

    def test_range_and_other_area_handoff(self):
        self.w("tests/contract/a2/test_a.py")
        self.commit("tw")
        ok = self.run_dev("pathguard.sh", "test-writer", "A2", "HEAD~1..HEAD")
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.w("tests/contract/a3/test_b.py")
        self.w(".claude/handoff/A3/status.md")
        self.commit("tw2")
        bad = self.run_dev("pathguard.sh", "test-writer", "A2", "HEAD~1..HEAD")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("tests/contract/a3/test_b.py", bad.stdout)

    def test_test_writer_cannot_modify_existing_fixture(self):
        self.w("tests/fixtures/f.txt", "a")
        self.commit("fx")
        self.w("tests/fixtures/f.txt", "b")
        self.w("tests/fixtures/new.txt", "n")
        r = self.run_dev("pathguard.sh", "test-writer", "A2", "working-tree")
        self.assertEqual(r.returncode, 1)
        self.assertIn("tests/fixtures/f.txt", r.stdout)
        self.assertNotIn("new.txt", r.stdout)

    def test_planner_and_verifier(self):
        self.w(".claude/plans/specs/02_scene.md")
        self.assertEqual(self.run_dev("pathguard.sh", "planner", "A2", "working-tree").returncode, 0)
        self.assertEqual(self.run_dev("pathguard.sh", "verifier", "A2", "working-tree").returncode, 1)

    def test_usage_errors(self):
        self.assertEqual(self.run_dev("pathguard.sh", "bogus", "A2", "working-tree").returncode, 2)
        self.assertEqual(self.run_dev("pathguard.sh", "builder").returncode, 2)


class LockTest(Tree):
    def lock(self):
        self.w("tests/unit/t.py", "a")
        self.w("selftest/faults/F-1/fault.yaml", "a")
        r = self.run_dev("lock_tests.sh")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_no_lock(self):
        self.assertEqual(self.run_dev("check_lock.sh").returncode, 3)

    def test_clean_passes(self):
        self.lock()
        lock = (self.d / "tests/LOCK.sha256").read_text()
        self.assertIn("tests/unit/t.py", lock)
        self.assertIn("selftest/faults/F-1/fault.yaml", lock)
        self.assertNotIn("LOCK.sha256", lock)
        self.w("tests/unit/__pycache__/t.pyc", "junk")  # noise ignored
        self.assertEqual(self.run_dev("check_lock.sh").returncode, 0)

    def test_changed_added_removed_fail(self):
        self.lock()
        self.w("tests/unit/t.py", "b")
        r = self.run_dev("check_lock.sh")
        self.assertEqual(r.returncode, 1)
        self.assertIn("CHANGED tests/unit/t.py", r.stdout)
        self.lock()
        self.w("tests/unit/new.py")
        self.assertIn("ADDED   tests/unit/new.py", self.run_dev("check_lock.sh").stdout)
        (self.d / "tests/unit/new.py").unlink()
        (self.d / "tests/unit/t.py").unlink()
        r = self.run_dev("check_lock.sh")
        self.assertEqual(r.returncode, 1)
        self.assertIn("REMOVED tests/unit/t.py", r.stdout)


class CiTest(Tree):
    def test_all_skipped_is_not_pass(self):
        r = self.run_dev("ci.sh", "--quick")
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn("SKIPPED", r.stdout)
        self.assertNotIn("PASS", r.stdout.replace("0 passed", ""))
        summ = list((self.d / ".harness/out/ci").glob("*/summary.md"))
        self.assertEqual(len(summ), 1)

    def fake_pytest(self, rc):
        b = self.d / ".venv/bin"
        b.mkdir(parents=True, exist_ok=True)
        p = b / "pytest"
        p.write_text(f"#!/bin/sh\nexit {rc}\n")
        p.chmod(0o755)
        self.w("tests/unit/test_a.py", "")

    def test_pass_and_fail(self):
        self.fake_pytest(0)
        r = self.run_dev("ci.sh", "--quick")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("unit: PASS", r.stdout)
        self.fake_pytest(1)
        r = self.run_dev("ci.sh", "--quick")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unit: FAIL", r.stdout)

    def test_lock_violation_fails_ci(self):
        self.fake_pytest(0)
        self.run_dev("lock_tests.sh")
        self.w("tests/unit/test_a.py", "changed")
        r = self.run_dev("ci.sh", "--quick")
        self.assertEqual(r.returncode, 1)
        self.assertIn("check_lock: FAIL", r.stdout)


class FreshCloneTest(Tree):
    def test_clone_runs_ci(self):
        self.w("tests/unit/test_a.py", "")
        b = self.d / ".venv/bin"  # not committed? commit it so the clone has it
        b.mkdir(parents=True, exist_ok=True)
        (b / "pytest").write_text("#!/bin/sh\nexit 0\n")
        (b / "pytest").chmod(0o755)
        (self.d / ".gitignore").write_text(".harness/\n")
        self.commit("add")
        dest = Path(tempfile.mkdtemp()) / "clone"
        self.addCleanup(shutil.rmtree, dest.parent, True)
        r = self.run_dev("verify_fresh_clone.sh", "main", str(dest), env={"VERIFY_REMOTE": str(self.d)})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ci_rc=0", r.stdout)
        self.assertTrue((dest / "tools/dev/ci.sh").exists())

    def test_bad_branch(self):
        dest = Path(tempfile.mkdtemp()) / "c"
        self.addCleanup(shutil.rmtree, dest.parent, True)
        r = self.run_dev("verify_fresh_clone.sh", "nope", str(dest), env={"VERIFY_REMOTE": str(self.d)})
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
