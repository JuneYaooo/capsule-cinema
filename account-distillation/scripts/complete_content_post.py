#!/usr/bin/env python3
"""Complete selected winner posts to content_complete evidence depth.

This is intentionally a selected-winner runner, not a bulk crawler. It uses
TikHub only to fetch a transient media URL, stores local evidence, and never
writes signed playback URLs or API keys.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import requests
except ImportError as exc:  # pragma: no cover - local runtime guard
    raise SystemExit("Missing dependency: requests") from exc

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - local runtime guard
    Image = None
    ImageDraw = None
    ImageFont = None


DEFAULT_ENV_FILE = Path("/Users/june2/code/github/video_workflow/.env")
DEFAULT_TIKHUB = Path(
    "/Users/june2/code/github/video_workflow/.claude/skills/account-diagnostic/tikhub/bin/tikhub"
)
RANGE_CHUNK_SIZE = 2 * 1024 * 1024
RANGE_CHUNK_RE = re.compile(r"^chunk_(\d{4})\.part$")


@dataclass
class QueueRow:
    priority: str
    account: str
    rank: str
    post_id: str
    caption: str
    interaction_score: str


def log(message: str) -> None:
    print(message, flush=True)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def rel(run_dir: Path, path: Path) -> str:
    return path.relative_to(run_dir).as_posix()


def run_checked(cmd: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"Command failed ({cmd[0]}): {detail[:1200]}")
    return proc


def ffprobe_duration(video: Path) -> float:
    proc = run_checked(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ],
        timeout=60,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"Could not read duration for {video}") from exc


def find_queue_row(run_dir: Path, post_id: str) -> QueueRow:
    queue = run_dir / "03_scoring" / "content_completion_queue.csv"
    with queue.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("post_id") == post_id:
                return QueueRow(
                    priority=row.get("priority", ""),
                    account=row.get("account", ""),
                    rank=row.get("account_winner_rank_fresh", ""),
                    post_id=post_id,
                    caption=row.get("caption_clean", ""),
                    interaction_score=row.get("interaction_score", ""),
                )
    raise RuntimeError(f"Post {post_id} not found in content_completion_queue.csv")


def extract_url(value: Any) -> str | None:
    if isinstance(value, str):
        if value.startswith("http://") or value.startswith("https://"):
            parsed = urlparse(value)
            path = parsed.path.lower()
            if ".mp4" in path or "video" in path or parsed.netloc:
                return value
        return None
    if isinstance(value, dict):
        preferred = [
            "original_video_url",
            "play_url",
            "download_url",
            "url",
            "video_url",
        ]
        for key in preferred:
            if key in value:
                found = extract_url(value[key])
                if found:
                    return found
        for item in value.values():
            found = extract_url(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = extract_url(item)
            if found:
                return found
    return None


def fetch_tikhub_media_url(post_id: str, tikhub: Path) -> tuple[str, dict[str, Any]]:
    log(f"[{post_id}] Fetching transient TikHub media URL")
    last_error = ""
    data: dict[str, Any] | None = None
    for attempt in range(1, 6):
        proc = subprocess.run(
            [
                str(tikhub),
                "douyin",
                "douyin_web_fetch_video_high_quality_play_url",
                "--aweme_id",
                post_id,
            ],
            text=True,
            capture_output=True,
            timeout=120,
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            break
        last_error = (proc.stderr or proc.stdout).strip()
        log(f"[{post_id}] TikHub lookup attempt {attempt} failed")
        if attempt < 5:
            time.sleep(5 * attempt)
    if data is None:
        raise RuntimeError(f"TikHub media lookup failed: {last_error[:1200]}")
    if data.get("code") not in (0, 200, "0", "200", None):
        raise RuntimeError(f"TikHub returned non-success code: {data.get('code')}")
    url = extract_url(data.get("data", data))
    if not url:
        raise RuntimeError("TikHub response did not contain a media URL")
    media_data = data.get("data") if isinstance(data.get("data"), dict) else {}
    return url, media_data


def download_media(url: str, target: Path, reported_size: int | None = None) -> None:
    if target.exists() and target.stat().st_size > 1024:
        log(f"[{target.stem}] Local video exists: {target}")
        return

    if assemble_local_ranged_parts(target, reported_size):
        return

    headers_base = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
        )
    }
    if not reported_size:
        reported_size = probe_remote_size(url, headers_base)
        if reported_size:
            log(f"[{target.stem}] Probed remote media size: {reported_size} bytes")

    if reported_size and reported_size >= 32 * 1024 * 1024:
        try:
            download_media_ranged(url, target, reported_size)
            return
        except Exception as exc:
            detail = str(exc).replace("\n", " ")[:180]
            saved_chunks = local_ranged_part_count(target)
            if saved_chunks:
                log(
                    f"[{target.stem}] Ranged download stopped with {saved_chunks} local chunks saved: "
                    f"{type(exc).__name__}: {detail}"
                )
                raise
            log(f"[{target.stem}] Ranged download unavailable: {type(exc).__name__}: {detail}; falling back to stream")

    part = target.with_suffix(target.suffix + ".part")
    if part.exists() and part.stat().st_size == 0:
        part.unlink()

    for attempt in range(1, 5):
        resume_at = part.stat().st_size if part.exists() else 0
        headers = dict(headers_base)
        if resume_at:
            headers["Range"] = f"bytes={resume_at}-"
        log(f"[{target.stem}] Download attempt {attempt}, resume_bytes={resume_at}")
        try:
            with requests.get(url, headers=headers, stream=True, timeout=(10, 25)) as response:
                if resume_at and response.status_code == 200:
                    part.unlink(missing_ok=True)
                    resume_at = 0
                response.raise_for_status()
                mode = "ab" if resume_at and response.status_code == 206 else "wb"
                with part.open(mode) as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            size = part.stat().st_size
            if reported_size and size < int(reported_size) * 0.98:
                raise RuntimeError(f"incomplete download: {size}/{reported_size} bytes")
            part.replace(target)
            log(f"[{target.stem}] Downloaded local MP4, bytes={target.stat().st_size}")
            return
        except Exception as exc:
            log(f"[{target.stem}] Download attempt {attempt} failed: {type(exc).__name__}")
            if attempt == 4:
                raise
            time.sleep(3 * attempt)


def expected_ranges(target: Path, reported_size: int) -> list[tuple[int, int, Path]]:
    parts_dir = target.parent / f"{target.name}.parts"
    ranges: list[tuple[int, int, Path]] = []
    for idx, start in enumerate(range(0, reported_size, RANGE_CHUNK_SIZE)):
        end = min(start + RANGE_CHUNK_SIZE - 1, reported_size - 1)
        ranges.append((start, end, parts_dir / f"chunk_{idx:04d}.part"))
    return ranges


def local_ranged_part_count(target: Path) -> int:
    parts_dir = target.parent / f"{target.name}.parts"
    if not parts_dir.exists():
        return 0
    return sum(1 for path in parts_dir.glob("chunk_*.part") if RANGE_CHUNK_RE.match(path.name))


def complete_local_ranges(
    parts_dir: Path,
    reported_size: int | None = None,
) -> tuple[int, list[Path]] | None:
    if reported_size:
        ranges = expected_ranges(parts_dir.parent / parts_dir.name.removesuffix(".parts"), reported_size)
        paths = [out for start, end, out in ranges if out.parent == parts_dir]
        if paths and all(out.exists() and out.stat().st_size == end - start + 1 for start, end, out in ranges):
            return reported_size, paths

    indexed: list[tuple[int, Path]] = []
    for path in parts_dir.glob("chunk_*.part"):
        match = RANGE_CHUNK_RE.match(path.name)
        if match:
            indexed.append((int(match.group(1)), path))
    indexed.sort()
    if not indexed:
        return None
    if [idx for idx, _ in indexed] != list(range(len(indexed))):
        return None

    paths = [path for _, path in indexed]
    sizes = [path.stat().st_size for path in paths]
    if any(size != RANGE_CHUNK_SIZE for size in sizes[:-1]):
        return None
    if not (0 < sizes[-1] <= RANGE_CHUNK_SIZE):
        return None
    if not reported_size and sizes[-1] == RANGE_CHUNK_SIZE:
        return None

    inferred_size = sum(sizes)
    if reported_size and inferred_size != reported_size:
        log(f"[{parts_dir.name.removesuffix('.mp4.parts')}] Local ranged chunks infer {inferred_size} bytes; reported_size={reported_size}")
        return None
    return inferred_size, paths


def assemble_local_ranged_parts(target: Path, reported_size: int | None = None) -> bool:
    parts_dir = target.parent / f"{target.name}.parts"
    if not parts_dir.exists():
        return False

    complete = complete_local_ranges(parts_dir, reported_size)
    if not complete:
        return False

    expected_size, paths = complete
    part = target.with_suffix(target.suffix + ".part")
    part.unlink(missing_ok=True)
    log(f"[{target.stem}] All ranged chunks present locally; assembling {len(paths)} chunks")
    with part.open("wb") as final:
        for chunk_path in paths:
            with chunk_path.open("rb") as handle:
                shutil.copyfileobj(handle, final, length=1024 * 1024)
    if part.stat().st_size != expected_size:
        raise RuntimeError(f"assembled size mismatch: {part.stat().st_size}/{expected_size}")
    part.replace(target)
    shutil.rmtree(parts_dir, ignore_errors=True)
    log(f"[{target.stem}] Downloaded local MP4, bytes={target.stat().st_size}")
    return True


def range_supported(url: str, headers_base: dict[str, str]) -> bool:
    headers = dict(headers_base)
    headers["Range"] = "bytes=0-0"
    with requests.get(url, headers=headers, stream=True, timeout=(20, 60)) as response:
        return response.status_code == 206


def probe_remote_size(url: str, headers_base: dict[str, str]) -> int | None:
    headers = dict(headers_base)
    headers["Range"] = "bytes=0-0"
    try:
        with requests.get(url, headers=headers, stream=True, timeout=(10, 40)) as response:
            content_range = response.headers.get("Content-Range", "")
            match = re.search(r"/(\d+)\s*$", content_range)
            if response.status_code == 206 and match:
                return int(match.group(1))
            content_length = response.headers.get("Content-Length")
            if response.status_code == 200 and content_length and content_length.isdigit():
                return int(content_length)
    except requests.RequestException as exc:
        log(f"Remote size probe failed: {type(exc).__name__}")
    return None


def download_range_part(
    url: str,
    headers_base: dict[str, str],
    start: int,
    end: int,
    out: Path,
) -> None:
    expected = end - start + 1
    if out.exists() and out.stat().st_size == expected:
        return
    for attempt in range(1, 4):
        try:
            tmp = out.with_suffix(out.suffix + ".tmp")
            if shutil.which("curl"):
                proc = subprocess.run(
                    [
                        "curl",
                        "--location",
                        "--fail",
                        "--silent",
                        "--show-error",
                        "--connect-timeout",
                        "10",
                        "--max-time",
                        "150",
                        "--range",
                        f"{start}-{end}",
                        "--output",
                        str(tmp),
                        "--config",
                        "-",
                    ],
                    input=f'url = "{url}"\n',
                    text=True,
                    capture_output=True,
                    timeout=170,
                )
                if proc.returncode != 0:
                    raise RuntimeError(f"curl range failed: {(proc.stderr or proc.stdout)[:300]}")
                if tmp.stat().st_size != expected:
                    raise RuntimeError(f"range incomplete {tmp.stat().st_size}/{expected}")
                tmp.replace(out)
                return

            headers = dict(headers_base)
            headers["Range"] = f"bytes={start}-{end}"
            with requests.get(url, headers=headers, stream=True, timeout=(10, 25)) as response:
                if response.status_code != 206:
                    raise RuntimeError(f"range status {response.status_code}")
                with tmp.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
                if tmp.stat().st_size != expected:
                    raise RuntimeError(f"range incomplete {tmp.stat().st_size}/{expected}")
                tmp.replace(out)
                return
        except Exception:
            out.with_suffix(out.suffix + ".tmp").unlink(missing_ok=True)
            if attempt == 3:
                raise
            time.sleep(2 * attempt)


def download_media_ranged(url: str, target: Path, reported_size: int) -> None:
    headers_base = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
        )
    }
    part = target.with_suffix(target.suffix + ".part")
    parts_dir = target.parent / f"{target.name}.parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    part.unlink(missing_ok=True)

    if assemble_local_ranged_parts(target, reported_size):
        return

    if not range_supported(url, headers_base):
        raise RuntimeError("server did not return 206 for range probe")

    ranges = expected_ranges(target, reported_size)
    log(f"[{target.stem}] Ranged download: {reported_size} bytes across {len(ranges)} chunks")
    with ThreadPoolExecutor(max_workers=min(4, len(ranges))) as pool:
        futures = [
            pool.submit(download_range_part, url, headers_base, start, end, out)
            for start, end, out in ranges
        ]
        done = 0
        for future in as_completed(futures):
            future.result()
            done += 1
            if done == len(ranges) or done % 4 == 0:
                log(f"[{target.stem}] Ranged chunks complete: {done}/{len(ranges)}")

    if not assemble_local_ranged_parts(target, reported_size):
        raise RuntimeError("ranged chunks incomplete after download")


def write_media_meta(run_dir: Path, post_id: str, media_data: dict[str, Any], video: Path) -> None:
    meta = {
        "post_id": post_id,
        "source": "tikhub_app_v3_high_quality_play_url",
        "content_type": media_data.get("content_type", "video/mp4"),
        "file_size_in_mb_reported": media_data.get("file_size_in_mb"),
        "local_video": rel(run_dir, video),
        "signed_url_stored": False,
    }
    (video.parent / f"{post_id}_media_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def extract_audio(video: Path, audio: Path) -> None:
    if audio.exists() and audio.stat().st_size > 1024:
        log(f"[{video.stem}] Audio exists: {audio}")
        return
    audio.parent.mkdir(parents=True, exist_ok=True)
    log(f"[{video.stem}] Extracting MP3 audio")
    run_checked(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vn",
            "-acodec",
            "libmp3lame",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-b:a",
            "64k",
            str(audio),
        ],
        timeout=600,
    )


def transcribe_siliconflow(audio: Path, txt: Path, js: Path) -> str:
    if txt.exists() and txt.read_text(encoding="utf-8").strip():
        log(f"[{audio.stem}] Transcript exists: {txt}")
        return txt.read_text(encoding="utf-8").strip()
    api_key = os.getenv("SILICONFLOW_API_KEY")
    api_base = os.getenv("SILICONFLOW_BASE_URL") or os.getenv("SILICONFLOW_API_BASE") or "https://api.siliconflow.cn/v1"
    if not api_key:
        raise RuntimeError("SILICONFLOW_API_KEY is not configured")
    log(f"[{audio.stem}] Transcribing with SiliconFlow")
    with audio.open("rb") as handle:
        response = requests.post(
            f"{api_base.rstrip('/')}/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (audio.name, handle, "audio/mpeg")},
            data={"model": "FunAudioLLM/SenseVoiceSmall"},
            timeout=240,
        )
    if response.status_code != 200:
        raise RuntimeError(f"SiliconFlow transcription failed: {response.status_code} {response.text[:500]}")
    result = response.json()
    text = (result.get("text") or "").strip()
    if not text:
        raise RuntimeError("SiliconFlow returned an empty transcript")
    js.write_text(json.dumps({"text": text}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    txt.write_text(text + "\n", encoding="utf-8")
    return text


def make_proxy(video: Path, proxy: Path) -> None:
    if proxy.exists() and proxy.stat().st_size > 1024:
        log(f"[{video.stem}] Proxy exists: {proxy}")
        return
    log(f"[{video.stem}] Creating 480p proxy with audio")
    vf = "scale='if(gt(iw,ih),-2,480)':'if(gt(iw,ih),480,-2)',fps=12"
    run_checked(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "48k",
            "-movflags",
            "+faststart",
            str(proxy),
        ],
        timeout=1200,
    )


def split_proxy(proxy: Path, segments_dir: Path, segment_seconds: int = 35) -> list[Path]:
    segments_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(segments_dir.glob("part_*.mp4"))
    if existing and all(path.stat().st_size > 1024 for path in existing):
        log(f"[{proxy.stem}] Segments exist: {len(existing)}")
        return existing
    for path in existing:
        path.unlink()
    log(f"[{proxy.stem}] Splitting proxy into {segment_seconds}s segments")
    run_checked(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(proxy),
            "-c",
            "copy",
            "-f",
            "segment",
            "-segment_time",
            str(segment_seconds),
            "-reset_timestamps",
            "1",
            str(segments_dir / "part_%02d.mp4"),
        ],
        timeout=600,
    )
    segments = sorted(segments_dir.glob("part_*.mp4"))
    if not segments:
        raise RuntimeError("No proxy segments were created")
    return segments


def keyframe_times(duration: float) -> list[int]:
    base = [0, 1, 3, 5, 8]
    cursor = 16
    while cursor < duration:
        base.append(cursor)
        cursor += 16
    if duration > 12:
        base.append(max(0, int(duration) - 2))
    return sorted({t for t in base if t <= max(0, int(duration))})


def extract_keyframes(video: Path, key_dir: Path) -> Path:
    key_dir.mkdir(parents=True, exist_ok=True)
    contact = key_dir / f"{video.stem}_contact_sheet.jpg"
    if contact.exists() and contact.stat().st_size > 1024:
        log(f"[{video.stem}] Keyframes exist: {key_dir}")
        return contact
    duration = ffprobe_duration(video)
    for t in keyframe_times(duration):
        out = key_dir / f"t{t:03d}.jpg"
        run_checked(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(t),
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(out),
            ],
            timeout=90,
        )
    frames = sorted(key_dir.glob("t*.jpg"))
    if not frames:
        raise RuntimeError("No keyframes were created")
    columns = 4
    rows = max(1, math.ceil(len(frames) / columns))
    run_checked(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            "1",
            "-pattern_type",
            "glob",
            "-i",
            str(key_dir / "t*.jpg"),
            "-vf",
            f"scale=320:-1,tile={columns}x{rows}",
            "-frames:v",
            "1",
            str(contact),
        ],
        timeout=120,
    )
    return contact


def gemini_config() -> tuple[str, str, str]:
    api_key = os.getenv("GEMINI3_API_KEY") or os.getenv("VIDEO_ANALYSIS_API_KEY")
    base_url = os.getenv("GEMINI3_BASE_URL") or os.getenv("VIDEO_ANALYSIS_BASE_URL") or "https://daydream88.fun/v1"
    model = (
        os.getenv("GEMINI3_MODEL_NAME")
        or os.getenv("VIDEO_ANALYSIS_MODEL_NAME")
        or "gemini-3.1-pro-preview"
    ).split(",")[0].strip()
    if not api_key:
        raise RuntimeError("GEMINI3_API_KEY or VIDEO_ANALYSIS_API_KEY is not configured")
    return api_key, base_url, model


def chat_completion(
    *,
    prompt: str,
    video_path: Path | None = None,
    max_tokens: int = 3500,
    timeout: int = 420,
) -> str:
    api_key, base_url, model = gemini_config()
    content: list[dict[str, Any]] | str
    if video_path:
        mime = mimetypes.guess_type(video_path.name)[0] or "video/mp4"
        b64 = base64.b64encode(video_path.read_bytes()).decode("utf-8")
        content = [
            {"type": "text", "text": prompt},
            {"type": "video_url", "video_url": {"url": f"data:{mime};base64,{b64}"}},
        ]
    else:
        content = prompt
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    url = url.replace("/v1/v1/", "/v1/")
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.25,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Gemini request failed: {response.status_code} {response.text[:800]}")
    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Gemini response had no choices")
    result = choices[0].get("message", {}).get("content", "")
    if not result.strip():
        raise RuntimeError("Gemini returned empty content")
    return result.strip()


def chat_completion_images(
    *,
    prompt: str,
    image_paths: list[Path],
    max_tokens: int = 3000,
    timeout: int = 240,
) -> str:
    api_key, base_url, model = gemini_config()
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image_path in image_paths:
        mime = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    url = url.replace("/v1/v1/", "/v1/")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    last_error = ""
    for attempt in range(1, 4):
        try:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
            if response.status_code != 200:
                raise RuntimeError(f"status {response.status_code}: {response.text[:500]}")
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError("no choices")
            result = choices[0].get("message", {}).get("content", "")
            if not result.strip():
                raise RuntimeError("empty content")
            return result.strip()
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            log(f"Gemini image request attempt {attempt} failed: {type(exc).__name__}")
            if attempt < 3:
                time.sleep(5 * attempt)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            log(f"Gemini image request attempt {attempt} failed: {type(exc).__name__}")
            if attempt < 3:
                time.sleep(5 * attempt)
    raise RuntimeError(f"Gemini image request failed: {last_error[:500]}")


def clean_model_markdown(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```markdown"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
    elif cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = re.sub(r"(?m)^(#{1,6})\s+#{1,6}\s+", r"\1 ", cleaned)
    return cleaned.strip()


def segment_prompt(row: QueueRow, idx: int, count: int, transcript: str) -> str:
    return f"""你在做抖音 AI工具/AI开源栏目号的内容级蒸馏。

