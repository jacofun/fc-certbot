"""Package only cert-generator source and its Linux/Python 3.10 dependencies."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


SOURCE_FILES = (
    "index.py", "authenticator.py", "cleanup.py", "dns_propagation.py", "requirements.txt",
    "check_dependencies.py", "cas/index.py", "alidns/index.py",
    "scripts/authenticator.sh", "scripts/cleanup.sh", "scripts/upload-certs.sh",
)


def build_package(source, destination):
    if not (source / "python/certbot/main.py").is_file():
        raise ValueError("Build cert-generator/python in the FC Python 3.10 image first")
    files = [source / name for name in SOURCE_FILES]
    files += sorted(p for p in (source / "python").rglob("*") if p.is_file())
    files = [p for p in files if not any(
        part in {".git", ".github", "__pycache__"} or part.startswith(".env")
        for part in p.relative_to(source).parts
    ) and p.suffix not in {".pyc", ".pyo"}]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for file in files:
            if not file.resolve().is_relative_to(source.resolve()):
                raise ValueError("Package symlink points outside cert-generator")
            archive.write(file, file.relative_to(source).as_posix())
    print(f"Created {destination.name}: {destination.stat().st_size} bytes")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    build_package(root / "src/cert-generator", root / "dist/cert-generator.zip")
