# E1a qualitative run: ETH3D HKairport01

## Run

- Accepted run: `E1a-eth3d-HKairport01-qual-20261104-002` (E1a–E6a extension workflow).
- Input: 240 RGB images, 2448×2048, from ETH3D HKairport01. The sequence provides `calibration.txt` (`fx=1444.43`, `fy=1444.34`, `cx=1179.5`, `cy=1044.9`) but no trajectory or paired depth/mesh GT.
- The intrinsics were converted to run-local `camera_intrinsics.yaml`; the effective MASt3R-SLAM config reported `use_calib: true` and `single_thread: true`.
- Host: RTX 5060; runtime 112.99 s; host-wide GPU memory peak 5,760 MiB over 564 samples.

## Outcome and scope

E1a exported 19 Keyframes at source frame ids `0, 131, 145–153, 160, 162–164, 167–169, 198`. The export gate passed. One source frame (154) was skipped by tracking; the event is preserved in the command log.

This is a qualitative tracking/association scene only. There is no trajectory or paired depth/mesh GT in the supplied sequence, so it is not included in E5a accuracy tables or the Replica scene-level averages.

An earlier attempt, `E1a-eth3d-HKairport01-qual-20261104-001`, also exported 19 Keyframes but printed `use_calib: false` despite receiving the intrinsics path. It is retained as a configuration failure and is superseded by run 002. The E1 launcher was fixed so a supplied calibration file sets `use_calib: true` in the run-specific config.

## Provenance

- E0a `preflight.json` SHA-256: `08351a4ab8dc7be6c129fe7aac415b34ad4e1a3f5717a237fdd4084ce917c3ce`.
- E1a `pointmaps/export_manifest.json` SHA-256: `9d7d3194f8202688248e1b67c1ae61c14abda4bab54b1e6a243bf6dae6ea0056`.
- Run-local intrinsics YAML SHA-256: `2ecfc29694836277ccb6503f1dc5a88079cc1636bdb40cb88ff2b4869b812a4e`.
- Input RGB mapping, original image hashes, pointmap hashes, runtime log, and skipped-frame record are under `runs/semantic_region_pointmap/E1a-eth3d-HKairport01-qual-20261104-002/`.