账号: {row.account}
Post ID: {row.post_id}
标题/文案: {row.caption}
当前是全片分段 {idx + 1}/{count}。请只基于本段可见画面和可听内容分析，不要虚构未出现画面。

全片 ASR 草稿供对齐参考:
{transcript}

输出中文 Markdown，必须包含:
1. 主要工具/主题
2. 关键画面表：时间戳、画面内容、对应口播/字幕
3. 本段口播卖点校正：纠正 ASR 中明显错词
4. 本段结构功能：这段在全片中承担什么作用
5. 可复用机制：开头、证明、UI演示、转场、字幕、音效、CTA 中可复用的具体做法
6. 不确定处：看不清/听不清处明确标注
"""


def dense_frame_prompt(row: QueueRow, idx: int, count: int, sheet: Path) -> str:
    return f"""你在做抖音 AI工具/AI开源栏目号的视觉层蒸馏。

账号: {row.account}
Post ID: {row.post_id}
标题/文案: {row.caption}
当前图片是全片密集抽帧接触表 {idx + 1}/{count}: {sheet.name}

要求:
- 只基于图片中实际可见的画面、字幕、OCR、UI 元素输出，不要根据标题或常识补画面。
- 如果某个字/界面看不清，写“看不清”，不要猜。
- 注意每个小格左上角的时间戳标签；按时间顺序写。
- 输出中文 Markdown。

