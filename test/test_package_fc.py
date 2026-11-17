import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_fc", ROOT / "scripts/package_fc.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PackageTests(unittest.TestCase):
    def test_package_has_root_handler_dependencies_and_executable_hooks_without_local_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            names = list(module.SOURCE_FILES) + ["python/certbot/main.py", "python/demo/.env", "python/demo/__pycache__/x.pyc"]
            for name in names:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("test")
                if name.endswith(".sh"):
                    path.chmod(0o755)
            (source / ".env").write_text("secret-must-not-be-packaged")
            output = root / "code.zip"
            module.build_package(source, output)
            with ZipFile(output) as archive:
                files = archive.namelist()
                self.assertIn("index.py", files)
                self.assertIn("python/certbot/main.py", files)
                self.assertFalse(any(".env" in name or "__pycache__" in name for name in files))
                self.assertEqual((archive.getinfo("scripts/authenticator.sh").external_attr >> 16) & 0o777, 0o755)

    def test_package_requires_installed_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "Build cert-generator"):
                module.build_package(root, root / "code.zip")


if __name__ == "__main__":
    unittest.main()
