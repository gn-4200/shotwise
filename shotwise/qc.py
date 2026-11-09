import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

from shotwise.providers.base import ProviderError, Result

log = logging.getLogger("shotwise.qc")


def ffprobe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def video_qc(min_duration_s=4.0, max_black_ratio=0.02, freeze_max_s=1.0):
    def check(result: Result, job):
        clip = next((f for f in result.files if f.suffix.lower() in (".mp4", ".webm", ".mov")), None)
        if clip is None:
            raise ProviderError("qc_failed", "no video file in result")
        if not shutil.which("ffprobe"):
            log.warning("ffprobe not installed, skipping video QC for %s", clip.name)
            return
        dur = float(ffprobe(clip)["format"]["duration"])
        if dur < min_duration_s:
            raise ProviderError("qc_failed", f"clip is {dur:.1f}s, under {min_duration_s}s")
        logtxt = subprocess.run(["ffmpeg", "-i", str(clip), "-vf",
                                 f"blackdetect=d=0.1:pic_th=0.98,freezedetect=n=-60dB:d={freeze_max_s}",
                                 "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
        black = sum(float(x) for x in re.findall(r"black_duration:([\d.]+)", logtxt))
        if black / dur > max_black_ratio:
            raise ProviderError("qc_failed", f"{black:.1f}s of black frames in {dur:.1f}s")
        if "freeze_start" in logtxt:
            raise ProviderError("qc_failed", "frozen frames detected")
    return check


def face_similarity(candidate: Path, reference: Path) -> float:
    """Cosine similarity of face embeddings (insightface). Works for realistic faces; for stylized
    characters swap in CLIP image similarity."""
    import cv2
    import numpy as np
    from insightface.app import FaceAnalysis
    app = FaceAnalysis(providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))

    def embed(p):
        faces = app.get(cv2.imread(str(p)))
        return max(faces, key=lambda f: f.det_score).normed_embedding if faces else None

    a, b = embed(candidate), embed(reference)
    return float(np.dot(a, b)) if a is not None and b is not None else 0.0


def make_qc(stage: str, cfg: dict):
    if stage == "video":
        return video_qc(cfg.get("min_duration_s", 4), cfg.get("max_black_ratio", 0.02), cfg.get("freeze_max_s", 1.0))
    if stage == "keyframes" and cfg.get("face_similarity_min", 0) > 0:
        def check(result: Result, job):
            ref = job.params.get("reference")
            if not ref or not Path(ref).exists():
                return
            try:
                score = face_similarity(result.files[0], Path(ref))
            except ImportError:
                log.warning("insightface not installed, skipping face QC")
                return
            if score < cfg["face_similarity_min"]:
                raise ProviderError("qc_failed", f"character similarity {score:.2f} below {cfg['face_similarity_min']}")
        return check
    return None
