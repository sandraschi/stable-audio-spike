# stable-audio-spike

A **spike, not a fleet MCP server**. It answers one question: can Stable Audio 3's
CPU models replace the two network audio dependencies in `demo-vid-mcp`?

| Today | Dependency |
|---|---|
| background music beds | `songgeneration-mcp` (network, model downloads) |
| sound effects | `sfx-mcp` -> FreeSound API (network, **needs `FREESOUND_API_KEY`**, currently unset) |

If the spike passes, this becomes a small local service exposing the same two URLs, and
`demo-vid-mcp` points at it instead of at the network. It is not an MCP server yet, has no
port, and is not in `WEBAPP_PORTS.md`. Promote it only after the A/B in `docs/DECISION.md`.

## Route: TFLite CPU, small models

`upstream/optimized/tflite` is Stability's portable runtime: no PyTorch, no transformers,
just LiteRT + XNNPACK. Windows x64 is supported.

| Model | Params | RAM (int8) | Max length | Use |
|---|---|---|---|---|
| `sm-music` | 433M | ~0.8 GB | 120 s | beds |
| `sm-sfx` | 433M | ~0.8 GB | 120 s | one-shot effects |
| `medium` | 1.4B | 2-4 GB | 380 s | skipped: needs Flash-Attention 2 / TensorRT, and the optimized TensorRT path is Linux-only |

Licence is the [Stability AI Community License](https://stability.ai/license); check the
revenue threshold before shipping generated audio inside a product.

## Install

```powershell
git clone --depth 1 https://github.com/Stability-AI/stable-audio-3.git upstream   # already done
scripts\bootstrap.ps1
```

`bootstrap.ps1` runs the upstream `install.bat` in `upstream/optimized/tflite`. First run
downloads model weights from HuggingFace (hundreds of MB, then cached).

## Generate

```powershell
scripts\gen.ps1 -Mode music -Prompt "calm ambient instrumental bed, no vocals" -Seconds 60
scripts\gen.ps1 -Mode sfx   -Prompt "single camera shutter click, close, dry" -Seconds 2
```

Output lands in `out/`, with the wall time and file size printed.

## A/B

```powershell
scripts\ab.ps1
```

Generates one 60 s bed and five effects, writes `out/ab.csv` (prompt, seconds, wall time,
size). Compare against a bed from `songgeneration-mcp` and against real recorded effects.

## Definition of done

- 60 s bed on CPU in under 30 s wall, under 2.5 GB peak RAM.
- The bed is usable under narration without ducking artefacts.
- 5 of 5 effect prompts produce something recognisable (not noise).
- No API key, no network at generation time.

## Files

| Path | What |
|---|---|
| `scripts/bootstrap.ps1` | one-time install of the TFLite runtime |
| `scripts/gen.ps1` | thin wrapper over `upstream/optimized/tflite/sa3.ps1` |
| `scripts/ab.ps1` | the benchmark run |
| `docs/DECISION.md` | go/no-go criteria and the result |
| `upstream/` | read-only clone, gitignored |
