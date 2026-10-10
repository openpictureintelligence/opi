## 13. Security considerations

- **No confidentiality.** A `.opi` is readable by anyone who can read the
  file. Do not put secrets in it. Encryption is deliberately out of scope;
  it would defeat zero-tooling ingestion.
- **Signatures assert origin and integrity of a run, not truth.** A valid
  signature means the named key signed these facets about this media. It
  says nothing about whether the model was right.
- **Key custody is out of scope; key history is not.** Loss or compromise
  of a producer key is handled by the append-only key log (§9.3): mark,
  re-sign, never delete. A verifier with the log can tell a legitimate
  historical signature from one made by a key added after the fact.
- **`files[].path`, `provenance`, `generator` and all human-layer text are
  untrusted input.** Never use `path` to open files without the same
  checks you would apply to any user-supplied path.
- **Unpacking.** Implementations that extract Full containers MUST reject
  member names that escape the target directory (`../`, absolute paths).
- **Resource limits.** Readers SHOULD cap the manifest size they will parse
  and the member sizes they will hash; producers SHOULD move very long
  arrays into members rather than the manifest. Members over 2 GiB are
  forbidden (§4.3).
- **Downgrade.** A reader MUST NOT treat a missing signature as equivalent
  to a valid one. `unsigned` is a distinct, visible status.
- **Human layer.** Because it is unsigned, nothing in it can be attributed.
  Systems that need attributable human annotations should record them as a
  signed run by a human-operated producer key, not in `editorial_annotations`.
- **`host` is a fingerprint if you let it be.** The `host` object (§7.2)
  names a class of machine — os, arch, accelerator — and MUST NOT name an
  instance. A hostname, user name, IP or serial number written there is
  under the run signature and so cannot be removed later without destroying
  the signature: the leak is permanent for the life of the run. Producers
  MUST populate `host` from the platform's coarse identifiers only, and
  validators SHOULD reject values outside the enumerations.
- **Human-layer identity is a claim, never a proof.** `by` (§8.2) is
  self-declared text that anyone holding the file can write or change, and
  a reader MUST NOT derive it from — or corroborate it with — any run
  signature; the two layers are unrelated by construction (§9.2). Tools
  SHOULD default to an opaque account identifier rather than a legal name,
  MUST NOT populate `by` from an OS user name or an email address, and
  SHOULD offer a way to strip `by` and `at` before a file travels
  (`openpicture annotate --anonymous`).
