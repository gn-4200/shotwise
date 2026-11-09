"""Assembly: normalize approved shots, build dialogue and music tracks, concat, mix and master. Needs ffmpeg + pydub."""
import subprocess
from pathlib import Path

from shotwise.stages import breakdown as bd


def timeline(breakdown) -> list[tuple[dict, float]]:
    """Shots in scene order with their start offset in seconds."""
    t, rows = 0.0, []
    for scene in breakdown.scenes:
        for shot in scene.shots:
            rows.append((shot.model_dump() | {"scene": scene.id}, t))
            t += shot.duration_s
    return rows


def source_for(config, episode, shot) -> Path | None:
    sd = config.shot_dir(episode, shot["id"])
    for p in (sd / "lipsync" / "approved.mp4", sd / "video" / "approved.mp4", sd / "keyframes" / "approved.png"):
        if p.exists():
            return p
    return None


def render_shot(shot, src: Path, out: Path, w, h, fps, crf):
    """Stills get a slow push-in (Ken Burns). Clips are scaled and padded to the master size."""
    d = shot["duration_s"]
    if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        frames = int(d * fps)
        vf = (f"scale=8000:-1,zoompan=z='min(zoom+0.0008,1.12)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":s={w}x{h}:fps={fps}")
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(src), "-vf", vf, "-t", str(d)]
    else:
        vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={fps}"
        cmd = ["ffmpeg", "-y", "-i", str(src), "-vf", vf, "-t", str(d)]
    subprocess.run(cmd + ["-an", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p", str(out)],
                   check=True, capture_output=True)


def _ts(ms: int) -> str:
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def dialogue_track(config, episode, rows, out: Path, gap_ms=250):
    from pydub import AudioSegment
    total_ms = int(sum(s["duration_s"] for s, _ in rows) * 1000) + 1000
    track = AudioSegment.silent(duration=total_ms)
    srt, n = [], 1
    for shot, start in rows:
        cursor = int(start * 1000) + 300
        for i, line in enumerate(shot.get("lines", []), 1):
            wav = config.shot_dir(episode, shot["id"]) / "voice" / f"line_{i}.wav"
            if not wav.exists():
                continue
            seg = AudioSegment.from_file(wav)
            track = track.overlay(seg, position=cursor)
            srt.append(f"{n}\n{_ts(cursor)} --> {_ts(cursor + len(seg))}\n{line['speaker']}: {line['text']}\n")
            n += 1
            cursor += len(seg) + gap_ms
    track.export(out, format="wav")
    out.with_suffix(".srt").write_text("\n".join(srt), encoding="utf-8")


def music_track(config, episode, breakdown, out: Path, fade_ms=1500):
    from pydub import AudioSegment
    total_ms = int(sum(s.duration_s for sc in breakdown.scenes for s in sc.shots) * 1000) + 1000
    track = AudioSegment.silent(duration=total_ms)
    t = 0
    for scene in breakdown.scenes:
        length = int(sum(s.duration_s for s in scene.shots) * 1000)
        cue = config.episode_dir(episode) / "audio" / "music" / scene.id / "cue.wav"
        if cue.exists():
            seg = AudioSegment.from_file(cue)
            while len(seg) < length:
                seg += seg
            track = track.overlay(seg[:length].fade_in(fade_ms).fade_out(fade_ms), position=t)
        t += length
    track.export(out, format="wav")


def concat(clips: list[Path], out: Path):
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in clips), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True, capture_output=True)


def mix_and_master(video: Path, dialogue: Path, music: Path, subs: Path | None, out: Path, crf):
    """Music ducks under dialogue, loudness to -16 LUFS, subtitles burned, faststart for web."""
    fc = ("[1:a]asplit=2[d1][d2];[2:a]volume=0.9[m];[m][d1]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[ducked];"
          "[d2][ducked]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]")
    vmap = "0:v"
    if subs and subs.exists():
        fc += f";[0:v]subtitles={subs.as_posix()}:force_style='FontName=Arial,FontSize=20,Outline=1'[v]"
        vmap = "[v]"
    subprocess.run(["ffmpeg", "-y", "-i", str(video), "-i", str(dialogue), "-i", str(music), "-filter_complex", fc,
                    "-map", vmap, "-map", "[a]", "-c:v", "libx264", "-crf", str(crf), "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", str(out)], check=True, capture_output=True)


def run(config, episode: str) -> Path:
    p = config.pipeline.stages["assemble"].params
    w, h, fps, crf = p.get("width", 1920), p.get("height", 1080), p.get("fps", 24), p.get("crf", 18)
    breakdown = bd.load(config, episode)
    rows = timeline(breakdown)
    missing = [s["id"] for s, _ in rows if source_for(config, episode, s) is None]
    if missing:
        raise RuntimeError(f"{len(missing)} shots have no approved keyframe or clip: {', '.join(missing[:10])}")
    out_dir = config.episode_dir(episode) / "out"
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    clips = []
    for shot, _ in rows:
        clip = work / f"{shot['id']}.mp4"
        if not clip.exists():
            render_shot(shot, source_for(config, episode, shot), clip, w, h, fps, crf)
        clips.append(clip)
    audio = config.episode_dir(episode) / "audio"
    audio.mkdir(exist_ok=True)
    dialogue_track(config, episode, rows, audio / "dialogue.wav")
    music_track(config, episode, breakdown, audio / "music.wav")
    concat(clips, work / "video.mp4")
    master = out_dir / f"{episode}.mp4"
    mix_and_master(work / "video.mp4", audio / "dialogue.wav", audio / "music.wav",
                   audio / "dialogue.srt" if p.get("burn_subtitles", True) else None, master, crf)
    (audio / "dialogue.srt").replace(out_dir / f"{episode}.srt")
    return master
