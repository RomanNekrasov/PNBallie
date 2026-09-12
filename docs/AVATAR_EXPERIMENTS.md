# Avatar likeness experiments — 12 September 2026

The operator requested local Spark experiments after the first selfie avatar
completed but lost facial detail compared with the existing OpenAI illustration.
This experiment compares prompt and composition strategies using the supplied
portrait. It does not change stored profiles or send photographs to a cloud API.

**Preferred generated result: photographic candidate 05, extraction threshold 225.** After the user found
the first three candidates too illustrated, the selfie-first follow-up produced
a more recognizable face with natural hair and skin detail. The CPU composition
of actual selfie pixels remains the unchanged-face comparison. The first
comparison and its superseded preference for candidate 01 remain recorded below.

## Follow-up plan: photographic likeness

Before generation, the follow-up was limited to one additional local Qwen Edit
trial and a CPU photographic comparison:

1. Use the selfie as **image 1**, the primary edit and identity target. Use the
   headless body as **image 2**, a supporting reference for the shirt, pose, rod
   and ball. Request a photographic face with natural proportions, skin/hair
   texture and the original expression; omit pixelation, caricature and ink
   outlines. Keep the body and plain white canvas as composition constraints.
2. Keep the already pinned `Qwen-Image-Edit-2511` weights, seed **777**, **40**
   steps, CFG **4**, BF16 and the **0.70** allocator cap. Run one Edit stage and
   inspect its RGB result before deciding whether further processing is useful.
3. Independently prepare a private CPU composition using the **actual selfie
   pixels** for the head and the existing body. Cropping, masking and placement
   provide a comparison without asking a model to redraw the face.
4. Compare recognizability, natural facial detail, proportions and the neck/body
   join. Choose the stronger result and record remaining limitations. This is
   still one portrait, not a general model benchmark or an automatic production
   pipeline.

- [x] Record the user's realism feedback and this bounded follow-up plan.
- [x] Run the single photographic-face Edit trial on Spark.
- [x] Prepare the CPU composition from the actual portrait pixels.
- [x] Compare the two approaches and select a result.
- [x] Validate transparency, runtime recovery and private artifact cleanup.

The portrait, exact prompts and generated images remain private. This follow-up
does not publish a new profile avatar, change the default generation prompt or
call OpenAI. GPU work uses the existing shared reservation and fresh-child
supervisor.

### Photographic CPU comparison prepared

The private result is
`.local-test/avatar-realism-20260912/photo-composite/best-natural-neck.png`.
It uses the actual selfie pixels with a manually traced silhouette and normal
resizing: no model redraw, facial retouching, beautification or color adjustment.
The face is easier to recognize in the visual review, and the refined neck join
looks more natural than the first placement. It provides the comparison using
actual face pixels alongside the generated photographic candidate below.

The neck refinement replaces **1,522 exposed original neck pixels** with sampled
selfie neck pixels. All **53,530 other visible original body pixels** are
preserved before final framing/resampling, including the shirt, collar outlines,
rod and ball. Face pixels and alpha are unchanged by that refinement. A short
blend joins the sampled neck to the placed photographic head.

The finished PNG passes the application's transparent-image validator:
**640 × 640 RGBA**, **277,565 bytes**, **66.3467%** exactly transparent pixels,
no EXIF and no visible outer-border pixels. Light/dark comparisons include the
initial placement and refined neck join.

This is visibly a photographic face on an illustrated body. Fine hair flyaways
are manually approximated, and the silhouette/neck placement is specific to this
portrait. It is not an automatic segmentation workflow. The private `NOTES.md`,
metadata and replay scripts preserve the mask and placement choices; they are
not committed with the documentation.

### Photographic Qwen Edit result

Candidate **05** completed on Spark from **11:02:50 to 11:16:00 UTC** with exit
code 0. It used the selfie as the first identity/edit input and the headless
body as the supporting reference, with photographic rather than illustrated
facial rendering. The pinned Edit revision, BF16, seed 777, 40 steps, CFG 4 and
0.70 allocator fraction were retained.

