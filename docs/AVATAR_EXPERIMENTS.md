# Avatar likeness experiments — 12 September 2026

The operator requested local Spark experiments after the first selfie avatar
completed but lost facial detail compared with the existing OpenAI illustration.
This experiment compares prompt and composition strategies using the supplied
portrait. It does not change stored profiles or send photographs to a cloud API.

**Selected result: candidate 01 with CPU background extraction.** The detailed
headless-body edit gives the closest likeness in this comparison. CPU extraction
preserves that Edit detail without another model redraw; Layered adds no visible
quality gain here and takes another 11 minutes 52 seconds. This is our visual
judgment of one portrait; the operator has not yet evaluated these new candidates.

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
- [x] Run each candidate sequentially on Spark and save RGB intermediates.
- [x] Compare likeness, face detail, body consistency and framing.
- [x] Test transparency on the strongest candidates and inspect light/dark edges.
- [x] Save a comparison sheet, select a preferred result and record limitations.
- [x] Verify GPU memory release, normal service availability and publish tooling.

## Three completed Edit comparisons

All three Edit runs completed on Spark on 12 September, between 09:49 and
10:30 UTC. Each returned a **1024 × 1024 RGB PNG** and exited with code 0.
These intermediate images have no alpha channel. The transparent CPU candidates
and the separate Layered result are evaluated below.

| Candidate | Visual assessment | Current selection |
| --- | --- | --- |
| 01 — headless body | More facial detail, a closed mouth and a closer expression; the face is too long/narrow and the curls exaggerated. | Selected for likeness, with CPU background extraction. |
| 02 — complete reference | Polished, compact cartoon, but retains the reference's toothy grin rather than the portrait's expression. | Less faithful expression despite a cleaner overall illustration. |
| 03 — head only | Simplified, more generic eyes, hair and beard; a slight neck-shading seam remains after composition. | Body consistency is strongest, but the face is less detailed than 01. |

This is an assessment of **one portrait**, not a general accuracy benchmark.
The prompt, crop/preprocessing and reference composition changed together;
the comparison does not establish which individual change caused an improvement.
Candidate 01 is our selected result; no user review of the new candidates is
claimed. No stored profile or default application prompt has changed, and no
new OpenAI request was made.

The private manifests provide these measured durations; total time includes
model import, loading, sampling, saving and child-process cleanup:

| Candidate | Model load (s) | Sampling (s) | Total supervisor time (s) |
| --- | ---: | ---: | ---: |
| 01 | 299.623 | 468.460 | 777.860 |
| 02 | 293.031 | 474.039 | 776.157 |
| 03 | 296.462 | 469.608 | 774.632 |

Host memory was sampled every five seconds, without read failures:

| Candidate | Samples | Available before (GiB) | Minimum available (GiB) | Available after (GiB) |
| --- | ---: | ---: | ---: | ---: |
| 01 | 158 | 112.124 | 52.629 | 111.388 |
| 02 | 158 | 111.315 | 52.901 | 112.230 |
| 03 | 157 | 112.164 | 50.457 | 111.887 |

All runs used Torch `2.13.0+cu130`, CUDA 13.0, BF16, the pinned Edit revision
`6f3ccc0b56e431dc6a0c2b2039706d7d26f22cb9`, and allocator fraction 0.70.
Available host memory recovered after each child exited. These host samples
are not a measurement of peak GPU allocation, and they do not prove the absence
of driver allocation warnings.

## Transparency comparison and final selection

All three CPU candidates pass the application's transparent-PNG validator as
**640 × 640 RGBA**. They have no visible pixels touching the outer image border
and no retained image metadata. `comparison-all.png` presents the previous
profile result and the three new candidates on light and dark backgrounds.

| Private result | Exact transparent pixels | Bytes |
| --- | ---: | ---: |
| `candidate-01.png` — selected | 60.522949% | 336,838 |
| `candidate-02.png` | 58.927246% | 359,693 |
| `candidate-03.png` | 63.159424% | 256,447 |

