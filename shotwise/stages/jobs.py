"""Builds Job objects per stage: prompts rendered from prompts/*.md, inputs taken from earlier stages."""
from jinja2 import Template

from shotwise.providers.base import Job


def _tpl(config, name):
    return Template((config.root / "prompts" / name).read_text(encoding="utf-8"))


def _ctx(shot, scene, bible):
    chars = [{"name": n, **bible["characters"].get(n, {"look": n})} for n in shot.get("characters", [])]
    loc = bible["locations"].get(shot["location"], {"look": shot["location"]})
    return {"shot": shot, "characters": chars, "location": loc, "scene": scene, "style": bible["style"],
            "note": shot.get("note", "")}


def build_jobs(config, stage, episode, shot, scene, bible, scfg) -> list[Job]:
    sd = config.shot_dir(episode, shot["id"])
    ctx = _ctx(shot, scene, bible)
    negative = bible["style"].get("negative", "")
    if stage == "keyframes":
        prompt = _tpl(config, "keyframe.md").render(**ctx).strip()
        ref = None
        if shot.get("characters"):
            sheet = config.root / "bible" / "characters" / shot["characters"][0].lower() / "sheet.png"
            ref = sheet if sheet.exists() else None
        return [Job(stage, episode, shot["id"], sd / "keyframes", prompt, {"ref_image": ref} if ref else {},
                    {"expected_filename": f"cand_{n}.png", "negative": negative, "reference": str(ref or ""), **scfg.params})
                for n in range(1, scfg.candidates + 1)]
    if stage == "video":
        prompt = _tpl(config, "video.md").render(**ctx).strip()
        fps = scfg.params.get("fps", 24)
        return [Job(stage, episode, shot["id"], sd / "video", prompt, {"keyframe": sd / "keyframes" / "approved.png"},
                    {"expected_filename": "attempt_{attempt}.mp4", "duration_s": shot["duration_s"],
                     "length": int(shot["duration_s"] * fps), "negative": negative, **scfg.params})]
    if stage == "voice":
        jobs = []
        for i, line in enumerate(shot.get("lines", []), 1):
            c = bible["characters"].get(line["speaker"], {})
            ref = config.root / c["voice_ref"] if c.get("voice_ref") else None
            emotion = line.get("emotion", "neutral")
            jobs.append(Job(stage, episode, shot["id"], sd / "voice", line["text"], {"voice_ref": ref} if ref else {},
                            {"expected_filename": f"line_{i}.wav", "voice": c.get("voice"), "speaker": line["speaker"],
                             "emotion": emotion, "exaggeration": bible["emotion"].get(emotion, 0.5)}))
        return jobs
    if stage == "lipsync":
        return [Job(stage, episode, shot["id"], sd / "lipsync", "",
                    {"video": sd / "video" / "approved.mp4", "audio": sd / "voice" / "line_1.wav"},
                    {"expected_filename": "attempt_{attempt}.mp4", "duration_s": shot["duration_s"]})]
    raise ValueError(f"no job builder for stage '{stage}'")


def music_job(config, episode, scene, scfg) -> Job:
    prompt = f"{scene['mood']}, cinematic score, {scene['time_of_day']}, instrumental, no vocals"
    return Job("music", episode, f"music:{scene['id']}", config.episode_dir(episode) / "audio" / "music" / scene["id"],
               prompt, {}, {"expected_filename": "cue.wav", "seconds": scfg.params.get("seconds_per_cue", 90), "lyrics": "[inst]"})
