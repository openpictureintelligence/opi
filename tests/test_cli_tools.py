"""CLI coverage for doctor / keys / annotate / diff and validate --keylog."""

import hashlib
import json
import re

from openpicture import cli, container, ed25519, sign, runs


def _clip(root, name="A001_C001.mov", body=b"movie", sign_with=None, signer="urn:p"):
    media = root / name
    media.write_bytes(body)
    m = {
        "opi": 0, "profile": "core",
        "media_binding": {"timecode": {"start": "00:00:00:00", "rate": {"num": 24, "den": 1}, "drop_frame": False}, "files": [{"role": "original", "name": name, "size": len(body),
                                     "sha256": hashlib.sha256(body).hexdigest()}]},
        "machine_intelligence": [{"run_id": runs.run_id("test:shots", "1", hashlib.sha256(body).hexdigest()),
                                  "producer": "test:shots", "model_version": "1",
                                  "facets": {"shots": [{"idx": 0, "confidence": 0.5, "span": {"frame_in": 0, "frame_out": 48}}]}}],
        "editorial_annotations": {},
    }
    if sign_with:
        sign.sign_all(m, sign_with, signer=signer)
    path = media.with_name(name + ".opi")
    container.write_core(m, path)
    return media, path


def test_doctor_text_json_and_repair(tmp_path, capsys):
    root = tmp_path / "archive"
    root.mkdir()
    media, side = _clip(root)
    (root / "B.mov").write_bytes(b"other")
    orphan_body = b"other"
    m = {"opi": 0, "profile": "core", "media_binding": {"timecode": {"start": "00:00:00:00", "rate": {"num": 24, "den": 1}, "drop_frame": False}, "files": [{"role": "original", "name": "gone.mov",
         "size": 5, "sha256": hashlib.sha256(orphan_body).hexdigest()}]}, "machine_intelligence": []}
    container.write_core(m, root / "gone.mov.opi")

    assert cli.main(["doctor", str(root)]) == 0
    out = capsys.readouterr().out
    assert "paired-unverified  1" in out and "orphan" in out and "would re-pair" in out

    assert cli.main(["doctor", str(root), "--verify-media", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["counts"]["paired"] == 1 and d["counts"]["orphan"] == 1 and d["counts"]["missing"] == 1

    assert cli.main(["doctor", str(root), "--repair", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["renames"][0]["applied"] is True and d["counts"] == {"paired-unverified": 2}

    # a mismatch makes the exit status 1
    media.write_bytes(b"changed")
    assert cli.main(["doctor", str(root), "--verify-media"]) == 1
    assert "mismatch" in capsys.readouterr().out


def test_keys_add_list_and_validate_keylog(tmp_path, capsys):
    root = tmp_path
    sk = ed25519.generate_secret()
    key_file = root / "k.hex"
    key_file.write_text(sk.hex() + "\n")
    _, side = _clip(root, sign_with=sk, signer="urn:lab")
    log = root / "keys.jsonl"

    assert cli.main(["validate", str(side), "--keylog", str(log)]) == 0
    assert "unknown-signer" in capsys.readouterr().out

    assert cli.main(["keys", "add", str(log), "--key", str(key_file), "--signer", "urn:lab", "--note", "laptop"]) == 0
    out = capsys.readouterr().out
    assert ed25519.public_key(sk).hex() in out and sk.hex() not in log.read_text()
    assert cli.main(["keys", "list", str(log)]) == 0
    assert "urn:lab" in capsys.readouterr().out
    assert cli.main(["keys", "list", str(log), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["note"] == "laptop"

    assert cli.main(["validate", str(side), "--keylog", str(log), "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["trust"][0]["trust"] == "trusted"

    # a raw public key works too
    assert cli.main(["keys", "add", str(log), "--key", "ab" * 32, "--signer", "urn:x"]) == 0


def test_annotate_cli(tmp_path, capsys):
    sk = ed25519.generate_secret()
    _, side = _clip(tmp_path, sign_with=sk)
    assert cli.main(["annotate", str(side), "--set", "rating=5", "--set", "notes=hero take",
                     "--set", 'tags=["a","b"]', "--label", "scene=42B",
                     "--created-by", "ae", "--by", "u-417"]) == 0
    ann = json.loads(capsys.readouterr().out)
    assert ann["rating"] == 5 and ann["notes"] == "hero take" and ann["tags"] == ["a", "b"]
    assert ann["labels"][0] == {**ann["labels"][0], "name": "scene", "value": "42B",
                                "created_by": "ae", "by": "u-417"}
    assert cli.main(["annotate", str(side), "--unset", "notes"]) == 0
    assert "notes" not in json.loads(capsys.readouterr().out)
    assert cli.main(["validate", str(side)]) == 0
    assert "valid-signed" in capsys.readouterr().out
    assert cli.main(["annotate", str(side), "--set", "novalue"]) == 2
    assert cli.main(["annotate", str(side), "--set", "labels=\"str\""]) == 1


def test_diff_cli(tmp_path, capsys):
    a_dir, b_dir = tmp_path / "a", tmp_path / "b"
    a_dir.mkdir(), b_dir.mkdir()
    _, a = _clip(a_dir)
    _, b = _clip(b_dir)
    assert cli.main(["diff", str(a), str(b)]) == 0
    assert capsys.readouterr().out.strip() == "identical"

    m, _ = container.read_manifest(b)
    m["editorial_annotations"]["rating"] = 4
    container.write_core(m, b)
    assert cli.main(["diff", str(a), str(b)]) == 0   # human-only change: machine identical
    assert "human        rating" in capsys.readouterr().out

    m["machine_intelligence"].append({"run_id": "r9", "producer": "test:asr", "model_version": "3", "facets": {"signals": [{"confidence": 1.0}]}})
    container.write_core(m, b)
    assert cli.main(["diff", str(a), str(b), "--json"]) == 1
    d = json.loads(capsys.readouterr().out)
    assert d["runs"][0]["change"] == "added" and d["machine_identical"] is False


def test_examples_diff_core_vs_full():
    from pathlib import Path
    ex = Path(__file__).resolve().parent.parent / "examples"
    rc = cli.main(["diff", str(ex / "A001_C001.mov.opi"), str(ex / "A001_C001.mov.full.opi")])
    assert rc == 1  # the Full example's run carries attachments the Core one lacks


def test_diff_renders_labels_by_id(tmp_path, capsys):
    a_dir, b_dir = tmp_path / "a", tmp_path / "b"
    a_dir.mkdir(), b_dir.mkdir()
    _, a = _clip(a_dir)
    _, b = _clip(b_dir)
    for path, labels in ((a, [{"id": "l1", "name": "select", "value": "hero", "created_by": "u"},
                              {"id": "l2", "name": "scene", "value": "42B", "created_by": "u"}]),
                         (b, [{"id": "l1", "name": "select", "value": "runner-up", "created_by": "u"},
                              {"id": "l3", "name": "take", "value": 2, "created_by": "u"}])):
        m, _ = container.read_manifest(path)
        m["editorial_annotations"] = {"labels": labels}
        container.write_core(m, path)
    assert cli.main(["diff", str(a), str(b), "--json"]) == 0   # human-only: machine identical
    d = json.loads(capsys.readouterr().out)
    assert [e["id"] for e in d["labels"]["changed"]] == ["l1"]
    assert [e["id"] for e in d["labels"]["removed"]] == ["l2"]
    assert [e["id"] for e in d["labels"]["added"]] == ["l3"]

    assert cli.main(["diff", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert re.search(r"label changed\s+l1", out)
    assert re.search(r"label removed\s+l2", out)
    assert re.search(r"label added\s+l3", out)


def test_python_m_openpicture_runs_the_cli():
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, "-m", "openpicture", "--version"],
                       capture_output=True, text=True, cwd=root)
    assert r.returncode == 0, r.stderr
    assert "openpicture" in r.stdout