Candidate 03 combines the generated head with the original body. A manual crop
removes excess generated neck and restores the original collar wings omitted
by the flat headless reference. All **55,052 existing visible body pixels** were
verified unchanged before final framing/resampling to 640 pixels. A small neck
shading seam remains; preserving the body cannot recover missing facial detail.

The fourth run, **Layered-only from candidate 01's saved RGB**, completed at
**10:44:42 UTC** with exit code 0. It used the pinned Layered revision
`8f0ca708dfff6ba1dd5f2d85d78f8c108a040bcf`, seed 777, 50 steps, CFG 4,
resolution 640 and four layers, retaining the 0.70 allocator limit.

- Model load: **301.526 s**; sampling: **400.629 s**; total supervisor time:
  **711.742 s** (11 minutes 52 seconds).
- **145** host-memory samples, no read failures: **111.922 GiB** available
  before, **48.860 GiB** minimum and **112.230 GiB** after child exit.
- Four RGBA layers and a **640 × 640 RGBA** foreground PNG, **276,667 bytes**,
  with **73.575439%** exactly transparent pixels.

`transparency-comparison.png` shows that Layered retains the broad likeness,
with slight redrawing but no visible quality gain over the CPU result. This is
**not evidence that Layered caused the original coarse facial rendering**.
Both outputs render cleanly on light/dark composites. Independent alpha checks
of the CPU cutout before final framing and the Layered foreground found one
connected visible component at alpha ≥16 in each, no detached visible pixels
and no visible pixels in the outer 5% border. The Layered PNG has
6,136 fully transparent pixels with nonzero RGB values; these hidden values can
look like speckles in a raw channel viewer but are invisible when composited.
They are not evidence of a dirty rendered background. Transparency percentages
also reflect different framing; they are not a quality ranking.

The measured Edit-plus-Layered stages total **1,489.602 s** (24 minutes 50 seconds).
The selected candidate uses the **777.860 s** Edit stage followed by CPU extraction
and manual framing, avoiding another 711.742 seconds of model work. This was an
operator-run comparison, not a benchmark of a fully automatic replacement
pipeline. Border-connected white extraction can leave enclosed background holes
or halos and can remove pale foreground connected to the background; the selected
image was visually checked, but this method is not established for arbitrary photos.

The tooling passes **167 backend tests** and Ruff, including real subprocess
timeout/SIGTERM cleanup, shared-slot exclusion, consecutive low-memory checks,
metadata removal and exact body-pixel preservation. All four CI checks on
[PR 20](https://github.com/RomanNekrasov/PNBallie/pull/20) passed at commit
`82cfd1e1f50a23cdda2d44973096fdc364e6a3b2`.

## Final runtime checks and private archive

After the four model runs, the GPU slot was reusable and **112.170 GiB** of
host memory was available. The inference cgroup recorded **zero OOM events and
zero OOM kills**. These observations do not establish that every driver warning
was absent.

Authenticated probes from both acceptance and preview workers received the
expected **503 busy / Retry-After 30** while the fourth run owned the slot. After
completion, both saw **HTTP 200**, `processing: false`, and an empty request
returned **422 without a busy header**. Both app queues had zero active jobs.
Acceptance, preview and production health endpoints returned HTTP 200 during
model loading. The acceptance profile PNG's hash still matched its baseline
exactly; no selected experiment result was written to a profile.

All **28** files in the temporary Spark experiment directory were archived
privately on the Mac with matching SHA-256 hashes. Only that exact temporary
experiment directory was then removed from Spark; runtime code and model caches
remain. The ignored local archive retains the inputs, specs, intermediates,
layers, logs and memory records needed to reproduce the comparison.
`archive-evidence.json` and `final-live-evidence.json` record these checks.
The shared reservation code is installed in the private runtime; application
image pins, default prompt and stored profiles remain unchanged.

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
