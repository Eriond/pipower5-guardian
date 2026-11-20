"""Build a source-complete installable ZIP without local caches or Git metadata."""
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
version = json.loads((root / "custom_components/pipower5_guardian/manifest.json").read_text())["version"]
output = root / "dist" / f"pipower5-guardian-{version}.zip"
output.parent.mkdir(exist_ok=True)
files = [root / name for name in ("README.md", "LICENSE", "NOTICE.md", "PROTOCOL-SOURCES.md", "VALIDATION.md", "CHANGELOG.md")]
for directory in ("custom_components", "tests", "scripts"):
    files.extend(path for path in (root / directory).rglob("*")
                 if path.is_file() and "__pycache__" not in path.parts
                 and path.suffix not in (".pyc", ".pyo"))
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, path.relative_to(root).as_posix())
with ZipFile(output) as archive:
    assert archive.testzip() is None
    assert "custom_components/pipower5_guardian/manifest.json" in archive.namelist()
print(output)
