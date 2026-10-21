"""Local audio service for the fleet - Stable Audio 3 small models (TFLite CPU).

Endpoints
    GET  /api/health            readiness, cache size, engine facts
    POST /api/music             {"prompt": str, "seconds": 60, "seed": 0}
    POST /api/sfx               {"prompt": str, "seconds": 2, "seed": 0}

Why this exists: demo-vid-mcp needs music beds and one-shot effects. Today that is a
network music service plus FreeSound (which needs an API key and has commercial-use
terms). This runs both locally, offline, with no key.

Honest limitation - the upstream runtime is a one-shot CLI and everything lives inside
``main()``, so it cannot keep the model resident in-process. An uncached request pays
about 4-5 s of model load before any audio is made. What this service adds on top of the
CLI:

* cache by (model, prompt, seconds, seed) - a repeated build is instant, no GPU/CPU work;
* peak normalisation to -3 dB (short effects otherwise arrive at -13 dB and vanish under
  narration);
* one endpoint per role, with the response shape demo-vid already expects.

Not an MCP server. It is a sidecar service on a claimed port (11250).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastmcp import FastMCP
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
TFLITE = ROOT / "upstream" / "optimized" / "tflite"
PY = TFLITE / ".venv" / "Scripts" / "python.exe"
SA3 = TFLITE / "scripts" / "sa3_tflite.py"
CACHE = ROOT / "out" / "cache"
TARGET_PEAK_DB = -3.0
MODEL_FOR = {"music": "sm-music", "sfx": "sm-sfx"}
MAX_SECONDS = {"music": 120, "sfx": 30}
PORT = int(os.getenv("SA3_SERVICE_PORT", "11250"))

# The MCP app must exist before FastAPI so its lifespan can be passed in at
# construction (see mcd BUG-083): without it every HTTP MCP call fails with 500.
mcp = FastMCP(
    "stable-audio",
    instructions="Local music and sound-effect generation (Stable Audio 3, CPU). "
    "No API key, no network. Results are cached and peak-normalised to -3 dB.",
)
mcp_app = mcp.http_app(path="/")

app = FastAPI(title="stable-audio-spike", version="0.2.0", lifespan=mcp_app.lifespan)


def _ffmpeg() -> str | None:
    for candidate in (
        shutil.which("ffmpeg"),
        str(Path.home() / "scoop" / "shims" / "ffmpeg.exe"),
        "C:\\Program Files\\FFmpeg\\bin\\ffmpeg.exe",
    ):
        if candidate and Path(candidate).exists():
            return candidate
    return None


class Request(BaseModel):
    prompt: str = Field(min_length=3, max_length=1200)
    seconds: int = Field(default=60, ge=1)
    seed: int = Field(default=0, ge=0)


class GenerateBody(BaseModel):
    """songgeneration-mcp's request shape: {prompt, duration}."""

    prompt: str = Field(min_length=3, max_length=1200)
    duration: float = Field(default=30, ge=1)


_SFX_INDEX = CACHE / "sfx-index.json"


