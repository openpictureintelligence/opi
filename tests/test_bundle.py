"""The single-file validator is real, current, and agrees with the package.

Three properties: the checked-in `tools/opi_verify.py` is exactly what
`tools/build_bundle.py` produces from the sources (drift check); it runs
as a standalone script with no import path and passes both examples; and
it fails a tampered file with exit status 1.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "tools" / "opi_verify.py"
BUILDER = ROOT / "tools" / "build_bundle.py"
EXAMPLES = sorted((ROOT / "examples").glob("*.opi"))


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_bundle", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(*args, cwd):
    return subprocess.run([sys.executable, str(BUNDLE), *args], capture_output=True, text=True, cwd=cwd)


def test_checked_in_bundle_matches_the_sources():
    built = _load_builder().build()
    assert BUNDLE.exists(), "run tools/build_bundle.py"
    assert BUNDLE.read_text(encoding="utf-8") == built, "tools/opi_verify.py has drifted; run tools/build_bundle.py"


def test_bundle_is_stdlib_only():
    import ast
    tree = ast.parse(BUNDLE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    # `cryptography` is an optional fast path behind try/except; everything else is stdlib
    non_std = imported - set(sys.stdlib_module_names) - {"cryptography"}
    assert not non_std, non_std
    assert "openpicture" not in imported


def test_bundle_validates_the_examples_from_a_clean_directory(tmp_path):
    # Copy the script alone into an empty directory: no package on the path.
    script = tmp_path / "opi_verify.py"
    shutil.copy(BUNDLE, script)
    for ex in EXAMPLES:
        shutil.copy(ex, tmp_path / ex.name)
    r = subprocess.run([sys.executable, str(script), *[str(tmp_path / e.name) for e in EXAMPLES]],
                       capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.count("valid-signed") == len(EXAMPLES) >= 2


def test_bundle_json_report(tmp_path):
    r = _run("--json", str(EXAMPLES[0]), cwd=tmp_path)
    assert r.returncode == 0
    rep = json.loads(r.stdout)
    assert rep["status"] == "valid-signed" and rep["opi"] == 0
    assert any(c["name"].startswith("run[0] valid") for c in rep["checks"])


def test_bundle_fails_a_tampered_core_file(tmp_path):
    core = next(e for e in EXAMPLES if not e.name.endswith(".full.opi"))
    with zipfile.ZipFile(core) as zf:
        doc = json.loads(zf.read("manifest.json"))
    doc["machine_intelligence"][0]["producer"] = "someone-else"
    bad = tmp_path / core.name
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("manifest.json", json.dumps(doc, indent=2) + "\n")
    r = _run(str(bad), cwd=tmp_path)
    assert r.returncode == 1
    assert "invalid" in r.stdout and "signature does not verify" in r.stdout


def test_bundle_fails_a_full_file_with_a_smuggled_member(tmp_path):
    full = next(e for e in EXAMPLES if e.name.endswith(".full.opi"))
    bad = tmp_path / full.name
    shutil.copy(full, bad)
    with zipfile.ZipFile(bad, "a") as zf:
        zf.writestr("extensions/com.example/payload.bin", b"\0" * 8)
    r = _run(str(bad), cwd=tmp_path)
    assert r.returncode == 1 and "undeclared" in r.stdout


def test_bundle_rejects_not_an_opi(tmp_path):
    junk = tmp_path / "junk.opi"
    junk.write_bytes(b"[1,2,3]")
    r = _run(str(junk), cwd=tmp_path)
    assert r.returncode == 1 and "readable" in r.stdout


def test_builder_check_mode_agrees(tmp_path):
    r = subprocess.run([sys.executable, str(BUILDER), "--check"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