必须包含:
1. 本 sheet 覆盖的时间范围。
2. 逐时间段视觉表：时间戳、画面/场景、可读字幕/OCR、剪辑/动效/镜头变化。
3. 可确认的工具/UI/素材：只能写图片中看得到的。
4. 对开场/证明/转场/CTA 的视觉机制观察。
5. 不确定处：看不清或抽帧无法判断的动作连续性。
"""


def final_prompt(row: QueueRow, transcript: str, visual_reviews: list[str], contact_rel: str) -> str:
    joined = "\n\n---\n\n".join(visual_reviews)
    return f"""你是短视频栏目号内容蒸馏员。请把下面证据合并成一个 `content_complete` 级别报告。

硬性要求:
- 只基于证据，不要编造工具功能、画面或口播。
- 输出中文 Markdown。
- 必须包含 content_distillation_status: content_complete。
- 必须给出口播稿校正版、Opening Audit、全片结构时间线、关键帧表、视觉系统、爆款机制、可复用模板、生产素材清单、风险评估、同类选题建议。
- Opening Audit 必须覆盖首帧、0-1s、1-3s、3-5s、5-8s，并判断开场是否匹配标题承诺。
- 关键帧表要把画面和口播/字幕对应起来。
- 视觉描述必须优先使用密集抽帧视觉分析中的可见画面/OCR；不得保留“推测为、可能展示、大概率”等无证据措辞。
- 末尾必须增加 `### Reuse Bank Entry`，下面只写高密度 bullet，字段包括 Evidence、Pattern、Opening、Loop、Visual system、Why it works、Reuse template、Required materials、Risk。

