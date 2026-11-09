"""Generic per-shot stage runner: keyframes, video, voice, lipsync, and per-scene music."""
import json
from datetime import datetime

from shotwise.chain import StageBlocked, run_chain
from shotwise.providers.base import Deferred, ManualRequired
from shotwise.providers.registry import chain_for
from shotwise.providers.remote import RemoteQueue
from shotwise.qc import make_qc
from shotwise.stages import breakdown as bd
from shotwise.stages.jobs import build_jobs, music_job

REMOTE_STAGES = {"video", "lipsync", "music"}
STAGES = ("keyframes", "video", "voice", "lipsync", "music")
FINAL = ("approved", "done")


def _providers(config, stage, force):
    providers = chain_for(config, stage, force)
    if config.pipeline.workers.transport == "rclone" and stage in REMOTE_STAGES:
        queue = config.root / config.pipeline.workers.queue_dir
        providers = [RemoteQueue(p, queue) if hasattr(p, "workflow_path") else p for p in providers]
    return providers


def _log_prompt(config, episode, sid, stage, job, result):
    if sid.startswith("music:"):
        return
    path = config.shot_dir(episode, sid) / "prompts.json"
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    rows.append({"stage": stage, "provider": result.provider, "prompt": job.prompt, "at": datetime.now().isoformat(timespec="seconds"),
                 "params": {k: v for k, v in job.params.items() if k in ("expected_filename", "attempt", "seed", "duration_s")},
                 "files": [f.name for f in result.files]})
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def _prereq(config, stage, episode, shot, scfg):
    """Return a (status, note) pair when the shot cannot run this stage yet, else None."""
    sd = config.shot_dir(episode, shot["id"])
    if stage == "video" and not shot.get("needs_video", True):
        return "skipped", "animated still"
    if stage == "video" and not (sd / "keyframes" / "approved.png").exists():
        return "waiting", "approve a keyframe first"
    if stage == "voice" and not shot.get("lines"):
        return "skipped", "no dialogue"
    if stage == "lipsync":
        if shot.get("shot_type") not in scfg.params.get("only_shot_types", []):
            return "skipped", "not a dialogue close-up"
        if not (sd / "video" / "approved.mp4").exists() or not (sd / "voice" / "line_1.wav").exists():
            return "waiting", "needs an approved clip and a voice line"
    return None


def run_stage(config, store, stage, episode, shot_ids=None, force=None) -> dict:
    scfg = config.pipeline.stages[stage]
    providers = _providers(config, stage, force)
    qc = make_qc(stage, scfg.qc)
    bible = config.bible()
    breakdown = bd.load(config, episode)
    scenes = {s.id: s.model_dump() for s in breakdown.scenes}
    report = {k: [] for k in ("done", "review", "manual", "queued", "blocked", "skipped", "waiting")}

    def execute(sid, jobs, lane):
        chain = providers
        if lane == "premium":
            chain = [p for p in providers if p.name.startswith("manual")] or providers[-1:]
        outcome, note = "ok", ""
        for job in jobs:
            try:
                res = run_chain(chain, job, store, attempts=scfg.attempts, qc=qc)
                _log_prompt(config, episode, sid, stage, job, res)
                note = res.provider
            except ManualRequired as e:
                outcome, note = "manual", str(e.request_file.name)
            except Deferred as e:
                outcome, note = ("queued", e.job_id) if outcome != "manual" else (outcome, note)
            except StageBlocked as e:
                store.set_status(episode, sid, stage, "blocked", str(e))
                report["blocked"].append(sid)
                return
        if outcome == "ok":
            status = "needs_review" if scfg.gate else "done"
            store.set_status(episode, sid, stage, status, note)
            report["review" if scfg.gate else "done"].append(sid)
        else:
            store.set_status(episode, sid, stage, "manual_required" if outcome == "manual" else "queued", note)
            report[outcome].append(sid)

    if stage == "music":
        for scene in breakdown.scenes:
            sid = f"music:{scene.id}"
            if shot_ids and sid not in shot_ids:
                continue
            try:
                row = store.get_shot(episode, sid)
            except KeyError:
                row = {"id": sid, "shot_type": "insert", "duration_s": float(scfg.params.get("seconds_per_cue", 90)),
                       "location": scene.location, "camera": "", "action": f"music cue: {scene.mood}", "characters": [],
                       "lines": [], "needs_video": False, "lane": "free", "stages": {}}
                store.upsert_shot(episode, row, scene.id)
            if row["stages"].get(stage, {}).get("status") in FINAL:
                continue
            execute(sid, [music_job(config, episode, scene.model_dump(), scfg)], row.get("lane", "free"))
        return report

    for shot in store.list_shots(episode):
        sid = shot["id"]
        if sid.startswith("music:") or (shot_ids and sid not in shot_ids):
            continue
        if shot["stages"].get(stage, {}).get("status") in FINAL:
            continue
        if (pre := _prereq(config, stage, episode, shot, scfg)):
            store.set_status(episode, sid, stage, *pre)
            report[pre[0]].append(sid)
            continue
        execute(sid, build_jobs(config, stage, episode, shot, scenes[shot["scene"]], bible, scfg), shot.get("lane", "free"))
    return report


def resume(config, store, episode: str) -> dict:
    """Finish a pending breakdown, then re-run every stage; manual and queued jobs pick up their results."""
    merged: dict = {}
    ep = config.episode_dir(episode)
    if not (ep / "script.md").exists():
        from shotwise.stages import script
        script.run(config, store, episode)                   # raises ManualRequired until response.md is pasted
        merged["script"] = ["done"]
    if not (config.episode_dir(episode) / "breakdown.json").exists():
        bd.run(config, store, episode)                       # raises ManualRequired if the response is still missing
        merged["breakdown"] = ["done"]
    for stage in STAGES:
        for k, v in run_stage(config, store, stage, episode).items():
            merged.setdefault(k, []).extend(v)
    return merged
