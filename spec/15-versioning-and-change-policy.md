## 15. Versioning and change policy

- `opi` is the only version number in the file. It changes only for
  incompatible changes: a required key removed or retyped, a signature
  payload change, a container rule change.
- Additive changes (new optional keys, new facets, new members) do not bump
  the version. Readers ignore what they do not know.
- `0` means *pre-freeze*: additive changes are expected and even the rules
  above may change with notice. `1` will be the first frozen version.
- The reference implementation's package version (`openpicture.__version__`)
  is independent of the format version.

---
