# Status

**As of 2026-10-09.** Format version **0, pre-freeze**. Reference
implementation `openpicture` **0.0.10**. Every claim on this page is tied
to that date or that version; when they move, this page moves.

## What "pre-freeze" means

`"opi": 0` in a manifest means the rules can still change, with notice, and
that additive change is expected. Readers are required to ignore fields
they do not understand, which is what makes additions safe. `"opi": 1` will
be the first frozen version; nothing is promised about when.

## Implemented and stable enough to build against

These are in the specification as MUST, implemented in `openpicture`,
tested, and checked by the standalone validator.

| Area | Decided |
|---|---|
| Physical form | A `.opi` is a ZIP; `manifest.json` first; Core = manifest only, Full = manifest plus members; profile from contents. A bare JSON manifest is an internal form, not a deliverable. |
| Naming and binding | `<media>.opi` beside the media (two-dot); binding by SHA-256, size and name; the media is never modified; `path` is informative and untrusted. |
| Container | ISO/IEC 21320-1 profile; aligned members (`.safetensors`, `.bin`) STOREd at 64-byte offsets via a local extra field; members ≤ 2 GiB; every member declared and hashed on a run; reserved directories `embeddings/`, `keyframes/`, `extensions/`. |
| Envelope | Integer `opi` as first key; readers ignore unknown keys; rational rate `{num, den}`; integer frame positions with exclusive out-points. |
| Runs | One run per producer pass; `run_id` derived from producer, model version and media hash; required run fields; every facet entry has `confidence` (number or `null`). |
| Signatures | Ed25519 over the RFC 8785 canonical form of `{media_binding, run}`, per run; status reported per run; unsigned is valid. |
| Keys | Append-only key log; public keys never withdrawn; the public key hex is the key id. |
| Human layer | `editorial_annotations` never signed, preserved on rewrite; read-back rules for producers that import it. Labels are matched by stable `id` when diffing; non-`labels` clauses are carried forward verbatim and never re-projected. `by` is a self-declared human claim and is never derived from a signature or a machine run. |
| Embeddings spans | Frame-exact `frame_spans` `[count, 2]` I64 preferred; the millisecond `spans` tensor is the backward-compatible fallback (0.0.9). |
| Sensitive facets | Facets about people or rights are review flags with `review_required: true`; no accuracy claim may travel in the file. |

## Public alpha access

The source repository is public at
[openpictureintelligence/opi](https://github.com/openpictureintelligence/opi).
Read, install, propose integrations, and report issues without a collaborator
invitation. Public availability does not freeze version 0 or establish
compatibility with an editor or MAM. `openpicture` is not on PyPI; consumers
should pin a validated source commit.

Documentation builds on every push. GitHub Pages publication is controlled by
`PAGES_ENABLED` after Pages is configured. The `.org` and `.io` DNS rollout
remains a separate steward action.

## Implemented, provisional

In the code and documented, expected to change before the freeze.

- **The unfrozen half of the facet vocabulary** — B12 closed on 2026-08-29
  and froze seven facets plus the embeddings attachment form; Appendix C is
  normative for those. The rest (`description`, `shot_size`, `composition`,
  `focus`, `take`, `continuity`, `clearance`, `text_on_screen`, `persons`,
  `audio_events`) are still proposals a validator does not reject a file
  for disagreeing with.
- **MAM companions** — `openpicture companion` writes iconik-shaped and flat
  JSON beside the `.opi`. CatDV XML and XMP are not written.
- **Embeddings metadata** — the required `__metadata__` keys in a
  safetensors member were set on 2026-08-29 and may still gain fields.
- **Producer conformance tooling (0.0.9)** — `tools/conformance/producer.py`
  reports each §16.4 P-check as pass, fail or unavailable and keeps the
  file-decidable checks separate from producer obligations and checks that
  need external evidence. Validator acceptance is not producer conformance.
- **CLI entry point (0.0.9)** — the `openpicture` console script and
  `python -m openpicture` run the same command; `openpicture diff` reports
  human labels by stable `id`.

## Not promised yet

- **Registrations.** `application/vnd.openpicture.opi+zip` and the macOS UTI
  `org.openpicture.opi` are drafted, not filed. Filing waits on the freeze.
- **Distribution.** `openpicture` is not on PyPI. Install from a checkout.
- **A Quick Look preview, a viewer, a hosted service.** Not part of the
  format. A Finder preview extension is a plausible later tool.
- **Adoption or compatibility claims.** The only producer is latent; the
  only tested consumers are `openpicture` itself and the readers on the
  [build pages](build/index.md). No editor or asset manager reads `.opi`
  natively; companions exist for that reason.

## Publication plan

Updated 2026-10-09. The repository is owned by the `openpictureintelligence`
organisation. The documentation site is built on every push; whether it is
published depends on the repository variable below.

| | Status |
|---|---|
| `openpictureintelligence.org` | **Registered** (Cloudflare). Carries the canonical, permanent specification URL: `https://openpictureintelligence.org/spec/`. Must never blanket-redirect elsewhere — `/spec/*` resolves here for good. Intended IANA reference URL; no registration has been made or accepted. |
| `openpicture.io` | **Registered** (Cloudflare). The human-facing project home. Non-spec paths may live here or redirect; the spec does not. |
| GitHub organisation `openpictureintelligence` | Created with a public organization profile. **Public alpha source available**; repository, Pages and documentation URLs use this organization. |
| GitHub Pages | Workflow ready; deploy gated on repository variable `PAGES_ENABLED`. Publication is enabled after the repository is public and Pages is configured. |

Sequence: ~~transfer `opi` and update repository, Pages and documentation
URLs~~ → ~~strict docs build passes~~ → enable Pages from the
organization-owned repository → point the `.org` at Pages with `/spec/`
served → wire the `.io`. Making the repository public, enabling Pages and
all DNS remain steward actions.

## Reference implementation

`openpicture` — standard-library Python 3.11+, 400+ tests including the
RFC 8785 and RFC 8032 vectors and an OpenSSL interoperability check; CI on
Linux and macOS across Python 3.11–3.14, plus a job that runs the
single-file validator alone in an empty directory. Package versions stay at
`0.0.x` during the public, pre-freeze alpha; the format version and the
package version are independent.

## Changelog

The software changelog is `CHANGELOG.md` in the repository, included here.

--8<-- "CHANGELOG.md"
