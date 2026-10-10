"""`openpicture` — inspect, validate, pack, unpack, keygen, sign, doctor, keys, annotate, diff.

Standard library only, like everything in this package. Every command
takes `--json` for a machine-readable envelope on stdout; exit status is
0 for valid / success, 1 for an invalid file, 2 for usage errors.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path

from . import MANIFEST_MEMBER, __version__, annotate, companion, container, diff as diffmod, discover, ed25519, keys, sign, validate


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="openpicture", description=__doc__.splitlines()[0])
    ap.add_argument("--version", action="version", version=f"openpicture {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate", help="structural + signature validation")
    p.add_argument("path", nargs="+")
    p.add_argument("--media-dir", help="where to look for the bound media (default: beside the sidecar)")
    p.add_argument("--keylog", help="append-only key log; adds a trusted/unknown-signer column per run")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=_validate)

    p = sub.add_parser("inspect", help="print the manifest and container members")
    p.add_argument("path")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=_inspect)

    p = sub.add_parser("pack", help="Core JSON (+ members) -> Full container")
    p.add_argument("manifest", help="a Core .opi or manifest.json")
    p.add_argument("out")
    p.add_argument("--member", action="append", default=[], metavar="NAME=PATH",
                   help="add a member; *.bin and *.safetensors members are stored 64-byte aligned")
    p.set_defaults(fn=_pack)

    p = sub.add_parser("unpack", help="Full container -> directory")
    p.add_argument("path")
    p.add_argument("out_dir")
    p.set_defaults(fn=_unpack)

    p = sub.add_parser("keygen", help="write a new Ed25519 secret key (hex, mode 0600)")
    p.add_argument("out")
    p.set_defaults(fn=_keygen)

    p = sub.add_parser("sign", help="sign every unsigned producer run")
    p.add_argument("path", help=".opi to sign (rewritten in place; members kept)")
    p.add_argument("--key", required=True, help="secret key file from `opi keygen`")
    p.add_argument("--signer", required=True, help="who signs, e.g. urn:example:producer")
    p.add_argument("--role", default="machine_producer")
    p.set_defaults(fn=_sign)

    p = sub.add_parser("doctor", help="pair media and sidecars under a tree; report spec §9 states")
    p.add_argument("dir")
    p.add_argument("--verify-media", action="store_true", help="hash every paired master (slow on big trees)")
    p.add_argument("--repair", action="store_true", help="re-pair orphans by sha256 and rename them")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=_doctor)

    p = sub.add_parser("keys", help="append-only key log (B15 recommendation; optional trust anchor)")
    ksub = p.add_subparsers(dest="keys_cmd", required=True)
    k = ksub.add_parser("add", help="append a public key (or derive it from a secret) to the log")
    k.add_argument("log")
    k.add_argument("--key", required=True, help="32-byte hex public key, or a secret-key file from `opi keygen`")
    k.add_argument("--signer", required=True)
    k.add_argument("--note", default="")
    k.set_defaults(fn=_keys_add)
    k = ksub.add_parser("list", help="print the log")
    k.add_argument("log")
    k.add_argument("--json", action="store_true")
    k.set_defaults(fn=_keys_list)

    p = sub.add_parser("annotate", help="edit the human layer (editorial_annotations) and nothing else")
    p.add_argument("path")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="set a field; VALUE is parsed as JSON when it parses, else kept as a string")
    p.add_argument("--unset", action="append", default=[], metavar="KEY")
    p.add_argument("--label", action="append", default=[], metavar="NAME=VALUE")
    p.add_argument("--created-by", dest="created_by", default=f"openpicture {__version__}",
                   help="§8.2 created_by for --label: where the record came from (default: this tool)")
    p.add_argument("--by", default=None,
                   help="§8.2 by for --label: the human who formed the judgement, self-declared. "
                        "Never taken from your OS user name (§13) — say it or leave it out")
    p.add_argument("--at", default=None, help="§8.2 at for --label: RFC 3339, when the human judged")
    p.add_argument("--note", dest="notes", default=None, help="§8.2 notes for --label")
    p.add_argument("--anonymous", action="store_true",
                   help="strip `by` and `at` from every label before the file travels (§8.2)")
    p.set_defaults(fn=_annotate)

    p = sub.add_parser("diff", help="compare two manifests (runs by run_id, labels by id); exit 1 if the machine layer differs")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=_diff)

    p = sub.add_parser("companion", help="write a same-basename companion a MAM will pair (iconik JSON, flat JSON)")
    p.add_argument("path", nargs="+", help=".opi file(s)")
    p.add_argument("--kind", choices=companion.KINDS, default="iconik")
    p.add_argument("--dest", help="directory to write into (default: beside each .opi)")
    p.set_defaults(fn=_companion)

    args = ap.parse_args(argv)
    return args.fn(args)


def _validate(args) -> int:
    worst = 0
    entries = keys.load(args.keylog) if getattr(args, "keylog", None) else None
    for path in args.path:
        report = validate.validate(path, media_dir=args.media_dir)
        trust = None
        if entries is not None and report.ok:
            try:
                manifest, _ = container.read_manifest(path)
                trust = keys.trust_report(manifest, entries)
            except (ValueError, OSError):
                trust = None
        if args.json:
            d = report.as_dict()
            if trust is not None:
                d["trust"] = [{"run": t.index, "status": t.status, "trust": t.trust,
                               "signer": t.signer, "public_key": t.public_key, "note": t.note} for t in trust]
            print(json.dumps(d, indent=2))
        else:
            print(f"{report.status:14} {path}  (profile={report.profile}, opi={report.version}, signatures={report.signature_status})")
            for c in report.checks:
                if not c.ok or c.detail:
                    print(f"  {'ok  ' if c.ok else 'FAIL'} {c.name}: {c.detail}")
            for t in trust or []:
                extra = f" ({t.note})" if t.note else ""
                print(f"  {t.trust:15} run[{t.index}] {t.signer or '?'}{extra}")
        if not report.ok:
            worst = 1
    return worst


def _doctor(args) -> int:
    pairings = discover.scan(args.dir, verify_media=args.verify_media)
    renames = discover.repair(args.dir, pairings, apply=True) if args.repair else []
    if renames:
        pairings = discover.scan(args.dir, verify_media=args.verify_media)
    counts = discover.summarize(pairings)
    bad = sum(counts.get(s, 0) for s in discover.BAD_STATES)
    if args.json:
        print(json.dumps({"root": args.dir, "counts": counts, "renames": [r.as_dict() for r in renames],
                          "pairings": [p.as_dict() for p in pairings]}, indent=2))
    else:
        print(f"{args.dir}: {len(pairings)} pairing(s)")
        for state, n in counts.items():
            print(f"  {state:18} {n}")
        for p in pairings:
            if p.state not in ("paired", "paired-unverified"):
                who = p.sidecar or p.media
                print(f"  {p.state:18} {who}  {p.detail}")
        for r in renames:
            print(f"  renamed            {r.sidecar.name} -> {r.target}")
        if not args.repair:
            orphans = [p for p in pairings if p.state == "orphan"]
            if orphans:
                proposals = discover.repair(args.dir, pairings)
                for r in proposals:
                    print(f"  would re-pair      {r.sidecar.name} -> {r.target}  (run with --repair)")
    return 1 if bad else 0


def _keys_add(args) -> int:
    key = args.key
    from_secret = False
    if os.path.exists(key):
        key = Path(key).read_text().strip()
        from_secret = True
    entry = keys.add(args.log, key, args.signer, note=args.note, from_secret=from_secret)
    print(f"{entry.public_key}  {entry.signer}")
    return 0


def _keys_list(args) -> int:
    entries = keys.load(args.log)
    if args.json:
        print(json.dumps([e.as_dict() for e in entries], indent=2))
    else:
        for e in entries:
            print(f"{e.public_key}  {e.signer}  {e.added_at}  {e.note}")
    return 0


def _parse_value(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return text


def _annotate(args) -> int:
    fields = {}
    for spec in args.set:
        k, sep, v = spec.partition("=")
        if not sep or not k:
            print(f"--set expects KEY=VALUE, got {spec!r}", file=sys.stderr)
            return 2
        fields[k] = _parse_value(v)
    try:
        if fields:
            annotate.set_fields(args.path, fields)
        if args.unset:
            annotate.remove_fields(args.path, args.unset)
        for spec in args.label:
            name, sep, v = spec.partition("=")
            if not sep or not name:
                print(f"--label expects NAME=VALUE, got {spec!r}", file=sys.stderr)
                return 2
            annotate.add_label(args.path, name, _parse_value(v), created_by=args.created_by,
                               by=args.by, at=args.at, notes=args.notes)
        if args.anonymous:
            annotate.anonymize(args.path)
    except annotate.AnnotationRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    manifest, _ = container.read_manifest(args.path)
    print(json.dumps(manifest.get("editorial_annotations", {}), indent=2, ensure_ascii=False))
    return 0


def _diff(args) -> int:
    ma, _ = container.read_manifest(args.a)
    mb, _ = container.read_manifest(args.b)
    res = diffmod.diff(ma, mb)
    if args.json:
        print(json.dumps(res.as_dict(), indent=2, ensure_ascii=False, default=str))
    else:
        if res.identical:
            print("identical")
        for k, (x, y) in res.envelope.items():
            print(f"envelope     {k}: {x!r} -> {y!r}")
        for k, (x, y) in res.binding.items():
            print(f"binding      {k}: {_short(x)} -> {_short(y)}")
        for r in res.runs:
            facets = ", ".join(f"{k} {a}->{b}" for k, (a, b) in r.facets.items())
            sig = "" if r.signature == (None, None) else f"  signed {r.signature[0]} -> {r.signature[1]}"
            print(f"run {r.change:8} {r.run_id} {r.producer}@{r.model_version}  {facets}{sig}")
            if r.changed_facets:
                print(f"             changed: {', '.join(r.changed_facets)}")
        for e in res.labels.added:
            print(f"label added   {_label_line(e['id'], e['label'])}")
        for e in res.labels.changed:
            print(f"label changed {_label_line(e['id'], e['to'])}")
        for e in res.labels.removed:
            print(f"label removed {_label_line(e['id'], e['label'])}")
        for k, (x, y) in res.human.items():
            print(f"human        {k}: {_short(x)} -> {_short(y)}")
        if res.signature_status[0] != res.signature_status[1]:
            print(f"signatures   {res.signature_status[0]} -> {res.signature_status[1]}")
    return 0 if res.machine_identical else 1


def _short(v, n: int = 60) -> str:
    s = json.dumps(v, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[: n - 1] + "…"


def _label_line(lid, label) -> str:
    ident = lid if lid else "(no id)"
    return f"{ident}  {label.get('name')}={_short(label.get('value'), 40)}"


def _inspect(args) -> int:
    manifest, profile = container.read_manifest(args.path)
    members = []
    if container.detect(args.path) == "zip":
        with zipfile.ZipFile(args.path) as zf:
            for info in zf.infolist():
                entry = {"name": info.filename, "size": info.file_size,
                         "stored": info.compress_type == zipfile.ZIP_STORED}
                if info.filename != MANIFEST_MEMBER:
                    entry["data_offset"] = container.member_data_offset(args.path, info.filename)
                members.append(entry)
    if args.json:
        print(json.dumps({"profile": profile, "members": members, "manifest": manifest}, indent=2, ensure_ascii=False))
    else:
        print(f"profile: {profile}")
        for m in members:
            off = f" @{m['data_offset']}" if "data_offset" in m else ""
            print(f"  {m['name']:40} {m['size']:>10} B  {'STORE' if m['stored'] else 'DEFLATE'}{off}")
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


def _pack(args) -> int:
    manifest, _ = container.read_manifest(args.manifest)
    manifest["profile"] = "full" if args.member else "core"
    members: dict[str, bytes] = {}
    runs = manifest.get("machine_intelligence") or []
    if args.member and not runs:
        print("members attach to a producer run; the manifest has none", file=sys.stderr)
        return 2
    attachments = runs[-1].setdefault("attachments", {}) if args.member else {}
    if args.member and "signature" in runs[-1]:
        print("the last run is already signed; attach members before signing it", file=sys.stderr)
        return 2
    import hashlib
    for spec in args.member:
        name, _, src = spec.partition("=")
        if not name or not src:
            print(f"--member expects NAME=PATH, got {spec!r}", file=sys.stderr)
            return 2
        data = Path(src).read_bytes()
        members[name] = data
        attachments[name] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                             "media_type": _media_type(name)}
    container.write_full(manifest, args.out, members)
    print(args.out)
    return 0


def _unpack(args) -> int:
    if container.detect(args.path) != "zip":
        print("not a ZIP-form .opi", file=sys.stderr)
        return 1
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.path) as zf:
        for name in zf.namelist():
            target = (out / name).resolve()
            if not str(target).startswith(str(out.resolve())):
                print(f"refusing to extract outside {out}: {name}", file=sys.stderr)
                return 1
            zf.extract(name, out)
    print(out)
    return 0


def _keygen(args) -> int:
    secret = ed25519.generate_secret()
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(secret.hex() + "\n")
    print(f"secret: {args.out}\npublic: {ed25519.public_key(secret).hex()}")
    return 0


def _sign(args) -> int:
    secret = bytes.fromhex(Path(args.key).read_text().strip())
    manifest, _profile = container.read_manifest(args.path)
    n = sign.sign_all(manifest, secret, signer=args.signer, role=args.role)
    container.rewrite(args.path, manifest)
    print(f"signed {n} run(s) as {args.signer}")
    return 0



def _companion(args) -> int:
    for path in args.path:
        try:
            out = companion.write_companion(path, kind=args.kind, dest=args.dest)
        except (ValueError, OSError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            return 1
        print(out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


def _media_type(name: str) -> str:
    import mimetypes
    if name.endswith(".safetensors"):
        return "application/x-safetensors"
    guess, _ = mimetypes.guess_type(name)
    return guess or "application/octet-stream"
