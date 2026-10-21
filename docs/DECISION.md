# Decision: Stable Audio 3 small models for demo-vid-mcp audio

Status: **evaluated 2026-10-21** on Goliath (Windows 11, Ryzen 9 5900X, CPU
inference, no GPU used). Verdict: technically viable; quality is the only open
question and it needs ears, not benchmarks.

## What is being decided

Replace two network dependencies in `demo-vid-mcp`:

1. `songgeneration-mcp` for the background bed.
2. `sfx-mcp` (FreeSound) for one-shot effects. Today this also needs `FREESOUND_API_KEY`,
   which is unset on this machine, so SFX resolve to nothing.

with one local CPU engine: Stable Audio 3 `sm-music` and `sm-sfx` (433M each, TFLite,
Windows x64).

## Measured (2026-10-21, `scripts\ab.ps1` + a 30 s RAM probe)

| Criterion | Target | Measured | Verdict |
|---|---|---|---|
| 60 s bed wall time (CPU) | < 30 s | **19.3 s** (0.32x realtime) | pass |
| Effect wall time | - | 5.2-5.9 s each for 1-3 s clips | pass, but 4-5 s of that is model load |
| Peak working set | < 2.5 GB | **2.0 GB** (30 s music run) | pass |
| Sample rate / format | 44.1 kHz stereo | 44.1 kHz stereo WAV, 6/6 files | pass |
| Files distinct | yes | 6 distinct MD5s | pass |
| Bed level | usable under narration | mean -26.7 dB, peak -4.4 dB | plausible bed |
| Boom effect | audible | mean -18.1 dB, peak -0.2 dB | pass |
| 1 s UI click | audible | mean -44.9 dB, peak -13.5 dB | **quiet** - needs gain |
| Works with no API key / offline | yes | yes, weights cached locally | pass |
| 5 effect prompts recognisable | 5/5 | not machine-checkable | **open** |
| Licence OK for shipped demos | terms checked | Community License, threshold not reviewed | **open** |

## Findings that change the design

1. **Per-call model load dominates short effects.** Every `sa3` invocation reloads
   the DiT, so a 1 s click costs 5.5 s wall. A service that keeps the model resident
   makes a batch of effects roughly free after the first one. This is the single most
   important reason to build a service rather than shell out per effect.
2. **Short effects come out quiet.** The 1 s click peaked at -13.5 dB while the boom
   hit -0.2 dB. Any integration must normalise (`loudnorm` or a fixed gain target)
   or effects will be inaudible under narration.
3. **`--decoder` is required non-interactively.** Without it the CLI opens an arrow
   picker and dies with `EOFError` inside a script. `scripts\gen.ps1` passes
   `--decoder same-s` for that reason.

## Why not `medium`

1.4B, better music, but needs Flash-Attention 2 in the PyTorch route and the optimized
TensorRT route is Linux-only. A demo bed does not justify that on Windows.

## Recommendation

Build a small local service (FastAPI on a claimed port) that:

- loads `sm-music` and `sm-sfx` once at startup and keeps them warm;
- exposes `/api/music` and `/api/sfx` with the same response shape demo-vid already
  expects from `songgeneration-mcp` and `sfx-mcp`;
- normalises effects to a target peak (about -3 dB) so short clicks are audible;
- caches by (prompt, seconds, seed) so repeated demos do not regenerate.

Then A/B the bed by ear against `songgeneration-mcp` before switching the default.
Keep the network engine as the high-quality fallback.

## Known context (2026-10-21)

- `sfx-mcp` HTTP transport was broken until today (mount without lifespan, and a trailing
  slash requirement). Fixed in `sfx-mcp` commits `ccb1fba` / `ae47e28` / `f474058`; the
  endpoint now accepts both `http://127.0.0.1:11120/mcp` and `/mcp/`.
- `demo-vid-mcp` voice/picture sync was fixed separately (`8816fcd`, `ee61173`) and now
  passes its own gate at +0.121 s worst drift.
- Raw artifacts: `out/ab.csv`, `out/ab-*.wav` (gitignored).

