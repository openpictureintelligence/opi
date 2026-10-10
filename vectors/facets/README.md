# Facet vectors

`valid-<facet>.json` — one conformant entry per facet in Appendix C. The
`stable` facets (`exposure_color`, `energy_curve`, `camera_motion`,
`audio_usability`) were taken from a real latent run on real footage
(2026-08-29 pilot store); the rest are fabricated to the appendix.

`invalid-*.json` — entries that `openpicture.facets.checks()` must flag;
`expect_failure_in` names the check that fires.

Each file: `{"facet": name, "entry": entry | [entries], "expect_failure_in"?: str}`.
