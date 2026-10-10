# The specification, by chapter

`spec/` holds the normative text of Open Picture Intelligence, one chapter
per file, in the order listed in `CHAPTERS.txt`. `SPEC.md` at the repository
root is **generated** from these files by `python tools/build_spec.py` and
must not be edited directly — `tests/test_spec_build.py` fails on drift.

Edit a chapter, rebuild, commit both.
