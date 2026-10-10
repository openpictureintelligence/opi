# Build with `.opi`

`.opi` is useful at the seam between a tool that produces intelligence and a
tool that needs to use it. This section covers both sides, plus the smallest
integration that is worth doing first.

Start with the job you need to do. You do not need to implement the whole
format before reading one file or putting a validation gate in front of an
import.

| You are | Start with |
|---|---|
| Writing a tool that analyses footage and should leave its results beside the media | [Producer workflow](producers.md) |
| Writing a tool, script or pipeline that should read those results | [Consumer workflow](consumers.md) |
| Deciding whether `.opi` fits at all, and want the least work that proves it | [The smallest useful integration](integration.md) |
| Mapping `.opi` fields to or from an existing standard or vendor format | [Interoperability](interop.md) |

## The boundary to keep

The media remains the source asset. A producer writes a sidecar beside it; a
consumer reads the fields it understands; a validator checks the relationship
before a pipeline trusts the claims. `.opi` does not replace an NLE, MAM,
archive or model.

Two things hold for every side:

- **The format is the contract; the reference implementation is Python.** A
  producer or consumer may be written in any language against the
  [specification](../spec/index.md). The `openpicture` package and the
  single-file validator demonstrate the reference behaviour and are the
  quickest way to check an implementation.
- **Validate before trusting.** A `.opi` states who claimed what about which
  media. `openpicture validate` (or the [standalone
  validator](../reference/validator.md)) checks the binding, members and
  signatures. Consumers that act on the claims should prefer runs whose
  signature verified.
