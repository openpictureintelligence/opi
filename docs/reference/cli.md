# Command line

The `openpicture` command ships with the reference implementation. Every subcommand takes `--help`; the text below is generated from the installed CLI. Exit status is 0 for success or a valid file, 1 for an invalid file or a doctor tree with problems, 2 for usage errors. The same CLI runs without the console script as `python -m openpicture`.

```text
usage: openpicture [-h] [--version]
                   {validate,inspect,pack,unpack,keygen,sign,doctor,keys,annotate,diff,companion} ...

`openpicture` — inspect, validate, pack, unpack, keygen, sign, doctor, keys, annotate, diff.

positional arguments:
  {validate,inspect,pack,unpack,keygen,sign,doctor,keys,annotate,diff,companion}
    validate            structural + signature validation
    inspect             print the manifest and container members
    pack                Core JSON (+ members) -> Full container
    unpack              Full container -> directory
    keygen              write a new Ed25519 secret key (hex, mode 0600)
    sign                sign every unsigned producer run
    doctor              pair media and sidecars under a tree; report spec §9 states
    keys                append-only key log (B15 recommendation; optional trust anchor)
    annotate            edit the human layer (editorial_annotations) and nothing else
    diff                compare two manifests (runs by run_id, labels by id); exit 1 if the
                        machine layer differs
    companion           write a same-basename companion a MAM will pair (iconik JSON, flat JSON)

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
```

## `openpicture validate`

Structural and signature validation of one or more files. Reports per check and per run; `--keylog` adds a trusted / unknown-signer column from an append-only key log; `--json` emits the report as JSON.

```text
usage: openpicture validate [-h] [--media-dir MEDIA_DIR] [--keylog KEYLOG] [--json]
                            path [path ...]

positional arguments:
  path

options:
  -h, --help            show this help message and exit
  --media-dir MEDIA_DIR
                        where to look for the bound media (default: beside the sidecar)
  --keylog KEYLOG       append-only key log; adds a trusted/unknown-signer column per run
  --json
```

## `openpicture inspect`

Prints the manifest and, for a Full file, every member with its size, compression and data offset.

```text
usage: openpicture inspect [-h] [--json] path

positional arguments:
  path

options:
  -h, --help  show this help message and exit
  --json
```

## `openpicture pack`

Builds a Full file from a manifest (a Core `.opi` or a bare `manifest.json`) plus members. Members attach to the last run and are declared in its `attachments` with SHA-256 and size; `*.bin` and `*.safetensors` members are stored 64-byte aligned. Attach before signing — members sit under the run's signature.

```text
usage: openpicture pack [-h] [--member NAME=PATH] manifest out

positional arguments:
  manifest            a Core .opi or manifest.json
  out

options:
  -h, --help          show this help message and exit
  --member NAME=PATH  add a member; *.bin and *.safetensors members are stored 64-byte aligned
```

## `openpicture unpack`

Extracts a Full file to a directory, refusing member names that escape it.

```text
usage: openpicture unpack [-h] path out_dir

positional arguments:
  path
  out_dir

options:
  -h, --help  show this help message and exit
```

## `openpicture keygen`

Writes a new Ed25519 secret key as hex, mode 0600, and prints the public key.

```text
usage: openpicture keygen [-h] out

positional arguments:
  out

options:
  -h, --help  show this help message and exit
```

## `openpicture sign`

Signs every unsigned run in a Core file in place. For a Full file, sign the manifest before packing.

```text
usage: openpicture sign [-h] --key KEY --signer SIGNER [--role ROLE] path

positional arguments:
  path             .opi to sign (rewritten in place; members kept)

options:
  -h, --help       show this help message and exit
  --key KEY        secret key file from `opi keygen`
  --signer SIGNER  who signs, e.g. urn:example:producer
  --role ROLE
```

## `openpicture doctor`

Walks a media tree and pairs every clip with its sidecar (two-dot name first, stem form as a fallback), reporting one state per pair: `paired`, `paired-unverified`, `missing`, `orphan`, `mismatch`, `duplicate`, `newer-schema`, `tampered`, `unreadable`. `--verify-media` hashes every master; `--repair` re-pairs orphans by SHA-256 and renames them. Exit 1 on mismatch, tampered or unreadable.

```text
usage: openpicture doctor [-h] [--verify-media] [--repair] [--json] dir

positional arguments:
  dir

options:
  -h, --help      show this help message and exit
  --verify-media  hash every paired master (slow on big trees)
  --repair        re-pair orphans by sha256 and rename them
  --json
```

## `openpicture keys`

Maintains an append-only key log (JSON Lines). `add` records a public key — given directly or derived from a secret-key file, so the secret never lands in the log — with its signer and a note; `list` prints it.

```text
usage: openpicture keys [-h] {add,list} ...

positional arguments:
  {add,list}
    add       append a public key (or derive it from a secret) to the log
    list      print the log

options:
  -h, --help  show this help message and exit
```

```text
usage: openpicture keys add [-h] --key KEY --signer SIGNER [--note NOTE] log

positional arguments:
  log

options:
  -h, --help       show this help message and exit
  --key KEY        32-byte hex public key, or a secret-key file from `opi keygen`
  --signer SIGNER
  --note NOTE
```

```text
usage: openpicture keys list [-h] [--json] log

positional arguments:
  log

options:
  -h, --help  show this help message and exit
  --json
```

## `openpicture annotate`

Edits `editorial_annotations` and nothing else. Refuses any edit that would change the machine layer; re-verifies signatures afterwards. Values given to `--set` are parsed as JSON when they parse.

`--created-by` records where a label came from and defaults to this tool; `--by` records which human formed the judgement and has no default, because §13 forbids taking it from your OS user name. `--anonymous` strips `by` and `at` from every label before a file travels, and leaves `created_by` alone — §8.2 requires it.

```text
usage: openpicture annotate [-h] [--set KEY=VALUE] [--unset KEY] [--label NAME=VALUE]
                            [--created-by CREATED_BY] [--by BY] [--at AT] [--note NOTES]
                            [--anonymous]
                            path

positional arguments:
  path

options:
  -h, --help            show this help message and exit
  --set KEY=VALUE       set a field; VALUE is parsed as JSON when it parses, else kept as a string
  --unset KEY
  --label NAME=VALUE
  --created-by CREATED_BY
                        §8.2 created_by for --label: where the record came from (default: this
                        tool)
  --by BY               §8.2 by for --label: the human who formed the judgement, self-declared.
                        Never taken from your OS user name (§13) — say it or leave it out
  --at AT               §8.2 at for --label: RFC 3339, when the human judged
  --note NOTES          §8.2 notes for --label
  --anonymous           strip `by` and `at` from every label before the file travels (§8.2)
```

## `openpicture diff`

Compares two manifests block by block: binding fields, runs added/removed/changed by `run_id`, human labels added/changed/removed by `id` (a label without an `id` is matched on its `name`, `value` and `span`), other human-layer changes, signature status. Exit 0 when the machine layer is identical.

```text
usage: openpicture diff [-h] [--json] a b

positional arguments:
  a
  b

options:
  -h, --help  show this help message and exit
  --json
```

## `openpicture companion`

Writes a same-basename companion a MAM will pair — iconik's documented sidecar JSON shape or a flat one-level JSON — beside the `.opi` or into `--dest`. Companions are lossy projections and carry no signatures.

```text
usage: openpicture companion [-h] [--kind {iconik,flat}] [--dest DEST] path [path ...]

positional arguments:
  path                  .opi file(s)

options:
  -h, --help            show this help message and exit
  --kind {iconik,flat}
  --dest DEST           directory to write into (default: beside each .opi)
```
