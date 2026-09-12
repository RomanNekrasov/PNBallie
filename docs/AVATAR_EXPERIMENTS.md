# Avatar likeness experiments — 12 September 2026

The operator requested local Spark experiments after the first selfie avatar
completed but lost facial detail compared with the existing OpenAI illustration.
This experiment compares prompt and composition strategies using the supplied
portrait. It does not change stored profiles or send photographs to a cloud API.

## Observations and plan

The existing result has coarse pixel features and generic eyes/hair. Its prompt
explicitly requests pixelation. The headless RGBA reference is converted directly
to RGB, making its transparent pixels black. These are separate possible causes
of weak likeness. The second Layered model may also change details, so the RGB
Edit result must be inspected before background extraction.

Three candidates use the same portrait crop, fixed seed 777, 40 Edit steps,
CFG 4 and the existing pinned Qwen models:

1. Add the portrait head to a headless figure on a padded white canvas, using a
   detailed cartoon instruction with no pixelation request.
2. Edit only the head/neck of the complete existing cartoon reference, preserving
   its body and using the portrait for identity.
3. Generate only a detailed cartoon head, then composite it onto the original
   transparent body. This separates face generation from exact body preservation.

The complete cartoon reference is an existing repository asset supplied to the
local experiment as a style/edit target. The ordinary application pipeline still
uses its headless reference. A comparison involving one portrait cannot establish
general identity accuracy for other people.

- [x] Inspect the selfie, existing result and reference alpha handling.
- [x] Save the experiment plan and private, metadata-free input specifications.
- [ ] Run each candidate sequentially on Spark and save RGB intermediates.
- [ ] Compare likeness, face detail, body consistency and framing.
- [ ] Test transparency on the strongest candidates and inspect light/dark edges.
- [ ] Save a comparison sheet, select a preferred result and record limitations.
- [ ] Verify GPU memory release, normal service availability and publish tooling.

## Reproducibility and data handling

Private input crops, exact prompt specifications, generated images and timings
live under the ignored `.local-test/avatar-experiments-20260912/` directory.
The root portrait is locally excluded from Git. No portraits, generated likenesses
or credentials belong in commits. Inputs are oriented and re-encoded without
photo metadata before transfer to the operator's Spark.

Each model stage runs in a fresh process, loads only pinned cached weights and
keeps the existing 0.70 CUDA allocator fraction. A process-shared GPU slot lets
normal avatar requests wait through the existing busy protocol while an
experiment owns the GPU. This reservation must be verified before model loading.
The HTTP service, databases and inference configuration retain their ordinary
application behavior; experimental prompts are private runner inputs.

## Running a comparison

`scripts/avatar_experiments.py` runs one Edit or Layered stage in the existing
Spark image. Its JSON specification accepts local input paths, ordered references,
the prompt, seed, dimensions, steps and CFG. `--validate-only` checks the inputs
without loading a model. Output directories must be new; the parent must exist.

```sh
python3 /app/scripts/avatar_experiments.py edit \
  --spec /cache/experiments/example/edit.json \
  --output /cache/experiments/example/outputs/edit
python3 /app/scripts/avatar_experiments.py layered \
  --spec /cache/experiments/example/layered.json \
  --output /cache/experiments/example/outputs/layered
```

Run inside the inference container with `PYTHONPATH=/app`, the existing read-only
model cache, and the same `/tmp/pnballie-avatar-gpu.lock` as the HTTP service.
The script's `--help` documents both specification formats. A supervisor keeps
the slot reserved until its fresh model child exits. It records host memory every
five seconds and stops only that child on timeout, SIGTERM, or two consecutive
readings below 12 GiB. Model children receive no service, cloud or database
credentials. This does not turn an external process into an application job.

Each output has a private manifest with input hashes/order, parameters, model
revisions, timings and status. Edit saves `edit.png`; Layered saves every original
layer and, when valid, `foreground.png`. The supervisor writes `memory.jsonl`
and a memory summary. Standard output contains bounded stage/progress messages.

`scripts/avatar_composite.py` provides three CPU-only comparison operations:

- `extract`: remove border-connected near-white background pixels; preserve
  enclosed whites. Inspect for halos, enclosed background holes and lost highlights.
- `compose`: place a manually cropped head on the original body, copying all
  visible body pixels exactly. Inspect the neck join and head proportions.
- `compare`: show images on light and dark backgrounds at the same scale.

These operations also require new output paths and write private PNG/metadata
files. They are explicit editing tools, not automatic face detection or a
general-purpose background segmentation model.
