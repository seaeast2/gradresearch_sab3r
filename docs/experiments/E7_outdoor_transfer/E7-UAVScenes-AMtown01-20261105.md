# E7 outdoor transfer: UAVScenes AMtown01

**Run:** `E7-uav-amtown01-postprocess-20261105-002`  
**E1a source:** `E7-uav-amtown01-test-20261105-006`  
**Pipeline status:** E1a, E2a, E3a, E4a, and E7 report completed.  
**Research interpretation:** inconclusive for semantic refinement transfer.

## Registered input and protocol

- Dataset: UAVScenes `AMtown01`, outdoor drone imagery.
- Input: 240 registered JPEG mapping frames sampled at 5 Hz from the 60–120 s interval. Held-out RGB was excluded.
- The original RGB timestamps were joined to staged frames. MASt3R-SLAM used forced Keyframes at 1 s intervals and exported 51 Keyframes.
- E2a used the fixed outdoor prompt set in `configs/e7_amtown01_semantic_prompts.json`, at 384 px long edge to fit the 8 GiB GPU. The result scores were mapped back to the E1a 512×416 pixel grid.
- E4a used only `road`, `ground`, `roof`, and `facade` as planar candidates. The 2.04× local-spacing selection threshold and optimizer gates came from two indoor validation scenes and were transferred unchanged; they have not been validated outdoors.
- LiDAR and reference poses were not used for mapping or refinement. This E7 run did not compute a paired LiDAR accuracy metric.

## Results

| Stage | Result |
|---|---|
| E1a SLAM export | 240 RGB frames; 51 Keyframes; completed |
| E2a semantic scores | 51/51 Keyframes; 10,862,592 pixels scored; all pixels were classified as `other` (100%); the other 11 labels received 0 pixels |
| E3a temporal association | 213 persistent Regions; 48 accepted of 1,485 candidate links; 1,437 rejected |
| E4a local refinement | 213 Regions checked; 0 selected, 0 rolled back, 0 pixels modified; non-target points remained exactly unchanged |

The semantic label distribution collapsed to `other`, so E3a's accepted links are geometric associations over a single semantic class. Their correctness was not checked against physical correspondences. E4a did not alter the map because no Region passed the planar semantic selection; 210 candidates also failed other frozen gates, while 3 failed only the planar-label requirement.

## Conclusion and limits

The full outdoor input completed E1a–E4a without a runtime failure after the GPU-compatible 384 px setting was used. This demonstrates that the stages can process the sequence, but it does **not** demonstrate successful outdoor semantic transfer or a geometric accuracy improvement. In this run, semantic classification was unusable for Region selection, refinement was a no-op, and no paired LiDAR metric was computed. The appropriate E7 result is **inconclusive**, not evidence that outdoor refinement helps or does not help.

This is one UAVScenes scene. The broad `other outdoor scene content` prompt dominated the fixed CLIP argmax; changing prompts after inspecting this test output would be a new exploratory run and is not included here. The frozen refinement threshold also comes from indoor scenes, so even a nonzero update would need outdoor validation.

## Provenance

- E1a export manifest SHA-256: `9e65c5607acf717f1ff22eb475d84e9be30c6493b47af138d6a61c6742f6edb6`
- E2a manifest SHA-256: `b07b270aff4f0b325dcddad15b4bd0dd3842d29ce729109c98718dff5220aad1`
- E3a temporal Regions SHA-256: `d2eee6892f67a9a5282561f697a75e688a61e61b6d2994208201469f186895c9`
- E4a refinement summary SHA-256: `ed097e3fb8b59ae2d32cfbf7940966d3ab04e8fbfcc6b297ea918a12706fc1b4`
- SAB3R prompt config SHA-256: `866cc717d7d815f8727f4d33a3f67dc9ffd823e833a2915d86b11593d3f43d01`
- Run artifacts: `runs/semantic_region_pointmap/E7-uav-amtown01-postprocess-20261105-002/`