| Measurement | Result |
| --- | ---: |
| Model load | 302.681 s |
| Sampling | 479.029 s |
| Total supervisor time | 790.748 s (13 minutes 11 seconds) |
| Host-memory samples / read failures | 160 / 0 |
| Available host memory before / minimum / after | 112.225 / 50.395 / 112.262 GiB |

The RGB intermediate is **1024 × 1024**, **596,736 bytes**. The selected private
file is `candidate-05-threshold-225.png`: **640 × 640 RGBA**, **307,486 bytes**,
**62.0098%** exactly transparent pixels, no EXIF, no visible outer-border pixels
and file permissions 0600. It passes the application's transparent-PNG validator.
No additional Layered generation was run for candidate 05.

Lowering the border-connected white-extraction threshold from 240 to **225**
removes **1,028 additional near-white source pixels** while keeping the original
candidate 05 framing. The central face region and body interior at least three
pixels from the silhouette remain unchanged, and no remaining foreground RGB
is retouched. White collar/ball details and skin highlights remain intact in
visual review. Threshold 220 was rejected: it removed another 214 edge pixels
with little visible benefit. A thin pale hair rim is reduced, not eliminated;
some hair pixels were already blended with white in the generated RGB image.

In `realism-comparison.png`, candidate 05 has a photographic face, a closed
mouth and detailed natural hair/skin. We prefer it as the **generated variant**:
it is substantially easier to recognize than candidate 01. The actual-photo
composition remains the comparison that does not redraw the face. Qwen still
redraws the body and can subtly change facial proportions; its output does not
preserve pixel identity. One portrait and several changed input/prompt choices
do not establish general success or isolate the cause of the improvement.

After completion, the GPU slot was reusable and **112.237 GiB** of host memory
was available, with zero cgroup OOM events or kills. Both acceptance and preview
workers reached the idle service with HTTP 200 and `processing: false`; their
queues had zero active jobs. Empty authenticated requests returned 422 without
a busy header. The acceptance profile PNG still matched its baseline hash.

All **seven** temporary Spark files for this follow-up were archived privately
on the Mac with matching SHA-256 hashes. Only the exact temporary experiment
directory was removed from Spark; runtime code and model cache remain unchanged.
The private `archive-evidence.json` and `final-live-evidence.json` record the
checks. Default prompts, app image pins and stored profiles have not changed;
this follow-up adds experimental evidence rather than permanent code changes.

## Initial cartoon comparison

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

| Candidate | Visual assessment | Initial selection |
| --- | --- | --- |
| 01 — headless body | More facial detail, a closed mouth and a closer expression; the face is too long/narrow and the curls exaggerated. | Initially selected for likeness; later feedback asks for more realism. |
| 02 — complete reference | Polished, compact cartoon, but retains the reference's toothy grin rather than the portrait's expression. | Less faithful expression despite a cleaner overall illustration. |
| 03 — head only | Simplified, more generic eyes, hair and beard; a slight neck-shading seam remains after composition. | Body consistency is strongest, but the face is less detailed than 01. |

This is an assessment of **one portrait**, not a general accuracy benchmark.
The prompt, crop/preprocessing and reference composition changed together;
the comparison does not establish which individual change caused an improvement.
Candidate 01 was our initial selection. The user subsequently found these
outputs too illustrated, motivating the photographic follow-up above. No stored
profile or default application prompt changed, and no new OpenAI request was made.

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

## Initial transparency comparison and selection

All three CPU candidates pass the application's transparent-PNG validator as
**640 × 640 RGBA**. They have no visible pixels touching the outer image border
and no retained image metadata. `comparison-all.png` presents the previous
profile result and the three new candidates on light and dark backgrounds.

| Private result | Exact transparent pixels | Bytes |
| --- | ---: | ---: |
| `candidate-01.png` — initial selection | 60.522949% | 336,838 |
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
The initially selected candidate uses the **777.860 s** Edit stage followed by CPU extraction
and manual framing, avoiding another 711.742 seconds of model work. This was an
operator-run comparison, not a benchmark of a fully automatic replacement
pipeline. Border-connected white extraction can leave enclosed background holes
or halos and can remove pale foreground connected to the background; the initial
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
