import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_spec_md_is_built_from_chapters():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_spec.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_every_chapter_is_listed_and_exists():
    listed = [l.strip() for l in (ROOT / "spec" / "CHAPTERS.txt").read_text().splitlines() if l.strip()]
    on_disk = sorted(p.name for p in (ROOT / "spec").glob("*.md") if p.name != "README.md")
    assert sorted(listed) == on_disk, (set(listed) ^ set(on_disk))
    for name in listed:
        assert (ROOT / "spec" / name).read_text().strip()
