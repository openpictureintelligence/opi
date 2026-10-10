## Appendix A — Annotated example

`examples/A001_C001.mov.opi`, produced end to end on 2026-08-29 from a 6 s
23.976 fps test clip registered into a latent store, one shot-detection run,
one human label. Verbatim, with commentary in the right margin.

```jsonc
{
  "opi": 0,                                  // first key; format major version
  "profile": "core",                         // matches the bytes: this file starts with "{"
  "generator": "latent 0.0.45",              // informative, unsigned
  "generated_at": "2026-08-29T13:30:43+00:00",
  "media_binding": {                         // signed by every run below
    "asset_id": "01a04db6-481c-7255-a87e-b426e1f2c130",
    "duration_s": 6.0,
    "shot_at": null,
    "camera": "Lavf61.7.100",
    "ingested_at": "2026-08-29T13:29:46+00:00",
    "timecode": {
      "start": "01:00:00:00",
      "recorded": "01:00:00:00",
      "rate": { "num": 24000, "den": 1001 }, // rational, never 23.976
      "drop_frame": false,
      "label": "23.976"                      // human-readable, derived
    },
    "files": [
      {
        "role": "original",                  // the sidecar lives beside this one
        "name": "A001_C001.mov",             // discovery hint
        "path": "A001_C001.mov",                 // informative, untrusted; a bare name here
        "size": 610380,
        "sha256": "81214813e87fdbb812a60675a5dc45637d5d40e69f899057bb5c8322abc8c07e", // THE binding
        "container": "mov,mp4,m4a,3gp,3g2,mj2",
        "video_codec": "h264",
        "audio_codec": "aac",
        "width": 640,
        "height": 360,
        "fps": 23.976
      }
    ],
    "provenance": [
      {
        "session_id": "01a04db6-479a-7e7e-adae-b6b2fe13357e",
        "original_path": "A001_C001.mov",
        "source_label": "A001",
        "checksum_verified_at": "2026-08-29T13:29:46+00:00",
        "note": null
      }
    ]
  },
  "machine_intelligence": [                  // one run per producer pass
    {
      "run_id": "d23f5d13c94f0918ab672cda134e80f5", // derived: sha256(JCS({producer, model_version, sha256}))[:32], see §7
      "producer": "shots:scenedetect",
      "model_version": "scenedetect-0.7",
      "generator": "latent 0.0.45",
      "facets": {                            // open in version 0
        "shots": [
          {
            "idx": 0,
            "confidence": null,
            "span": {
              "t_start_s": 0.0,
              "t_end_s": 5.964291666666667,
              "tc_in": "01:00:00:00",
              "tc_out": "01:00:06:00",        // exclusive
              "frames": 144,
              "frame_in": 0,
              "frame_out": 144
            }
          }
        ]
      },
      "signature": {                         // covers {media_binding, this run minus this key}
        "role": "machine_producer",
        "signer": "urn:openpicture:example:producer",
        "algorithm": "Ed25519",
        "public_key": "558273f79c8b304f1ad035f2201c01ceed02b71cb20f0ffbcccfee49c5cdcb15",
        "signed_at": "2026-08-30T01:15:39+00:00",
        "signature": "2XN6F6CXT1IJpGL9NIrLCdv6YyjnzR1VNJnGtbjyqW0+hy6eBbWC8e32Rrd8u/EhcEcc6omHSchRV4EZOZYsCw=="
      }
    }
  ],
  "editorial_annotations": {                 // never signed; the holder's
    "labels": [                              // the writer owns this key and preserves all others
      {
        "name": "select",
        "value": "hero",
        "created_by": "editor",
        "created_at": "2026-08-29T13:30:43+00:00",
        "span": {
          "t_start_s": 0.0, "t_end_s": 2.0,
          "tc_in": "01:00:00:00", "tc_out": "01:00:02:00",
          "frames": 48, "frame_in": 0, "frame_out": 48
        }
      }
    ]
  }
}
```

`examples/A001_C001.mov.full.opi` is the same manifest packed as a Full
container with `keyframes/shot_0000.webp` (7 636 B, STORE) and a 44-byte
`embeddings.bin` STORED at data offset 9152 (= 143 × 64). Both examples
validate `valid-signed` against the public key above; the corresponding
throwaway secret is `examples/example-producer.key`.
