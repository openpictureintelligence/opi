## Summary

<!-- What changed, and why? Link an issue when one exists. -->

## Change type

- [ ] Specification or schema
- [ ] Reference implementation
- [ ] Validator, test vector, or conformance tooling
- [ ] Documentation or project health

## Validation

- [ ] `python -m pytest -q`
- [ ] `python tools/opi_verify.py examples/*.opi`
- [ ] `python tools/build_bundle.py --check`
- [ ] `mkdocs build --strict`
- [ ] Other validation: <!-- command and result -->

## Compatibility and safety

- [ ] Existing unknown keys and human annotations are preserved where applicable.
- [ ] No media files are modified by the change.
- [ ] No secrets or private media are included.
- [ ] If the format changed, `SPEC.md`, schema, tests, vectors, and changelog are aligned.
