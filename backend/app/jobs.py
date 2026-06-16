"""In-process async job store for the upload pipeline (single uvicorn worker).

Completed jobs persist to a JSON file so their results survive a service
restart; in-flight jobs (background threads) are not resumed — the FE will just
see a stuck stage and the user can re-upload.

COMPLIANCE: stores ONLY our own pipeline outputs (stage, the stored audio's
extension, the transcript/score/decode result). It never holds Musixmatch lyric
content — the match branch keeps only {title, artist, trackId}.
"""

import json
import threading
import time
import uuid
from pathlib import Path

STAGES = ("uploaded", "transcribing", "correcting", "matching", "done", "error")

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_STORE = _DATA_DIR / "jobs.json"
_lock = threading.Lock()


def _load() -> dict:
    try:
        with open(_STORE, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


_jobs: dict = _load()


def _persist() -> None:
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _STORE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(_jobs, fh, ensure_ascii=False)
        tmp.replace(_STORE)
    except OSError:
        pass  # in-process dict still holds it; persistence is best-effort


def create(ext: str) -> str:
    jid = uuid.uuid4().hex[:16]
    with _lock:
        _jobs[jid] = {
            "jobId": jid,
            "stage": "uploaded",
            "ext": ext,
            "created": time.time(),
            "error": None,
            "result": None,
        }
        _persist()
    return jid


def get(jid: str) -> dict | None:
    return _jobs.get(jid)


def set_stage(jid: str, stage: str) -> None:
    with _lock:
        j = _jobs.get(jid)
        if j:
            j["stage"] = stage
            _persist()


def set_result(jid: str, result: dict) -> None:
    with _lock:
        j = _jobs.get(jid)
        if j:
            j["result"] = result
            j["stage"] = "done"
            _persist()


def set_error(jid: str, msg: str) -> None:
    with _lock:
        j = _jobs.get(jid)
        if j:
            j["error"] = msg
            j["stage"] = "error"
            _persist()
