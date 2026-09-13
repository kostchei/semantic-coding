"""Unit tests for semcode.registry."""

from pathlib import Path
import tempfile
import unittest

from semcode.registry import load_registry, save_registry, resolve_project


class RegistryTests(unittest.TestCase):
    def test_load_existing_registry(self):
        reg = load_registry()
        self.assertIn("ORAC", reg)
        self.assertIn("ash-rpg", reg)
        self.assertIn("praetor_silica", reg)
        self.assertIn("LDGM", reg)
        for name, info in reg.items():
            self.assertTrue(Path(info["source_path"]).is_dir(), f"Source path for {name} does not exist")

    def test_corrupt_registry_raises_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg_path = Path(tmp) / "registry.json"
            reg_path.write_text("{corrupt json", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                load_registry(str(reg_path))
            # Verify file content is still the original corrupted content
            self.assertEqual(reg_path.read_text(encoding="utf-8"), "{corrupt json")

    def test_missing_registry_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg_path = Path(tmp) / "nonexistent.json"
            with self.assertRaises(RuntimeError):
                load_registry(str(reg_path))

    def test_atomic_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg_path = Path(tmp) / "registry.json"
            sample = {"test": {"source_path": "D:\\test", "text_dir": "t", "code_dir": "c"}}
            save_registry(sample, str(reg_path))
            loaded = load_registry(str(reg_path))
            self.assertEqual(loaded, sample)

    def test_resolve_project_priorities_and_nesting(self):
        sample = {
            "parent": {
                "source_path": "D:\\Projects\\Monorepo",
                "text_dir": "p_text",
                "code_dir": "p_code",
            },
            "child": {
                "source_path": "D:\\Projects\\Monorepo\\packages\\app",
                "text_dir": "c_text",
                "code_dir": "c_code",
            }
        }
        # Nested match prefers child
        t, c, name, sp = resolve_project(
            cwd="D:\\Projects\\Monorepo\\packages\\app\\src",
            registry=sample
        )
        self.assertEqual(name, "child")
        self.assertEqual(t, "c_text")

        # Parent directory matches parent
        t, c, name, sp = resolve_project(
            cwd="D:\\Projects\\Monorepo\\docs",
            registry=sample
        )
        self.assertEqual(name, "parent")

        # Client session roots resolution
        t, c, name, sp = resolve_project(
            roots=["D:\\Projects\\Monorepo\\packages\\app"],
            registry=sample
        )
        self.assertEqual(name, "child")

        # Unknown path raises ValueError
        with self.assertRaises(ValueError) as ctx:
            resolve_project(cwd="D:\\Unrelated\\Repo", registry=sample)
        self.assertIn("is not registered", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
