"""Vertical 9:16 cutdowns of the strongest scenes for Instagram, TikTok and Shorts."""
import subprocess
from pathlib import Path

from shotwise.stages import breakdown as bd


def pick_scenes(breakdown, count=3, min_s=60, max_s=90):
    """Scenes ranked by dialogue density, with their start offset and trimmed length."""
    scored, t = [], 0.0
    for scene in breakdown.scenes:
        dur = sum(s.duration_s for s in scene.shots)
        lines = sum(len(s.lines) for s in scene.shots)
        if dur >= min_s:
            scored.append((lines / dur, scene.id, t, min(dur, max_s)))
        t += dur
    return [(sid, start, length) for _, sid, start, length in sorted(scored, reverse=True)[:count]]


def render_vertical(master: Path, start_s: float, length_s: float, subs: Path | None, out: Path):
    vf = "crop=ih*9/16:ih,scale=1080:1920"
    if subs and subs.exists():
        vf += f",subtitles={subs.as_posix()}:force_style='FontName=Arial,FontSize=30,Outline=2,MarginV=90'"
    subprocess.run(["ffmpeg", "-y", "-ss", str(start_s), "-t", str(length_s), "-i", str(master), "-vf", vf,
                    "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-movflags", "+faststart", str(out)],
                   check=True, capture_output=True)


def run(config, episode: str) -> list[Path]:
    p = config.pipeline.stages["cutdowns"].params
    out_dir = config.episode_dir(episode) / "out"
    master = out_dir / f"{episode}.mp4"
    if not master.exists():
        raise RuntimeError(f"master not found, run `shotwise assemble {episode}` first")
    outs = []
    for sid, start, length in pick_scenes(bd.load(config, episode), p.get("count", 3), p.get("min_s", 60), p.get("max_s", 90)):
        out = out_dir / f"{episode}_cut_{sid}.mp4"
        render_vertical(master, start, length, out_dir / f"{episode}.srt", out)
        outs.append(out)
    return outs