def _load_index() -> dict:
    try:
        return json.loads(_SFX_INDEX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_index(index: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    _SFX_INDEX.write_text(json.dumps(index, indent=1), encoding="utf-8")


@mcp.tool
def sfx_search(
    operation: str = "search",
    query: str = "",
    sound_id: str = "",
    destination: str = "",
    duration_max: int = 5,
) -> dict:
    """Search or download a sound effect, mirroring sfx-mcp's contract.

    demo-vid-mcp calls sfx_search in two steps: operation="search" returns
    data.sounds[] with an id, then operation="download" writes a file into
    `destination` and returns data.file_path. The sounds are generated locally
    by Stable Audio 3, not recordings from FreeSound, so there is no API key and
    no per-sound licence to attribute.

    Args:
        operation: "search" or "download".
        query: Sound description, e.g. "camera shutter click, close, dry".
        sound_id: Id returned by search, required for download.
        destination: Directory to write the WAV into (download).
        duration_max: Upper bound in seconds for the generated effect.

    Returns:
        {"success": bool, "data": {...}} or {"success": False, "error": str}.
    """
    if operation == "search":
        text = (query or "").strip()
        if not text:
            return {"success": False, "error": "query is required"}
        seconds = min(max(1, int(duration_max)), MAX_SECONDS["sfx"])
        key = hashlib.sha256(f"{text}|{seconds}".encode()).hexdigest()[:10]
        index = _load_index()
        index[key] = {"prompt": text, "seconds": seconds}
        _save_index(index)
        return {
            "success": True,
            "data": {
                "query": text,
                "count": 1,
                "sounds": [
                    {
                        "id": key,
                        "name": text,
                        "duration": seconds,
                        "license": "generated locally (Stable Audio 3 Community License)",
                        "source": "stable-audio-3 sm-sfx",
                    }
                ],
            },
        }

    if operation != "download":
        return {"success": False, "error": f"unknown operation '{operation}'"}

    entry = _load_index().get(sound_id)
    if not entry:
        return {"success": False, "error": f"unknown sound_id '{sound_id}'"}
    if not destination:
        return {"success": False, "error": "destination is required"}
    try:
        result = generate("sfx", entry["prompt"], int(entry["seconds"]), 0)
    except HTTPException as exc:
        return {"success": False, "error": str(exc.detail)}
    dest_dir = Path(destination)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"sfx-{sound_id}.wav"
    shutil.copy2(result["audio_path"], dest)
    return {
        "success": True,
        "data": {
            "file_path": str(dest),
            "bytes": dest.stat().st_size,
            "cached": result.get("cached", False),
        },
    }


@app.post("/api/generate")
def generate_compat(body: GenerateBody) -> dict:
    """songgeneration-mcp's endpoint, served locally.

    demo-vid-mcp POSTs {"prompt", "duration"} and expects {"success", "file"}.
    """
    try:
        result = generate("music", body.prompt, int(round(body.duration)), 0)
    except HTTPException as exc:
        return {"success": False, "error": str(exc.detail)}
    return {
        "success": True,
        "file": result["audio_path"],
        "backend": "stable-audio-3 sm-music (local, CPU)",
        "cached": result.get("cached", False),
        "wall_s": result.get("wall_s"),
    }


def _ready() -> tuple[bool, str]:
    if not PY.is_file():
        return False, f"runtime missing: {PY} (run scripts/bootstrap.ps1)"
    if not SA3.is_file():
        return False, f"upstream script missing: {SA3}"
    if not (TFLITE / "models").is_dir():
        return False, f"models missing: {TFLITE / 'models'}"
    return True, "ok"


def _peak_db(path: Path, ffmpeg: str) -> float | None:
    proc = subprocess.run(  # noqa: S603 - fixed argv, absolute binary, no shell
        [ffmpeg, "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    for line in (proc.stderr or "").splitlines():
        if "max_volume:" in line:
            try:
                return float(line.split("max_volume:")[1].split("dB")[0].strip())
            except ValueError:
                return None
    return None


def _normalise(src: Path, dst: Path, ffmpeg: str) -> float:
    """Peak-normalise to TARGET_PEAK_DB. Returns the applied gain in dB."""
    peak = _peak_db(src, ffmpeg)
    if peak is None:
        shutil.copy2(src, dst)
        return 0.0
    gain = round(TARGET_PEAK_DB - peak, 2)
    proc = subprocess.run(  # noqa: S603 - fixed argv, absolute binary, no shell
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-af", f"volume={gain}dB", str(dst)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        shutil.copy2(src, dst)
        return 0.0
    return gain


def _cache_key(model: str, prompt: str, seconds: int, seed: int) -> str:
    body = json.dumps(
        {"model": model, "prompt": prompt, "seconds": seconds, "seed": seed},
        sort_keys=True,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:20]


def generate(kind: str, prompt: str, seconds: int, seed: int) -> dict:
    ready, reason = _ready()
    if not ready:
        raise HTTPException(status_code=503, detail=reason)
    ffmpeg = _ffmpeg()
    if not ffmpeg:
        raise HTTPException(status_code=503, detail="ffmpeg not found")

    model = MODEL_FOR[kind]
    seconds = min(max(1, seconds), MAX_SECONDS[kind])
    CACHE.mkdir(parents=True, exist_ok=True)
    key = _cache_key(model, prompt, seconds, seed)
    out = CACHE / f"{key}.wav"
    meta = CACHE / f"{key}.json"
    if out.is_file():
        return {
            "success": True,
            "audio_path": str(out),
            "cached": True,
            "model": model,
            "seconds": seconds,
            "engine": "stablediffusion-audio-3-tflite",
        }

    raw = CACHE / f"{key}.raw.wav"
    argv = [
        str(PY),
        str(SA3),
        "--prompt",
        prompt,
        "--dit",
        model,
        "--decoder",
        "same-s",
        "--seconds",
        str(seconds),
        "--out",
        str(raw),
    ]
    if seed:
        argv += ["--seed", str(seed)]

    started = time.perf_counter()
    proc = subprocess.run(  # noqa: S603 - fixed argv, absolute python, no shell
        argv, capture_output=True, text=True, timeout=900, cwd=str(TFLITE)
    )
    wall = round(time.perf_counter() - started, 2)
    if proc.returncode != 0 or not raw.is_file():
        tail = ((proc.stderr or "") + (proc.stdout or ""))[-800:]
        raise HTTPException(status_code=502, detail=f"generation failed: {tail}")

    gain = _normalise(raw, out, ffmpeg)
    raw.unlink(missing_ok=True)
    payload = {
        "prompt": prompt,
        "model": model,
        "seconds": seconds,
        "seed": seed,
        "wall_s": wall,
        "gain_db": gain,
        "target_peak_db": TARGET_PEAK_DB,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    meta.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return {
        "success": True,
        "audio_path": str(out),
        "cached": False,
        "model": model,
        "seconds": seconds,
        "wall_s": wall,
        "gain_db": gain,
        "engine": "stablediffusion-audio-3-tflite",
    }


@app.get("/api/health")
def health() -> dict:
    ready, reason = _ready()
    cached = len(list(CACHE.glob("*.wav"))) if CACHE.is_dir() else 0
    return {
        "status": "ok" if ready else "degraded",
        "reason": reason,
        "engine": "stable-audio-3 sm-music/sm-sfx (TFLite CPU)",
        "models": list(MODEL_FOR.values()),
        "warm": False,
        "note": "uncached requests pay ~4-5 s of model load; results are cached",
        "cache_entries": cached,
        "target_peak_db": TARGET_PEAK_DB,
        "port": PORT,
        "mcp_endpoint": f"http://127.0.0.1:{PORT}/mcp",
    }


@app.post("/api/music")
def music(body: Request) -> dict:
    return generate("music", body.prompt, body.seconds, body.seed)


@app.post("/api/sfx")
def sfx(body: Request) -> dict:
    return generate("sfx", body.prompt, body.seconds, body.seed)


@app.get("/api/cache")
def cache() -> dict:
    if not CACHE.is_dir():
        return {"entries": 0, "items": []}
    items = []
    for meta in sorted(CACHE.glob("*.json")):
        if meta.name == _SFX_INDEX.name:
            continue
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data["audio"] = str(meta.with_suffix(".wav"))
        items.append(data)
    return {"entries": len(items), "items": items[-50:]}


class _McpPathAlias:
    """Route /mcp to the mounted MCP app (Starlette needs the trailing slash).

    Without this, POST /mcp hits the mount with an empty child path and returns
    405, while /mcp/ works - the exact failure in mcd BUG-083.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path") == "/mcp":
            scope = dict(scope)
            scope["path"] = "/mcp/"
            scope["raw_path"] = b"/mcp/"
        await self.app(scope, receive, send)


app.add_middleware(_McpPathAlias)
app.mount("/mcp", mcp_app)
