## 12. Reader requirements

A conforming reader:

1. detects the profile by bytes (§3.1), never by extension;
2. refuses an `opi` major it does not implement; ignores unknown keys
   otherwise (§5.3);
3. reads only `manifest.json` when it wants Core semantics from a Full file;
4. confirms `sha256` before trusting a sidecar against media it holds (§2.2);
5. treats `editorial_annotations` as mutable and unsigned (§8);
6. reports signature status per run and never collapses `partial` into
   `signed` (§9.4);
7. computes `.bin` offsets from the local header and tolerates unknown
   extra-field records (§4.4);
8. treats `files[].path` as untrusted text (§13);
9. treats `by` as a self-declared claim: never corroborated by a run
   signature, never rendered as though it were (§8.2, §13).

**Readers that keep a store.** A reader that ingests sidecars into its own
index will meet the same `run_id` twice with different content. It SHOULD
resolve that without asking a human, and SHOULD resolve it deterministically
— the reference producer takes a valid signature over an unsigned run, then
a more trusted key over a less trusted one, then the later `generated_at`,
and on a dead tie keeps what it already holds and reports the collision. The
loser SHOULD be retained as history rather than as a second current run, so
that "did we ever see a different answer" stays answerable while everything
downstream sees one (§7.3, §8.4). None of this is required by the file
format; it is stated here because every store hits it, and a store that
resolves it differently on each run is worse than one that resolves it
wrongly but predictably.

The consolidated list, cross-referenced by rule and including the time,
run-selection and sensitive-facet clauses, is the Reader class in §16.2.
