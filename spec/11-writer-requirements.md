## 11. Writer requirements

- MUST write atomically: temp file in the target directory, `fsync`,
  atomic rename. Never patch in place.
- MUST NOT modify the media (§2.3).
- MUST name per §2.1 unless the caller supplies an explicit destination.
- MUST preserve the human layer on rewrite (§8.3).
- SHOULD be deterministic (§4.5, §7.7): same inputs → same bytes apart from
  `generated_at` and `signed_at`.
- SHOULD emit one run per producer pass (§7.2) and sign each run it is
  entitled to sign.
- MUST NOT emit members over 2 GiB (§4.6).
- Writing a sidecar is an *egress* of derived data. Producers operating
  under a data-egress policy MUST apply that policy at the write, not at
  the in-memory build.
- MUST NOT fill a label's `by` from an operating-system user name or an
  email address, and MUST NOT derive it from any signature, signer or machine
  run (§8.2, §8.4, §13). A writer that offers identity SHOULD also offer a way
  to remove it (`openpicture annotate --anonymous`).
- SHOULD omit `media_binding.files[].path` and `provenance[].original_path`;
  when a location is written it SHOULD be relative and MUST NOT be an absolute
  path, a home directory or a user name — a `.opi` travels and the value is
  never trusted (§6.2, §6.4, F3).
- MUST keep `host` a class and never an instance when it writes one: no
  hostname, user name, address or serial number goes under a signature
  (§7.2, §13).
- SHOULD keep a label's `id` stable across rewrites for as long as the label
  means the same thing, and SHOULD write only live labels — a label the
  writer has retracted is omitted, not written with a `null` value (§8.4).

The consolidated list a writer conforms to, cross-referenced by rule, is the
Producer class in §16.4.
