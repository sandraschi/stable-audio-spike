# Decision: Stable Audio 3 small models for demo-vid-mcp audio

Status: **scaffolded, not evaluated.** Fill in the measured columns after `scripts\ab.ps1`.

## What is being decided

Replace two network dependencies in `demo-vid-mcp`:

1. `songgeneration-mcp` for the background bed.
2. `sfx-mcp` (FreeSound) for one-shot effects. Today this also needs `FREESOUND_API_KEY`,
   which is unset on this machine, so SFX resolve to nothing.

with one local CPU engine: Stable Audio 3 `sm-music` and `sm-sfx` (433M each, TFLite,
Windows x64).

## Criteria

| Criterion | Target | Measured |
|---|---|---|
| 60 s bed wall time (CPU) | < 30 s | |
| Peak RAM | < 2.5 GB | |
| Bed usable under narration | no warbling, no vocals | |
| 5 effect prompts recognisable | 5/5 | |
| Works with no API key / offline | yes | |
| Licence OK for shipped demos | Community License terms checked | |

## Why not `medium`

1.4B, better music, but needs Flash-Attention 2 in the PyTorch route and the optimized
TensorRT route is Linux-only. A demo bed does not justify that on Windows.

## If it passes

Build a small local service (FastAPI + `/api/music` + `/api/sfx`, fixed port claimed via
`claim_ports.py`) and point demo-vid's `MUSIC_MCP_URL` / `SFX_MCP_URL` at it. Keep
`songgeneration-mcp` as the high-quality fallback.

## If it fails

Stay on `songgeneration-mcp` for music, and fix `sfx-mcp` (dual transport is now done;
still needs `FREESOUND_API_KEY`). Record why here so this is not re-litigated.

## Known context (2026-10-21)

- `sfx-mcp` HTTP transport was broken until today (mount without lifespan, and a trailing
  slash requirement). Fixed in `sfx-mcp` commits `ccb1fba` / `ae47e28`; endpoint is
  `http://127.0.0.1:11120/mcp/`.
- `demo-vid-mcp` voice/picture sync was fixed separately (`8816fcd`, `ee61173`) and now
  passes its own gate at +0.121 s worst drift.