账号: {row.account}
Post ID: {row.post_id}
标题/文案: {row.caption}
互动分: {row.interaction_score}
关键帧接触表: {contact_rel}

SiliconFlow ASR:
{transcript}

Gemini 3.1 密集抽帧视觉分析:
{joined}
"""


def make_dense_frame_sheets(video: Path, sheet_dir: Path, *, force: bool = False) -> list[Path]:
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError("Pillow is required for dense frame sheets")
    if force and sheet_dir.exists():
        shutil.rmtree(sheet_dir)
    sheet_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(sheet_dir.glob("sheet_*.jpg"))
    if existing and not force:
        log(f"[{video.stem}] Dense frame sheets exist: {len(existing)}")
        return existing

    duration = ffprobe_duration(video)
    interval = 1 if duration <= 75 else 2
    frames_dir = sheet_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("frame_*.jpg"):
        old.unlink()
    vf = (
        f"fps=1/{interval},scale=300:-1,"
        "drawtext=text='%{pts\\:hms}':x=8:y=8:fontsize=18:"
        "fontcolor=white:box=1:boxcolor=black@0.65"
    )
    log(f"[{video.stem}] Extracting dense frames every {interval}s")
    run_checked(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            vf,
            "-q:v",
            "3",
            str(frames_dir / "frame_%04d.jpg"),
        ],
        timeout=1200,
    )
    frames = sorted(frames_dir.glob("frame_*.jpg"))
    if not frames:
        raise RuntimeError("No dense frames were created")

    columns = 3
    rows = 3
    per_sheet = columns * rows
    font = ImageFont.load_default()
    sheets: list[Path] = []
    for sheet_idx in range(math.ceil(len(frames) / per_sheet)):
        group = frames[sheet_idx * per_sheet : (sheet_idx + 1) * per_sheet]
        opened = [Image.open(path).convert("RGB") for path in group]
        cell_w = max(img.width for img in opened)
        cell_h = max(img.height for img in opened) + 22
        sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), "white")
        draw = ImageDraw.Draw(sheet)
        for idx, img in enumerate(opened):
            x = (idx % columns) * cell_w
            y = (idx // columns) * cell_h
            frame_no = sheet_idx * per_sheet + idx
            approx_t = frame_no * interval
            label = f"t={approx_t:03d}s"
            draw.rectangle([x, y, x + cell_w, y + 22], fill=(0, 0, 0))
            draw.text((x + 6, y + 5), label, fill=(255, 255, 255), font=font)
            sheet.paste(img, (x, y + 22))
        out = sheet_dir / f"sheet_{sheet_idx:02d}.jpg"
        sheet.save(out, quality=84)
        sheets.append(out)
        for img in opened:
            img.close()
    log(f"[{video.stem}] Dense frame sheets created: {len(sheets)}")
    return sheets


def analyze_dense_frame_sheets(
    row: QueueRow,
    sheets: list[Path],
    out_dir: Path,
    *,
    force: bool = False,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for idx, sheet in enumerate(sheets):
        out = out_dir / f"{row.post_id}_dense_sheet_{idx:02d}_gemini31.md"
        paths.append(out)
        if out.exists() and out.read_text(encoding="utf-8").strip() and not force:
            log(f"[{row.post_id}] Dense sheet {idx:02d} review exists")
            continue
        log(f"[{row.post_id}] Gemini dense-frame review {idx + 1}/{len(sheets)}")
        content = chat_completion_images(
            prompt=dense_frame_prompt(row, idx, len(sheets), sheet),
            image_paths=[sheet],
            max_tokens=1900,
            timeout=300,
        )
        content = clean_model_markdown(content)
        out.write_text(
            f"# Gemini 3.1 Dense Frame Review {idx:02d}: {row.post_id}\n\n{content}\n",
            encoding="utf-8",
        )
    return paths


def analyze_segments(row: QueueRow, segments: list[Path], transcript: str, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for idx, segment in enumerate(segments):
        out = out_dir / f"{row.post_id}_segment_{idx:02d}_gemini31.md"
        paths.append(out)
        if out.exists() and out.read_text(encoding="utf-8").strip():
            log(f"[{row.post_id}] Segment {idx:02d} review exists")
            continue
        log(f"[{row.post_id}] Gemini segment review {idx + 1}/{len(segments)}")
        content = chat_completion(
            prompt=segment_prompt(row, idx, len(segments), transcript),
            video_path=segment,
            max_tokens=2800,
            timeout=480,
        )
        content = clean_model_markdown(content)
        out.write_text(
            f"# Gemini 3.1 Segment Review {idx:02d}: {row.post_id}\n\n{content}\n",
            encoding="utf-8",
        )
    return paths


def merge_final_review(
    row: QueueRow,
    run_dir: Path,
    visual_paths: list[Path],
    transcript: str,
    contact: Path,
    *,
    force: bool = False,
) -> Path:
    out = run_dir / "05_video_multimodal" / "complete" / f"{row.post_id}_content_complete_review.md"
    if out.exists() and out.read_text(encoding="utf-8").strip() and not force:
        log(f"[{row.post_id}] Final review exists: {out}")
        return out
    log(f"[{row.post_id}] Merging final content_complete review")
    visual_reviews = [path.read_text(encoding="utf-8") for path in visual_paths]
    content = chat_completion(
        prompt=final_prompt(row, transcript, visual_reviews, rel(run_dir, contact)),
        video_path=None,
        max_tokens=5200,
        timeout=480,
    )
    content = clean_model_markdown(content)
    out.write_text(f"# Content Complete Review: {row.post_id}\n\n{content}\n", encoding="utf-8")
    _, base_url, model = gemini_config()
    meta = {
        "post_id": row.post_id,
        "model": model,
        "base_url": base_url,
        "evidence_layers": [
            "siliconflow_transcript",
            "gemini31_dense_frame_visual_reviews",
            "keyframes",
        ],
        "response_chars": len(content),
        "api_key_stored": False,
        "visual_method": "dense_timestamped_frame_sheets",
    }
    out.with_name(f"{row.post_id}_content_complete_review_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return out


def update_queue(run_dir: Path, post_id: str) -> None:
    path = run_dir / "03_scoring" / "content_completion_queue.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    for row in rows:
        if row.get("post_id") == post_id:
            row["media_status_current"] = "content_complete"
            row["local_video"] = "yes"
            row["transcript_status"] = "siliconflow_complete"
            row["visual_review_status"] = "gemini31_dense_frame_complete"
            row["keyframe_status"] = "extracted_reviewed"
            row["content_distillation_status"] = "content_complete"
            row["next_action"] = "done_first_pass_review_for_reuse_bank"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def update_evidence_map(
    run_dir: Path,
    row: QueueRow,
    video: Path,
    transcript: Path,
    final_review: Path,
    visual_review_dir: Path,
    dense_sheet_dir: Path,
    contact: Path,
) -> None:
    path = run_dir / "00_index" / "evidence_map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    post = data.setdefault("winner_posts", {}).setdefault(row.post_id, {})
    post.setdefault("account", row.account)
    post.setdefault("rank", int(row.rank) if str(row.rank).isdigit() else row.rank)
    post.setdefault(
        "card",
        f"04_account_deep_dive/{row.account}/winner_cards/{row.post_id}.md",
    )
    post["media_status"] = "content_complete"
    post["content_distillation_status"] = "content_complete"
    post["local_video"] = rel(run_dir, video)
    post["siliconflow_transcript"] = rel(run_dir, transcript)
    post["gemini31_content_complete_review"] = rel(run_dir, final_review)
    post.pop("gemini31_segment_reviews_dir", None)
    post["gemini31_dense_frame_reviews_dir"] = rel(run_dir, visual_review_dir) + "/"
    post["dense_frame_sheets_dir"] = rel(run_dir, dense_sheet_dir) + "/"
    post["keyframe_contact_sheet"] = rel(run_dir, contact)

    wanted = [
        ("siliconflow_transcript", rel(run_dir, transcript)),
        ("gemini31_content_complete_review", rel(run_dir, final_review)),
        ("gemini31_dense_frame_reviews", rel(run_dir, visual_review_dir) + "/"),
        ("dense_frame_sheets", rel(run_dir, dense_sheet_dir) + "/"),
        ("keyframe_contact_sheet", rel(run_dir, contact)),
        ("local_video", rel(run_dir, video)),
    ]
    reviews = [
        item
        for item in post.setdefault("reviews", [])
        if not (isinstance(item, dict) and item.get("kind") == "gemini31_segment_reviews")
    ]
    post["reviews"] = reviews
    existing = {(item.get("kind"), item.get("path")) for item in reviews if isinstance(item, dict)}
    for kind, item_path in wanted:
        if (kind, item_path) not in existing:
            reviews.append({"kind": kind, "path": item_path})

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_winner_card(
    run_dir: Path,
    row: QueueRow,
    video: Path,
    transcript: Path,
    final_review: Path,
    visual_review_dir: Path,
    dense_sheet_dir: Path,
    contact: Path,
) -> None:
    card = run_dir / "04_account_deep_dive" / row.account / "winner_cards" / f"{row.post_id}.md"
    if not card.exists():
        return
    text = card.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    inserted_status = False
    inserted_media = False
    skip_prefixes = (
        "- Content distillation status:",
        "- local_video:",
        "- siliconflow_transcript:",
        "- gemini31_content_complete_review:",
        "- gemini31_segment_reviews:",
        "- gemini31_dense_frame_reviews:",
        "- dense_frame_sheets:",
        "- keyframe_contact_sheet:",
        "- metadata only in this fresh 50 pass",
    )
    for line in lines:
        if line.startswith(skip_prefixes):
            continue
        out.append(line)
        if line.startswith("- Hashtags:") and not inserted_status:
            out.append("- Content distillation status: `content_complete`")
            inserted_status = True
        if line.strip() == "- Media evidence:" and not inserted_media:
            out.extend(
                [
                    f"- local_video: `{rel(run_dir, video)}`",
                    f"- siliconflow_transcript: `{rel(run_dir, transcript)}`",
                    f"- gemini31_content_complete_review: `{rel(run_dir, final_review)}`",
                    f"- gemini31_dense_frame_reviews: `{rel(run_dir, visual_review_dir)}/`",
                    f"- dense_frame_sheets: `{rel(run_dir, dense_sheet_dir)}/`",
                    f"- keyframe_contact_sheet: `{rel(run_dir, contact)}`",
                ]
            )
            inserted_media = True
    if not inserted_status:
        out.insert(0, "- Content distillation status: `content_complete`")
    note = (
        "\nNote: `content_complete` is based on local video, SiliconFlow transcript, "
        "Gemini 3.1 dense timestamped frame visual review, and keyframe/opening audit."
    )
    new_text = "\n".join(out).rstrip()
    if "Gemini 3.1 dense timestamped frame visual review" not in new_text:
        new_text += "\n" + note
    card.write_text(new_text + "\n", encoding="utf-8")


def extract_reuse_entry(final_review: Path) -> str:
    text = final_review.read_text(encoding="utf-8")
    marker = "### Reuse Bank Entry"
    if marker not in text:
        return ""
    entry = text.split(marker, 1)[1].strip()
    entry = re.split(r"\n#{2,3}\s+", entry, maxsplit=1)[0].strip()
    return clean_model_markdown(entry)


def lane_for_card(run_dir: Path, row: QueueRow) -> str:
    card = run_dir / "04_account_deep_dive" / row.account / "winner_cards" / f"{row.post_id}.md"
    if not card.exists():
        return ""
    match = re.search(r"- Lane: `([^`]+)`", card.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def update_reuse_bank(run_dir: Path, row: QueueRow, final_review: Path) -> None:
    path = run_dir / "06_synthesis" / "viral_reuse_bank.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if row.post_id in text:
        return
    entry = extract_reuse_entry(final_review)
    if not entry:
        entry = f"- Evidence: `{rel(run_dir, final_review)}`\n- Pattern: see full content-complete review."
    evidence_line = f"- Evidence: `{rel(run_dir, final_review)}`\n"
    if re.search(r"^-+\s*Evidence:", entry, flags=re.M):
        evidence_line = ""
    block = f"\n### Content-Complete Sample: {row.account} / {row.post_id}\n\n{evidence_line}{entry}\n"
    lane = lane_for_card(run_dir, row)
    section_by_lane = {
        "ai_tool_radar": "## S - AI工具榜单",
        "ai_office": "## S - AI办公公式/模板",
        "open_source_radar": "## A - GitHub/开源项目雷达",
        "ai_video_effect": "## A - AI视频效果前置教程",
        "agent_dev_tool": "## A - Agent/开发者工具排坑",
    }
    heading = section_by_lane.get(lane)
    if heading and heading in text:
        start = text.index(heading)
        next_match = re.search(r"\n## ", text[start + len(heading) :])
        if next_match:
            insert_at = start + len(heading) + next_match.start()
            text = text[:insert_at].rstrip() + "\n" + block + "\n" + text[insert_at:].lstrip()
        else:
            text = text.rstrip() + "\n" + block
    else:
        text = text.rstrip() + "\n" + block
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def append_run_log(run_dir: Path, message: str) -> None:
    path = run_dir / "99_logs" / "run_log.md"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"- {message}\n")


def complete_post(
    run_dir: Path,
    post_id: str,
    tikhub: Path,
    *,
    force_visual: bool = False,
    force_final: bool = False,
) -> None:
    row = find_queue_row(run_dir, post_id)
    media_root = run_dir / "05_video_multimodal" / "media" / post_id
    audio_root = run_dir / "05_video_multimodal" / "complete_audio"
    key_root = run_dir / "05_video_multimodal" / "keyframes" / post_id
    dense_root = run_dir / "05_video_multimodal" / "dense_frames" / post_id
    complete_root = run_dir / "05_video_multimodal" / "complete" / post_id
    dense_review_root = complete_root / "dense_frame_reviews"
    media_root.mkdir(parents=True, exist_ok=True)
    complete_root.mkdir(parents=True, exist_ok=True)

    video = media_root / f"{post_id}.mp4"
    proxy = media_root / f"{post_id}_proxy_480p.mp4"
    audio = audio_root / f"{post_id}_audio.mp3"
    transcript_txt = audio_root / f"{post_id}_siliconflow_transcript.txt"
    transcript_json = audio_root / f"{post_id}_siliconflow_transcript.json"

    if not video.exists() or video.stat().st_size <= 1024:
        if assemble_local_ranged_parts(video):
            write_media_meta(run_dir, post_id, {}, video)
        else:
            url, media_data = fetch_tikhub_media_url(post_id, tikhub)
            reported_size = None
            if isinstance(media_data.get("file_size"), str) and media_data["file_size"].isdigit():
                reported_size = int(media_data["file_size"])
            download_media(url, video, reported_size=reported_size)
            write_media_meta(run_dir, post_id, media_data, video)
    else:
        log(f"[{post_id}] Using existing local video")
        media_meta = media_root / f"{post_id}_media_meta.json"
        if not media_meta.exists():
            write_media_meta(run_dir, post_id, {}, video)

    extract_audio(video, audio)
    transcript = transcribe_siliconflow(audio, transcript_txt, transcript_json)
    contact = extract_keyframes(video, key_root)
    dense_sheets = make_dense_frame_sheets(video, dense_root, force=force_visual)
    visual_paths = analyze_dense_frame_sheets(row, dense_sheets, dense_review_root, force=force_visual)
    final_review = merge_final_review(
        row,
        run_dir,
        visual_paths,
        transcript,
        contact,
        force=force_final or force_visual,
    )

    update_queue(run_dir, post_id)
    update_evidence_map(run_dir, row, video, transcript_txt, final_review, dense_review_root, dense_root, contact)
    update_winner_card(run_dir, row, video, transcript_txt, final_review, dense_review_root, dense_root, contact)
    update_reuse_bank(run_dir, row, final_review)
    append_run_log(run_dir, f"Completed content_complete multimodal review for {row.account}/{post_id}.")
    log(f"[{post_id}] content_complete done")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--post-id", required=True, action="append")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--tikhub", type=Path, default=DEFAULT_TIKHUB)
    parser.add_argument("--force-visual", action="store_true", help="Regenerate dense-frame visual reviews and final report.")
    parser.add_argument("--force-final", action="store_true", help="Regenerate final merged report from existing visual reviews.")
    args = parser.parse_args()

    load_env_file(args.env_file)
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("ffmpeg and ffprobe are required")
    if not args.tikhub.exists():
        raise SystemExit(f"TikHub CLI not found: {args.tikhub}")

    run_dir = args.run_dir.resolve()
    for post_id in args.post_id:
        complete_post(
            run_dir,
            str(post_id),
            args.tikhub,
            force_visual=args.force_visual,
            force_final=args.force_final,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
