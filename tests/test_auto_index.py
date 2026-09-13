"""Unit tests for semcode.auto_index."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from semcode.auto_index import check_eligibility, get_git_repo_root


class AutoIndexTests(unittest.TestCase):
    def test_git_repo_root_detection(self):
        root = Path(__file__).resolve().parent.parent
        self.assertEqual(get_git_repo_root(str(root)), root)
        self.assertEqual(get_git_repo_root(str(root / "semcode")), root)

    def test_non_git_path_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(get_git_repo_root(tmp))

    def test_deny_patterns(self):
        self.assertFalse(check_eligibility(Path("C:\\Windows"))[0])
        self.assertFalse(check_eligibility(Path("C:\\Program Files"))[0])

    def test_max_files_threshold(self):
        root = Path(__file__).resolve().parent.parent
        with patch("semcode.auto_index.get_git_files", return_value=["f.py"] * 5001), \
             patch("semcode.auto_index.load_config", return_value={"max_files": 5000, "deny_patterns": []}):
            eligible, reason, files = check_eligibility(root)
            self.assertFalse(eligible)
            self.assertIn("exceeds auto-index limit", reason)


if __name__ == "__main__":
    unittest.main()
