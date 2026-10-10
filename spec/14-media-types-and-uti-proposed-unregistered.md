## 14. Media types and UTI (proposed, unregistered)

| | Value |
|---|---|
| `.opi` file (Core and Full — both are ZIP, §3) | `application/vnd.openpicture.opi+zip` (RFC 6839 §3.6 structured suffix) |
| Bare manifest (internal form only, never a `.opi` file) | `application/vnd.openpicture.opi+json` |
| Extension | `.opi` |
| macOS UTI | `org.openpicture.opi`, conforming to `public.zip-archive` |
| Intended canonical reference URL | `https://openpictureintelligence.org/spec/` |

**None of these are registered.** The schema freeze that gated the IANA
vendor-tree registration closed on 2026-08-29 (B12, Appendix C); the filing
now waits on its own reference URL. `https://openpictureintelligence.org/spec/`
is the *intended* canonical reference URL for that filing, and a filing is
not made until that path actually serves this document — a registration
naming a URL that 404s is worse than no registration. Until a registration
is accepted, nothing about the format, this document or the documentation
site may imply that IANA has registered `.opi`. Because a `.opi` file is always a
ZIP (§3), one UTI conforming to `public.zip-archive` describes every file;
see §3.4 for the history of the two-form alternative.
